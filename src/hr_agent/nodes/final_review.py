from src.hr_agent.core.state import GraphState
from src.hr_agent.core.llm import final_review_llm, llm , final_review_llm_fb
from src.hr_agent.core.models import FinalReviewOutput
from src.hr_agent.tools.helpers import _extract_text
from src.hr_agent.tools.llm_utils import invoke_with_fallback
from src.hr_agent.tools.logger import get_logger,NodeTimer
FINAL_REVIEW_PROMPT = """
You are a Final Technical Review Agent.

You will receive a synthesized technical profile of a software engineer
based on analysis of their GitHub repositories, and the Job Description
they applied for.

Your task is to produce a clear, professional technical assessment.

Instructions:
- Preserve technical accuracy
- Avoid exaggeration or speculation
- Use neutral, professional language
- Avoid generic praise
- Present observations as evidence-based statements
- Reference actual repository names when citing evidence
"""


def final_review(state: GraphState) -> dict:
    print("---FINAL_REVIEW---")
    
    candidate   = state.get("candidate_name", "")
    log         = get_logger("final_review")

    prompt_text = f"""{FINAL_REVIEW_PROMPT}

    Job Description:
    {state.get("job_description", "")}

    GitHub Technical Profile:
    {state.get("final_profile", "")}
    """ 
    with NodeTimer("final_review", candidate=candidate) as timer:
        try:
            data: FinalReviewOutput = invoke_with_fallback(final_review_llm, final_review_llm_fb, prompt_text)
            if data is None:
                raise ValueError("Structured output returned None")

            final_summary = (
                f"CANDIDATE SUMMARY:\n{data.candidate_summary}\n\n"
                f"ROLE FIT ASSESSMENT:\n{data.role_fit_assessment}\n\n"
                f"KEY EVIDENCE:\n{data.key_evidence}\n\n"
                f"RECOMMENDATION:\n{data.recommendation}"
            )
            
            log.info("final_review_complete", candidate=candidate)
            return {"final_summary": final_summary}

        except Exception as e:
            print(f"  [final review failed: ATTEMPTING RECOVERY]")
            log.error("final review ATTEMPTING RECOVERY",
                candidate=candidate
            )
            try:
                response = llm.invoke(prompt_text)
                log.info("final review completed", candidate=candidate)
                timer.set_extra(recovered=True)
                return {"final_summary": _extract_text(response)}
            
            except Exception as e:
                log.error("final review recovered",
                    candidate=candidate,
                    error_type=e.__class__.__name__,
                    error=str(e)[:300],
                )
                timer.set_extra(recovered=False)