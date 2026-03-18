from typing import TypedDict, List, Optional, Literal, Annotated


def merge_summaries(existing: dict, new: list) -> dict:
    """Reducer — merges parallel worker summaries into one dict."""
    result = dict(existing or {})
    for item in (new or []):
        if isinstance(item, dict):
            result.update(item)
    return result


class GraphState(TypedDict):
    # ── Inputs ────────────────────────────────────────────────
    job_description: str
    resume_path:     str
    applied_role:    str          # role they applied for (passed in invoke)

    # ── Resume extraction ─────────────────────────────────────
    resume_text:      str
    candidate_name:   str
    candidate_email:  str
    current_role:     str         # extracted from resume
    github_url:       Optional[str]
    linkedin_url:     Optional[str]

    # ── Resume scoring ────────────────────────────────────────
    resume_score:    float
    resume_analysis: str
    not_a_resume:    bool

    # ── GitHub traversal ──────────────────────────────────────
    routed_files:   List[str]
    analyzed_repos: List[str]
    summaries:      Annotated[dict, merge_summaries]
    next_action:    str
    final_summary:  str
    final_profile:  str

    # ── Security ──────────────────────────────────────────────
    security_red_flags: List[dict]

    # ── GitHub scoring ────────────────────────────────────────
    github_score:    float
    github_analysis: str

    # ── Decision ──────────────────────────────────────────────
    decision:         Literal[
        "auto_select", "hitl", "no_github",
        "approved", "rejected", "request_more_info"
    ]
    hitl_outcome:     Optional[Literal["approved", "rejected"]]
    hitl_reason:      Optional[str]
    hitl_packet:      Optional[dict]
    rejection_reason: str
    next_steps:       str
    email_sent:       bool