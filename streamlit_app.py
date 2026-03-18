"""
streamlit_app.py — HR Agent UI (FSM approach)

FSM States:
  input      → user fills form and clicks Run
  screening  → pipeline runs synchronously (blocks, shows spinner)
  hitl       → HR reviews and makes decision
  complete   → show final result

Key insight from the article:
  Never run long tasks in background threads with queues.
  Instead, run synchronously in the Streamlit main thread.
  Use st.session_state as the FSM state store.
  HITL is just another state — pipeline result is stored,
  HR makes decision, then resume pipeline from that point.
"""

import os
import sys
import tempfile

# ── Path setup ────────────────────────────────────────────────
_app_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.join(_app_dir, "src", "hr_agent")
for _p in [_app_dir, _src_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st
import os
from dotenv import load_dotenv
load_dotenv()
st.set_page_config(page_title="HR Agent", page_icon="🎯", layout="centered")

# ── LangSmith tracing ─────────────────────────────────────────
# Must be set before any LangChain imports (load_nodes/load_graphs
# are cached so they only run once, but env vars must be ready first)
def _setup_langsmith():
    import os
    from dotenv import load_dotenv
    load_dotenv()
 
    api_key = os.getenv("LANGSMITH_API_KEY", "")
    if not api_key:
        return  # tracing disabled if no key
 
    os.environ["LANGSMITH_API_KEY"]=os.getenv("LANGSMITH_API_KEY")
    os.environ["LANGCHAIN_TRACING_V2"]="true"
    os.environ["LANGCHAIN_PROJECT"]="HR Agent"
    os.environ["LANGCHAIN_ENDPOINT"]    = "https://api.smith.langchain.com"
 
_setup_langsmith()
 
# ── Load pipeline nodes (cached) ─────────────────────────────
@st.cache_resource
def load_nodes():

    from src.hr_agent.nodes.resume_extractor      import resume_extractor
    from src.hr_agent.nodes.resume_scorer         import resume_scorer
    from src.hr_agent.nodes.profile_extractor     import profile_extractor
    from src.hr_agent.nodes.workers.base_worker   import dispatch_workers
    from src.hr_agent.nodes.workers.python_worker import python_worker
    from src.hr_agent.nodes.workers.readme_worker import readme_worker
    from src.hr_agent.nodes.workers.infra_worker  import infra_worker
    from src.hr_agent.nodes.workers.config_worker import config_worker
    from src.hr_agent.nodes.workers.notebook_worker import notebook_worker
    from src.hr_agent.nodes.synthesizer           import synthesizer
    from src.hr_agent.nodes.final_review          import final_review
    from src.hr_agent.nodes.github_scorer         import github_scorer
    from src.hr_agent.nodes.decision_engine       import decision_engine, route_hitl_outcome
    from src.hr_agent.nodes.email_nodes           import send_acceptance_email, send_rejection_email
    from src.hr_agent.tools.logger                    import configure_logger, pipeline_stats
    return {
        "resume_extractor":      resume_extractor,
        "resume_scorer":         resume_scorer,
        "profile_extractor":     profile_extractor,
        "dispatch_workers":      dispatch_workers,
        "python_worker":         python_worker,
        "readme_worker":         readme_worker,
        "infra_worker":          infra_worker,
        "config_worker":         config_worker,
        "notebook_worker":       notebook_worker,
        "synthesizer":           synthesizer,
        "final_review":          final_review,
        "github_scorer":         github_scorer,
        "decision_engine":       decision_engine,
        "send_acceptance_email": send_acceptance_email,
        "send_rejection_email":  send_rejection_email,
        "configure_logger":      configure_logger,
        "pipeline_stats":        pipeline_stats,
    }

nodes = load_nodes()


# ── Two sub-graphs (cached) ───────────────────────────────────
@st.cache_resource
def load_graphs():
    """
    Phase 1 graph: START → ... → decision_engine → END
    Stops at decision_engine and returns state. No HITL node needed.

    Phase 2 graph: email only — called after HR decides.
    """
    from langgraph.graph import StateGraph, START, END
    from src.hr_agent.core.state import GraphState
    from langgraph.types import Send

    # ── Phase 1: resume + github + decision ───────────────────
    b1 = StateGraph(GraphState)
    b1.add_node("resume_extractor",  nodes["resume_extractor"])
    b1.add_node("resume_scorer",     nodes["resume_scorer"])
    b1.add_node("profile_extractor", nodes["profile_extractor"])
    b1.add_node("python_worker",     nodes["python_worker"])
    b1.add_node("readme_worker",     nodes["readme_worker"])
    b1.add_node("infra_worker",      nodes["infra_worker"])
    b1.add_node("config_worker",     nodes["config_worker"])
    b1.add_node("notebook_worker",   nodes["notebook_worker"])
    b1.add_node("synthesizer",       nodes["synthesizer"])
    b1.add_node("final_review",      nodes["final_review"])
    b1.add_node("github_scorer",     nodes["github_scorer"])
    b1.add_node("decision_engine",   nodes["decision_engine"])

    b1.add_edge(START, "resume_extractor")
    b1.add_edge("resume_extractor", "resume_scorer")

    # branch after resume_scorer:
    # has github_url → full GitHub analysis pipeline
    # no github_url  → skip straight to decision_engine
    def route_after_resume_scorer(state):
        return "profile_extractor" if state.get("github_url") else "decision_engine"

    b1.add_conditional_edges(
        "resume_scorer", route_after_resume_scorer,
        {"profile_extractor": "profile_extractor", "decision_engine": "decision_engine"}
    )

    def route_after_profile_extractor(state):
        if not state.get("analyzed_repos"):
            return ["decision_engine"]
        return nodes["dispatch_workers"](state)
 
    b1.add_conditional_edges(
        "profile_extractor", route_after_profile_extractor,
        ["python_worker","readme_worker","infra_worker",
         "config_worker","notebook_worker","synthesizer","decision_engine"],
    )

    b1.add_edge("python_worker",   "synthesizer")
    b1.add_edge("readme_worker",   "synthesizer")
    b1.add_edge("infra_worker",    "synthesizer")
    b1.add_edge("config_worker",   "synthesizer")
    b1.add_edge("notebook_worker", "synthesizer")
    b1.add_edge("synthesizer",     "final_review")
    b1.add_edge("final_review",    "github_scorer")
    b1.add_edge("github_scorer",   "decision_engine")
    b1.add_edge("decision_engine", END)   # always stop here

    graph1 = b1.compile()

    # ── Phase 2: email only ────────────────────────────────────
    b2 = StateGraph(GraphState)
    b2.add_node("send_acceptance_email", nodes["send_acceptance_email"])
    b2.add_node("send_rejection_email",  nodes["send_rejection_email"])

    def route_email(s):
        d = s.get("decision","rejected")
        if d in ("auto_select","approved"): return "send_acceptance_email"
        return "send_rejection_email"

    b2.add_conditional_edges(START, route_email,
        {"send_acceptance_email":"send_acceptance_email",
         "send_rejection_email": "send_rejection_email"})
    b2.add_edge("send_acceptance_email", END)
    b2.add_edge("send_rejection_email",  END)

    graph2 = b2.compile()
    return graph1, graph2

graph1, graph2 = load_graphs()


# ── Session state init ────────────────────────────────────────
def init():
    defaults = {
        "state":        "input",   # FSM state
        "pipeline_out": None,      # result after phase 1
        "final_out":    None,      # result after phase 2
        "email_body":   None,      # captured email
        "tmp_path":     None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init()


# ── Email capture helper ──────────────────────────────────────
@st.cache_resource
def get_email_capture():
    """Returns a dict that email_nodes._send_email will write into."""
    return {"to": "", "subject": "", "body": ""}

_email_capture = get_email_capture()

@st.cache_resource
def patch_email():
    from src.hr_agent.nodes import email_nodes          as em
    original = em._send_email
    def _send_and_capture(to_email, subject, body, log=None):
        _email_capture["to"]      = to_email
        _email_capture["subject"] = subject
        _email_capture["body"]    = body

        original(to_email, subject, body, log=log)

    em._send_email = _send_and_capture
    return original

patch_email()


# ── Initial state builder ─────────────────────────────────────
def make_initial_state(jd, resume_path, role):
    return {
        "job_description": jd,  "resume_path": resume_path,
        "applied_role": role,   "resume_text": "",
        "candidate_name": "",   "candidate_email": "",
        "current_role": "",     "github_url": None,
        "linkedin_url": None,   "routed_files": [],
        "analyzed_repos": [],   "summaries": {},
        "next_action": "",      "final_summary": "",
        "final_profile": "",
        "not_a_resume":  False,    "resume_score": 0.0,
        "resume_analysis": "",  "github_score": 0.0,
        "github_analysis": "",  "decision": "hitl",
        "hitl_outcome": None,   "hitl_reason": None,
        "hitl_packet": None,    "rejection_reason": "",
        "next_steps": "",       "email_sent": False,
    }


# ══════════════════════════════════════════════════════════════
# FSM STATE: input
# ══════════════════════════════════════════════════════════════
if st.session_state.state == "input":

    st.title("🎯 HR Agent")
    st.caption("Automated Candidate Screening Pipeline")

    uploaded = st.file_uploader("Resume (PDF or DOCX)", type=["pdf","docx"])
    jd       = st.text_area("Job Description", height=200,
                            placeholder="Paste the full job description here...")
    role     = st.text_input("Applied Role", placeholder="e.g. Junior AI Engineer")

    if st.button("▶ Run Pipeline", type="primary"):
        if not uploaded or not jd.strip() or not role.strip():
            st.error("Please provide resume, job description, and applied role.")
        else:
            # save to temp file first so validator can read it
            suffix = ".pdf" if uploaded.name.endswith(".pdf") else ".docx"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(uploaded.getbuffer())
            tmp.close()
 
            # ── Input validation ──────────────────────────────
            from src.hr_agent.tools.input_validator import validate_all
            validation = validate_all(
                file_path = tmp.name,
                file_name = uploaded.name,
                jd        = jd,
                role      = role,
            )
 
            # show warnings even if ok
            for w in validation["warnings"]:
                st.warning(w)
 
            if not validation["ok"]:
                # show all errors and stop
                for e in validation["errors"]:
                    st.error(e)
                os.unlink(tmp.name)
            else:
                # use sanitized inputs going forward
                st.session_state.tmp_path = tmp.name
                st.session_state.jd       = validation["jd"].sanitized
                st.session_state.role     = validation["role"].sanitized
                st.session_state.state    = "screening"
                st.rerun()


# ══════════════════════════════════════════════════════════════
# FSM STATE: screening — runs pipeline synchronously
# ══════════════════════════════════════════════════════════════
elif st.session_state.state == "screening":

    st.title("🎯 HR Agent")
    with st.spinner("⏳ Screening candidate... this takes 1-2 minutes."):
        try:
            nodes["configure_logger"](log_file="logs/pipeline.jsonl", level="INFO")
            nodes["pipeline_stats"].reset()

            initial = make_initial_state(
                st.session_state.jd,
                st.session_state.tmp_path,
                st.session_state.role,
            )
            result = graph1.invoke(initial)
            st.session_state.pipeline_out = result
            decision = result.get("decision","hitl")

            if decision == "auto_select":
                # run email directly
                email_result = graph2.invoke(result)
                st.session_state.final_out  = email_result
                st.session_state.email_body = dict(_email_capture)
                st.session_state.state      = "complete"
            else:
                # needs HR review
                st.session_state.state = "hitl"

        except Exception as e:
            import traceback
            st.session_state.error = str(e)
            st.session_state.trace = traceback.format_exc()
            st.session_state.state = "error"

    st.rerun()


# ══════════════════════════════════════════════════════════════
# FSM STATE: hitl — HR makes decision
# ══════════════════════════════════════════════════════════════
elif st.session_state.state == "hitl":

    st.title("🎯 HR Agent")
    result = st.session_state.pipeline_out or {}
    packet = result.get("hitl_packet") or {}

    st.subheader("⚠️ HR Review Required")
    st.info(packet.get("review_reason", result.get("hitl_reason", "Manual review needed.")))

    col1, col2 = st.columns(2)
    col1.metric("Resume Score", f"{int(result.get('resume_score',0))}/100")
    col2.metric("GitHub Score", f"{int(result.get('github_score',0))}/100")

    st.markdown(f"**Candidate:** {result.get('candidate_name','—')}")
    st.markdown(f"**Current Role:** {result.get('current_role','—')}")
    if result.get("github_url"):
        st.markdown(f"**GitHub:** [{result['github_url']}]({result['github_url']})")

    with st.expander("Resume Analysis"):
        st.text(result.get("resume_analysis","—"))
    with st.expander("GitHub Analysis"):
        st.text(result.get("github_analysis","—"))

    st.divider()
    st.markdown("**Your Decision**")
    reason = st.text_input("Reason / Notes (required)", key="hitl_reason")

    col_a, col_r, col_i = st.columns(3)

    with col_a:
        if st.button("✅ Approve", use_container_width=True):
            if not reason.strip():
                st.error("Please enter a reason.")
            else:
                role = result.get("applied_role", result.get("current_role","the position"))
                updated = {
                    **result,
                    "hitl_outcome": "approved",
                    "hitl_reason":  reason,
                    "decision":     "approved",
                    "next_steps": (
                        f"Congratulations! Following a thorough review of your profile, "
                        f"we are pleased to invite you to the next stage of the interview "
                        f"process for the {role} position. "
                        f"Our team will be in touch within 2 business days.\n\n"
                        f"Reviewer note: {reason}"
                    ),
                    "rejection_reason": "",
                }
                with st.spinner("Sending email..."):
                    final = graph2.invoke(updated)
                st.session_state.final_out  = final
                st.session_state.email_body = dict(_email_capture)
                st.session_state.state      = "complete"
                st.rerun()

    with col_r:
        if st.button("❌ Reject", use_container_width=True):
            if not reason.strip():
                st.error("Please enter a reason.")
            else:
                role = result.get("applied_role", result.get("current_role","the position"))
                updated = {
                    **result,
                    "hitl_outcome": "rejected",
                    "hitl_reason":  reason,
                    "decision":     "rejected",
                    "next_steps":   "",
                    "rejection_reason": (
                        f"Thank you for your interest in the {role} position. "
                        f"After a careful review, we will not be moving forward "
                        f"at this time.\n\nWe appreciate your time and wish you the best."
                    ),
                }
                with st.spinner("Sending email..."):
                    final = graph2.invoke(updated)
                st.session_state.final_out  = final
                st.session_state.email_body = dict(_email_capture)
                st.session_state.state      = "complete"
                st.rerun()

    with col_i:
        if st.button("❓ More Info", use_container_width=True):
            if not reason.strip():
                st.error("Please enter a reason.")
            else:
                role = result.get("applied_role", result.get("current_role","the position"))
                updated = {
                    **result,
                    "hitl_outcome": "rejected",
                    "hitl_reason":  reason,
                    "decision":     "request_more_info",
                    "next_steps":   "",
                    "rejection_reason": (
                        f"Thank you for your interest in the {role} position. "
                        f"We would like to request some additional information.\n\n"
                        f"{reason}\n\nPlease reply with the requested information."
                    ),
                }
                with st.spinner("Sending email..."):
                    final = graph2.invoke(updated)
                st.session_state.final_out  = final
                st.session_state.email_body = dict(_email_capture)
                st.session_state.state      = "complete"
                st.rerun()


# ══════════════════════════════════════════════════════════════
# FSM STATE: complete
# ══════════════════════════════════════════════════════════════
elif st.session_state.state == "complete":

    st.title("🎯 HR Agent")

    result   = st.session_state.final_out or st.session_state.pipeline_out or {}
    decision = result.get("decision","").upper()
    candidate= result.get("candidate_name","—")
    r_score  = result.get("resume_score", 0)
    g_score  = result.get("github_score", 0)

    if decision in ("AUTO_SELECT","APPROVED"):
        st.success(f"✅ **{candidate}** — {decision.replace('_',' ')}")
    elif decision == "REJECTED":
        st.error(f"❌ **{candidate}** — Rejected")
    else:
        st.warning(f"⏸ **{candidate}** — {decision.replace('_',' ')}")

    col1, col2 = st.columns(2)
    col1.metric("Resume Score", f"{int(r_score)}/100")
    col2.metric("GitHub Score", f"{int(g_score)}/100")

    with st.expander("Resume Analysis"):
        st.text(result.get("resume_analysis","—"))
    with st.expander("GitHub Analysis"):
        st.text(result.get("github_analysis","—"))

    em = st.session_state.email_body
    if em and em.get("body"):
        st.divider()
        st.subheader("📧 Email Preview")
        st.text(f"To: {em.get('to','')}")
        st.text(f"Subject: {em.get('subject','')}")
        st.text_area("Body", em.get("body",""), height=150, disabled=True)

    # pipeline stats
    try:
        stats = nodes["pipeline_stats"].summary()
        st.divider()
        st.caption(
            f"⏱ {round(stats.get('total_duration_ms',0)/1000,1)}s  "
            f"| 🔁 {stats.get('primary_failures',0)} failures / "
            f"{stats.get('fallback_triggers',0)} fallbacks  "
            f"| 🪙 {stats.get('total_input_tokens',0):,} in / "
            f"{stats.get('total_output_tokens',0):,} out tokens"
        )
    except Exception:
        pass

    st.divider()
    if st.button("← New Screening"):
        if st.session_state.get("tmp_path"):
            try: os.unlink(st.session_state.tmp_path)
            except: pass
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ══════════════════════════════════════════════════════════════
# FSM STATE: error
# ══════════════════════════════════════════════════════════════
elif st.session_state.state == "error":

    st.title("🎯 HR Agent")
    st.error(f"Pipeline failed: {st.session_state.get('error','Unknown error')}")
    with st.expander("Stack trace"):
        st.code(st.session_state.get("trace",""), language="python")
    if st.button("← Start Over"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()