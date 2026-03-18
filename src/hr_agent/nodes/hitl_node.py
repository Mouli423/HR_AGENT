# import json
# import re
# from langgraph.types import interrupt
# from src.hr_agent.core.state import GraphState


# def hitl_node(state: GraphState) -> dict:
#     print("--- HITL: Awaiting HR Decision ---")

#     packet = state.get("hitl_packet", {})
#     _print_hr_packet(packet)

#     human_response = interrupt({
#         "type":          "hr_review",
#         "review_packet": packet,
#         "instructions": (
#             'Provide your decision as: '
#             '{"outcome": "approved" | "rejected" | "request_more_info", '
#             '"reason": "your notes here"}'
#         ),
#     })

#     outcome, reason = _parse_hr_response(human_response)

#     print(f"--- HR DECISION: {outcome.upper()} ---")
#     print(f"    Reason: {reason}")

#     role = state.get("applied_role", state.get("current_role", "the position"))

#     if outcome == "approved":
#         return {
#             "hitl_outcome":     "approved",
#             "hitl_reason":      reason,
#             "decision":         "approved",
#             "next_steps": (
#                 f"Congratulations! Following a thorough review of your profile, "
#                 f"we are pleased to invite you to the next stage of the interview "
#                 f"process for the {role} position. "
#                 f"Our team will be in touch within 2 business days.\n\n"
#                 f"Reviewer note: {reason}"
#             ),
#             "rejection_reason": "",
#         }

#     elif outcome == "request_more_info":
#         return {
#             "hitl_outcome":     "rejected",
#             "hitl_reason":      reason,
#             "decision":         "request_more_info",
#             "next_steps":       "",
#             "rejection_reason": (
#                 f"Thank you for your interest in the {role} position. "
#                 f"After reviewing your application, we would like to request "
#                 f"some additional information before proceeding.\n\n"
#                 f"{reason}\n\n"
#                 f"Please reply to this email with the requested information."
#             ),
#         }

#     else:  # rejected
#         return {
#             "hitl_outcome":     "rejected",
#             "hitl_reason":      reason,
#             "decision":         "rejected",
#             "next_steps":       "",
#             "rejection_reason": (
#                 f"Thank you for your interest in the {role} position. "
#                 f"After a careful review of your application and profile, "
#                 f"we regret to inform you that we will not be moving forward "
#                 f"with your application at this time.\n\n"
#                 f"We appreciate the time you invested in applying and wish you "
#                 f"the very best in your search."
#             ),
#         }


# def _print_hr_packet(packet: dict):
#     print("\n" + "=" * 60)
#     print("HR REVIEW PACKET")
#     print("=" * 60)
#     print(f"Candidate     : {packet.get('candidate_name')}")
#     print(f"Role          : {packet.get('applied_role')}")
#     print(f"Current Role  : {packet.get('current_role')}")
#     print(f"Resume Score  : {packet.get('resume_score')}/100")
#     print(f"GitHub Score  : {packet.get('github_score')}/100")
#     print(f"GitHub URL    : {packet.get('github_url')}")
#     if packet.get("warnings"):
#         print("\nWarnings:")
#         for w in packet["warnings"]:
#             print(f"  {w}")
#     print(f"\nReason for review: {packet.get('review_reason')}")
#     print("=" * 60)
#     print("\nResume Analysis:")
#     analysis = packet.get("resume_analysis", "N/A")
#     print(analysis[:600] + ("..." if len(analysis) > 600 else ""))
#     print("\nGitHub Analysis:")
#     github = packet.get("github_analysis", "N/A")
#     print(github[:600] + ("..." if len(github) > 600 else ""))
#     print("=" * 60 + "\n")


# def _parse_hr_response(human_response) -> tuple:
#     try:
#         if isinstance(human_response, dict):
#             return (
#                 human_response.get("outcome", "rejected"),
#                 human_response.get("reason",  "Decision made by HR team."),
#             )
#         if isinstance(human_response, str):
#             cleaned = re.sub(r"```json|```", "", human_response).strip()
#             match   = re.search(r"\{.*\}", cleaned, re.DOTALL)
#             if match:
#                 data = json.loads(match.group(0))
#                 return (
#                     data.get("outcome", "rejected"),
#                     data.get("reason",  "Decision made by HR team."),
#                 )
#             text = human_response.lower().strip()
#             if "approve"   in text: return "approved",          human_response
#             if "more info" in text: return "request_more_info", human_response
#             return "rejected", human_response
#     except Exception:
#         pass
#     return "rejected", str(human_response)


import time
from src.hr_agent.tools.logger import get_logger,NodeTimer
from src.hr_agent.core.state import GraphState

VALID_OUTCOMES = {
    "1": "approved",
    "2": "rejected",
    "3": "request_more_info",
}


def hitl_node(state: GraphState) -> dict:
    print("--- HITL: Awaiting HR Decision ---")

    candidate = state.get("candidate_name", "")
    packet    = state.get("hitl_packet", {})
    log       = get_logger("hitl_node")
 
    _print_hr_packet(packet)

    hitl_start       = time.time()
    outcome, reason  = _collect_hr_input()
    review_duration  = int((time.time() - hitl_start) * 1000)
 
    print(f"\n--- HR DECISION: {outcome.upper()} ---")
    print(f"    Reason: {reason}")
 
    log.info("hr_decision",
        candidate=candidate,
        outcome=outcome,
        reason=reason,
        review_duration_ms=review_duration,
        resume_score=packet.get("resume_score"),
        github_score=packet.get("github_score"),
    )

    role = state.get("applied_role", state.get("current_role", "the position"))

    if outcome == "approved":
        return {
            "hitl_outcome":     "approved",
            "hitl_reason":      reason,
            "decision":         "approved",
            "next_steps": (
                f"Congratulations! Following a thorough review of your profile, "
                f"we are pleased to invite you to the next stage of the interview "
                f"process for the {role} position. "
                f"Our team will be in touch within 2 business days.\n\n"
                f"Reviewer note: {reason}"
            ),
            "rejection_reason": "",
        }

    elif outcome == "request_more_info":
        return {
            "hitl_outcome":     "rejected",
            "hitl_reason":      reason,
            "decision":         "request_more_info",
            "next_steps":       "",
            "rejection_reason": (
                f"Thank you for your interest in the {role} position. "
                f"After reviewing your application, we would like to request "
                f"some additional information before proceeding.\n\n"
                f"{reason}\n\n"
                f"Please reply to this email with the requested information."
            ),
        }

    else:  # rejected
        return {
            "hitl_outcome":     "rejected",
            "hitl_reason":      reason,
            "decision":         "rejected",
            "next_steps":       "",
            "rejection_reason": (
                f"Thank you for your interest in the {role} position. "
                f"After a careful review of your application and profile, "
                f"we regret to inform you that we will not be moving forward "
                f"with your application at this time.\n\n"
                f"We appreciate the time you invested in applying and wish you "
                f"the very best in your search."
            ),
        }


def _collect_hr_input() -> tuple:
    """Interactively prompts HR for a decision and reason via CMD."""
    print("\n" + "=" * 60)
    print("HR ACTION REQUIRED")
    print("=" * 60)
    print("  1. Approve")
    print("  2. Reject")
    print("  3. Request More Info")
    print("=" * 60)

    # Decision
    while True:
        choice = input("\nEnter your decision (1 / 2 / 3): ").strip()
        if choice in VALID_OUTCOMES:
            outcome = VALID_OUTCOMES[choice]
            break
        print("  Invalid input. Please enter 1, 2, or 3.")

    # Reason
    while True:
        reason = input("Enter your reason / notes: ").strip()
        if reason:
            break
        print("  Reason cannot be empty. Please enter your notes.")

    return outcome, reason


def _print_hr_packet(packet: dict):
    print("\n" + "=" * 60)
    print("HR REVIEW PACKET")
    print("=" * 60)
    print(f"Candidate     : {packet.get('candidate_name')}")
    print(f"Role          : {packet.get('applied_role')}")
    print(f"Current Role  : {packet.get('current_role')}")
    print(f"Resume Score  : {packet.get('resume_score')}/100")
    print(f"GitHub Score  : {packet.get('github_score')}/100")
    print(f"GitHub URL    : {packet.get('github_url')}")
    if packet.get("warnings"):
        print("\nWarnings:")
        for w in packet["warnings"]:
            print(f"  {w}")
    print(f"\nReason for review: {packet.get('review_reason')}")
    print("=" * 60)
    print("\nResume Analysis:")
    analysis = packet.get("resume_analysis", "N/A")
    print(analysis[:600] + ("..." if len(analysis) > 600 else ""))
    print("\nGitHub Analysis:")
    github = packet.get("github_analysis", "N/A")
    print(github[:600] + ("..." if len(github) > 600 else ""))
    print("=" * 60)