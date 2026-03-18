from src.hr_agent.core.state import GraphState
from src.hr_agent.config.settings import SCORE_THRESHOLD
from src.hr_agent.tools.logger import get_logger,NodeTimer


def decision_engine(state: GraphState) -> dict:
    print("--- DECISION ENGINE ---")

    candidate    = state.get("candidate_name", "")
    resume_score = state.get("resume_score", 0.0)
    github_score = state.get("github_score", 0.0)
    github_url   = state.get("github_url",   "")
    role         = state.get("applied_role", state.get("current_role", "the position"))
    log          = get_logger("decision_engine")

    with NodeTimer("decision_engine", candidate=candidate):
        not_a_resume = state.get("not_a_resume", False)
        decision     = _route(resume_score, github_score, github_url, not_a_resume)
        hitl_reason = _build_hitl_reason(resume_score, github_score, github_url) if decision == "hitl" else ""
        hitl_packet = _build_hitl_packet(state, hitl_reason) if decision == "hitl" else None
        next_steps = ""
        if decision == "auto_select":
            next_steps = (
                f"Congratulations! We are pleased to invite you to the next stage "
                f"of the interview process for the {role} position. "
                f"Our team will be in touch within 2 business days to schedule "
                f"a technical interview."
            )
 
        rejection_reason = ""
        if decision == "hard_reject":
            rejection_reason = (
                f"Thank you for your application for the {role} position. "
                f"Unfortunately, the document you submitted does not appear to be a resume. "
                f"Please resubmit with a valid CV or resume."
            )
            # treat hard_reject as rejected for email routing
            decision = "rejected"
 
        print(f"  Decision: {decision.upper()} "
              f"(Resume: {resume_score}, GitHub: {github_score})")
 
        log.info("decision_made",
            candidate=candidate,
            decision=decision.upper(),
            resume_score=resume_score,
            github_score=github_score,
            threshold=SCORE_THRESHOLD,
            hitl_reason=hitl_reason if decision == "hitl" else None,
        )
 
        return {
            "decision":         decision,
            "hitl_reason":      hitl_reason,
            "hitl_packet":      hitl_packet,
            "next_steps":       next_steps,
            "rejection_reason": rejection_reason,
        }
 
def _route(resume_score, github_score, github_url, not_a_resume=False) -> str:
    if not_a_resume:                                                             return "hard_reject"
    if not github_url:                                                       return "hitl"
    if github_score == 0.0 and github_url:                                  return "hitl"
    if resume_score >= SCORE_THRESHOLD and github_score >= SCORE_THRESHOLD: return "auto_select"
    return "hitl"


def _build_hitl_reason(resume_score, github_score, github_url) -> str:
    if not github_url:
        return (f"No GitHub URL found in resume. Resume: {resume_score}/100. "
                f"Please request GitHub profile from candidate.")
    if github_score == 0.0 and github_url:
        return (f"GitHub URL provided but profile could not be analyzed "
                f"(no public repos or invalid URL). Resume: {resume_score}/100.")
    if resume_score < SCORE_THRESHOLD and github_score >= SCORE_THRESHOLD:
        return (f"GitHub ({github_score}/100) is strong but resume ({resume_score}/100) "
                f"is below threshold ({SCORE_THRESHOLD}). "
                f"GitHub suggests strong capability — worth reviewing resume carefully.")
    if resume_score >= SCORE_THRESHOLD and github_score < SCORE_THRESHOLD:
        return (f"Resume ({resume_score}/100) is strong but GitHub ({github_score}/100) "
                f"is below threshold ({SCORE_THRESHOLD}). "
                f"Please verify claimed skills against GitHub evidence.")
    # both below threshold
    return (f"Scores below threshold. "
            f"Resume: {resume_score}/100 | GitHub: {github_score}/100 | "
            f"Threshold: {SCORE_THRESHOLD}/100.")


def _build_hitl_packet(state: GraphState, hitl_reason: str) -> dict:
    warnings = []
    if not state.get("github_url"):
        warnings.append("⚠️ NO GITHUB: No GitHub profile available.")

    return {
        "candidate_name":  state.get("candidate_name",  "N/A"),
        "candidate_email": state.get("candidate_email", "N/A"),
        "applied_role":    state.get("applied_role",    "N/A"),
        "current_role":    state.get("current_role",    "N/A"),
        "github_url":      state.get("github_url",      "N/A"),
        "linkedin_url":    state.get("linkedin_url",    "N/A"),
        "resume_score":    state.get("resume_score",    0.0),
        "github_score":    state.get("github_score",    0.0),
        "score_threshold": SCORE_THRESHOLD,
        "resume_analysis": state.get("resume_analysis", ""),
        "github_analysis": state.get("github_analysis", ""),
        "final_profile":   state.get("final_profile",   ""),
        "analyzed_repos":  state.get("analyzed_repos",  []),
        "review_reason":   hitl_reason,
        "warnings":        warnings,
        "hr_actions":      ["approve", "reject", "request_more_info"],
        "instructions": (
            "Review the candidate profile and analysis below. "
            "Respond with: approve, reject, or request_more_info."
        ),
    }


def route_hitl_outcome(state: GraphState) -> str:
    decision = state.get("decision", "rejected")
    return "approved" if decision == "approved" else "rejected"