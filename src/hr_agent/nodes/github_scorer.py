from src.hr_agent.core.state import GraphState
from src.hr_agent.core.llm import github_llm, llm , github_llm_fb
from src.hr_agent.core.models import GitHubScoreOutput
from src.hr_agent.tools.helpers import _extract_text, _extract_score
from src.hr_agent.tools.llm_utils import invoke_with_fallback
from src.hr_agent.tools.logger import get_logger, NodeTimer
 

GITHUB_SCORER_PROMPT = """
You are an expert Technical Recruiter specializing in GitHub profile evaluation.

You will receive a Job Description and a structured GitHub technical profile
synthesized from the candidate's repositories.

── STEP 1: Detect seniority from the JD ──────────────────────
- JUNIOR   : demos expected, not penalized; evaluate tech stack and learning trajectory
- MID      : mix of learning + some production signals expected
- SENIOR   : production evidence, system design, architecture ownership required
- FOUNDING : all of senior + business judgment, team leadership signals

── STEP 2: Score using the rubric below RELATIVE to detected seniority ──

The rubric uses compressed bands at the bottom (precision not needed for
clear rejects) and fine-grained bands near and above the threshold (70),
where the auto-select vs HITL decision is made.

Score | Band        | Criteria
------|-------------|----------------------------------------------------------
 0-39 | Poor        | No meaningful GitHub presence, completely irrelevant
      |             | projects, or entirely forked/copied repos with no
      |             | original contributions
40-54 | Weak        | Some activity but projects are shallow demos, stale,
      |             | or show minimal technical investment in relevant areas
55-64 | Moderate    | Some relevant projects with real code but limited depth.
      |             | Tech stack partially aligns with JD requirements
65-72 | Borderline  | Close to threshold. Relevant projects present with genuine
      |             | effort but missing production signals or depth for the role
73-84 | Strong      | Relevant projects show genuine technical investment.
      |             | Good stack alignment with the JD. Original work evident
85-92 | Very Strong | Strong, original, relevant projects with real depth.
      |             | Clear evidence of capability for the target role
93-100| Exceptional | Rare. Outstanding portfolio — production-grade projects,
      |             | strong originality, directly aligned with JD requirements

── STEP 3: Additional evaluation signals ─────────────────────
Penalize for:
- Forked repos with no original contributions 
- Profile with no commits in last 12 months 
- Resume claims not evidenced in GitHub (reduce by 5-10 points)

Boost for:
- Original projects not just tutorials or course work
- Evidence of end-to-end thinking (not just model calls)
- Agentic patterns, eval frameworks, production deployment signals

── STEP 4: Scoring rules to reduce variance ──────────────────
- Assign a SINGLE integer score. Do not hedge with ranges.
- Junior JD: do NOT penalize for absence of production-grade code
- Senior JD: prototype-only profile caps at 64 regardless of tech stack
- Strong tech stack with no original work: score 55-64, not higher
- Only reference projects from the ANALYZED REPOSITORIES list
- Do NOT invent or guess project names not in that list

── STEP 5: Fill score_rationale BEFORE score ─────────────────
Before writing the score integer, fill score_rationale with:
  "<band name> (<range>): <single most important reason>"
Example: "Borderline (65-72): Multiple original LangGraph projects with
  Docker/CI but no production deployment or secret management"

The score integer MUST fall within the range stated in score_rationale.
This ensures your reasoning and score are always consistent.

Respond with valid JSON only. No explanation, no markdown, no code blocks.
"""


def github_scorer(state: GraphState) -> dict:
    print("--- GITHUB SCORER ---")

    candidate = state.get("candidate_name", "")
    profile   = state.get("final_profile", "")
    log       = get_logger("github_scorer")
 
    if not profile or len(profile.strip()) < 50:
        log.warning("no_github_profile", candidate=candidate)
        return {
            "github_score":    0.0,
            "github_analysis": "GitHub profile could not be analyzed.",
        }
 
    repo_list = "\n".join(f"  - {r}" for r in state.get("analyzed_repos", []))

    prompt_text = f"""{GITHUB_SCORER_PROMPT}

    ANALYZED REPOSITORIES (only reference these):
    {repo_list}

    Job Description:
    {state.get("job_description", "")}

    Candidate GitHub Technical Profile:
    {profile}
    """
    with NodeTimer("github_scorer", candidate=candidate) as timer:
        try:
            data: GitHubScoreOutput = invoke_with_fallback(github_llm, github_llm_fb, prompt_text)
            if data is None:
                raise ValueError("Structured output returned None")

            analysis = (
                f"Detected Seniority : {data.detected_seniority}\n"
                f"Score              : {data.score}/100\n"
                f"Score Rationale    : {data.score_rationale}\n"
                f"Originality Signal : {data.originality_signal}\n\n"
                f"Relevant Projects  :\n"
                + "\n".join(f"  • {p}" for p in data.relevant_projects)
                + f"\n\nSummary: {data.summary}"
            )

            timer.set_extra(score=data.score, band=data.score_rationale.split(":")[0])
            log.info("github_scored",
                candidate=candidate,
                score=data.score,
                seniority=data.detected_seniority,
                originality=data.originality_signal,
                rationale=data.score_rationale,
            )
            return {
                "github_score":       float(data.score),
                "github_analysis":    analysis
            }

        except Exception as e:
            print(f"  [github_scorer failed] : ATTEMPTING RECOVERY")
            log.error("github_scorer_failed : ATTEMPTING RECOVERY",
                candidate=candidate
            )
            try:
                response = llm.invoke(prompt_text)
                raw_text = _extract_text(response)
                score    = _extract_score(raw_text)
                log.info("github_Scorer completed", candidate=candidate)
                timer.set_extra(recovered=True)
                return {
                    "github_score":       score,
                    "github_analysis":    raw_text

                }

            except Exception as e:
                log.error("github_scorer_recovery_failed",
                    candidate=candidate,
                    error_type=e.__class__.__name__,
                    error=str(e)[:300],
                )
                timer.set_extra(recovered=False)