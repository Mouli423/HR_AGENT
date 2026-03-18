from langgraph.graph import StateGraph, START, END

from src.hr_agent.core.state import GraphState
from src.hr_agent.nodes.resume_extractor          import resume_extractor
from src.hr_agent.nodes.resume_scorer             import resume_scorer
from src.hr_agent.nodes.profile_extractor         import profile_extractor
from src.hr_agent.nodes.workers.base_worker       import dispatch_workers
from src.hr_agent.nodes.workers.python_worker     import python_worker
from src.hr_agent.nodes.workers.readme_worker     import readme_worker
from src.hr_agent.nodes.workers.infra_worker      import infra_worker
from src.hr_agent.nodes.workers.config_worker     import config_worker
from src.hr_agent.nodes.workers.notebook_worker   import notebook_worker
from src.hr_agent.nodes.synthesizer               import synthesizer
from src.hr_agent.nodes.final_review              import final_review
from src.hr_agent.nodes.github_scorer             import github_scorer
from src.hr_agent.nodes.decision_engine           import decision_engine, route_hitl_outcome
from src.hr_agent.nodes.hitl_node                 import hitl_node
from src.hr_agent.nodes.email_nodes               import send_acceptance_email, send_rejection_email


def build_graph():
    builder = StateGraph(GraphState)
 
    # ── Nodes ─────────────────────────────────────────────────
    builder.add_node("resume_extractor",      resume_extractor)
    builder.add_node("resume_scorer",         resume_scorer)
    builder.add_node("profile_extractor",     profile_extractor)
    builder.add_node("python_worker",         python_worker)
    builder.add_node("readme_worker",         readme_worker)
    builder.add_node("infra_worker",          infra_worker)
    builder.add_node("config_worker",         config_worker)
    builder.add_node("notebook_worker",       notebook_worker)
    builder.add_node("synthesizer",           synthesizer)
    builder.add_node("final_review",          final_review)
    builder.add_node("github_scorer",         github_scorer)
    builder.add_node("decision_engine",       decision_engine)
    builder.add_node("hitl_node",             hitl_node)
    builder.add_node("send_acceptance_email", send_acceptance_email)
    builder.add_node("send_rejection_email",  send_rejection_email)
 
    # ── Entry ──────────────────────────────────────────────────
    builder.add_edge(START, "resume_extractor")
    builder.add_edge("resume_extractor", "resume_scorer")
 
    # ── Branch after resume_scorer ────────────────────────────
    # Path 1: has github_url → full GitHub analysis pipeline
    # Path 2: no github_url  → skip straight to decision_engine
    def route_after_resume_scorer(state):
        return "profile_extractor" if state.get("github_url") else "decision_engine"
 
    builder.add_conditional_edges(
        "resume_scorer", route_after_resume_scorer,
        {
            "profile_extractor": "profile_extractor",
            "decision_engine":   "decision_engine",
        }
    )
    def route_after_profile_extractor(state):
        if not state.get("analyzed_repos"):
            return ["decision_engine"]
        return dispatch_workers(state)
 
    builder.add_conditional_edges(
        "profile_extractor",
        route_after_profile_extractor,
        [
            "python_worker",
            "readme_worker",
            "infra_worker",
            "config_worker",
            "notebook_worker",
            "synthesizer",
            "decision_engine",
        ],
    )
    # ── Parallel worker dispatch ───────────────────────────────
    builder.add_conditional_edges(
        "profile_extractor",
        dispatch_workers,
        [
            "python_worker",
            "readme_worker",
            "infra_worker",
            "config_worker",
            "notebook_worker",
            "synthesizer",    # fallback if no files found
        ],
    )
    builder.add_edge("python_worker",   "synthesizer")
    builder.add_edge("readme_worker",   "synthesizer")
    builder.add_edge("infra_worker",    "synthesizer")
    builder.add_edge("config_worker",   "synthesizer")
    builder.add_edge("notebook_worker", "synthesizer")
 
    # ── GitHub scoring pipeline ────────────────────────────────
    builder.add_edge("synthesizer",   "final_review")
    builder.add_edge("final_review",  "github_scorer")
    builder.add_edge("github_scorer", "decision_engine")
 
    # ── Decision routing ──────────────────────────────────────
    builder.add_conditional_edges(
        "decision_engine",
        lambda s: s["decision"],
        {
            "auto_select": "send_acceptance_email",
            "hitl":        "hitl_node",
        },
    )
 
    # ── HITL outcome routing ──────────────────────────────────
    builder.add_conditional_edges(
        "hitl_node",
        route_hitl_outcome,
        {
            "approved": "send_acceptance_email",
            "rejected": "send_rejection_email",
        },
    )
 
    # ── Terminal edges ────────────────────────────────────────
    builder.add_edge("send_acceptance_email", END)
    builder.add_edge("send_rejection_email",  END)
 
    return builder.compile()
 
 
# single shared graph instance imported by main.py and streamlit_app.py
graph = build_graph()