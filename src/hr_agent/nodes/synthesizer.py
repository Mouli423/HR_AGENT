from src.hr_agent.core.state import GraphState
from src.hr_agent.core.llm import synthesizer_llm, llm , synthesizer_llm_fb
from src.hr_agent.core.models import SynthesizerOutput
from src.hr_agent.tools.helpers import _extract_text
from src.hr_agent.tools.llm_utils import invoke_with_fallback
from src.hr_agent.tools.logger import get_logger, NodeTimer


SYNTHESIZER_PROMPT = """
You are a Technical Synthesis Agent.

You will receive structured outputs from specialized worker agents that analyzed
a candidate's GitHub repositories. Each worker focused on a different signal type:
python code, documentation, infrastructure, configuration, and notebooks.

Your task is to synthesize these into a single coherent technical profile.

Instructions:
- Combine all stack and library lists into one consolidated technology list
- Identify recurring patterns across multiple workers — these are stronger signals
- Reference actual repository names from the ANALYZED REPOSITORIES list
- Highlight strengths only if supported by evidence from multiple workers
- Identify gaps only if consistently observed across workers
- Do NOT introduce tools or claims not found in the worker outputs
- Do NOT rate the candidate or assign seniority labels
- Be concise — the output feeds directly into a scoring engine
"""


def _format_worker_outputs(summaries: dict) -> str:
    """Formats structured worker dicts into a clean readable prompt section."""
    sections = []
    for worker_key, output in summaries.items():
        if isinstance(output, dict):
            # structured output — format each field cleanly
            lines = [f"### {worker_key.upper().replace('_', ' ')}"]
            for field, value in output.items():
                if isinstance(value, list):
                    lines.append(f"{field}: {', '.join(value) if value else 'none'}")
                elif isinstance(value, str) and value.strip():
                    lines.append(f"{field}: {value.strip()}")
            sections.append("\n".join(lines))
        else:
            # fallback plain text from older runs
            sections.append(f"### {worker_key.upper()}\n{str(output)[:500]}")
    return "\n\n".join(sections)


def synthesizer(state: GraphState) -> dict:
    print("---SYNTHESIZER---")

    candidate   = state.get("candidate_name", "")
    summaries   = state.get("summaries", {})
    worker_text = _format_worker_outputs(summaries)
    repo_list   = "\n".join(f"  - {r}" for r in state.get("analyzed_repos", []))
    log         = get_logger("synthesizer")
 
    prompt_text = f"""{SYNTHESIZER_PROMPT}

    ANALYZED REPOSITORIES:
    {repo_list}

    WORKER OUTPUTS:
    {worker_text}
    """
    with NodeTimer("synthesizer", candidate=candidate) as timer:
        try:
            data: SynthesizerOutput = invoke_with_fallback(synthesizer_llm, synthesizer_llm_fb, prompt_text)
            if data is None:
                raise ValueError("Structured output returned None")

            final_profile = (
                f"TECHNICAL STACK:\n{data.technical_stack}\n\n"
                f"PROJECT HIGHLIGHTS:\n{data.project_highlights}\n\n"
                f"ENGINEERING PRACTICES:\n{data.engineering_practices}\n\n"
                f"STRENGTHS:\n{data.strengths}\n\n"
                f"CONCERNS:\n{data.concerns}\n\n"
                f"OVERALL PROFILE:\n{data.overall_profile}"
            )
            log.info("synthesis_complete", candidate=candidate)
            return {"final_profile": final_profile}

        except Exception as e:
            print(f"  [synthesizer failed: ATTEMPTING RECOVERY]")
            log.error("synthesizer_failed ATTEMPTING RECOVERY",
                candidate=candidate
            )
            try:
                response = llm.invoke(prompt_text)
                log.info("synthesis_complete", candidate=candidate)
                timer.set_extra(recovered=True)
                return {"final_profile": _extract_text(response)}
            
            except Exception as e:
                log.error("synthesizer_recovery_failed",
                    candidate=candidate,
                    error_type=e.__class__.__name__,
                    error=str(e)[:300],
                )
                timer.set_extra(recovered=False)

            