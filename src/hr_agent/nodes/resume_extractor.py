from src.hr_agent.core.state import GraphState
from src.hr_agent.core.llm import extractor_llm, llm , extractor_llm_fb
from src.hr_agent.core.models import ResumeExtractorOutput
from src.hr_agent.tools.resume_parser import parse_resume
from src.hr_agent.tools.llm_utils import invoke_with_fallback
from src.hr_agent.tools.logger import get_logger, NodeTimer

 
def resume_extractor(state: GraphState) -> dict:

    print("--- RESUME EXTRACTOR ---")

    log  = get_logger("resume_extractor")

    path = state.get("resume_path", "")
    if not path:
        log.warning("no_resume_path")
        return {
            "resume_text":     "",
            "github_url":      state.get("github_url"),
            "linkedin_url":    state.get("linkedin_url"),
            "candidate_email": state.get("candidate_email"),
            "candidate_name":  state.get("candidate_name"),
            "current_role":    state.get("current_role", ""),
        }

    data = parse_resume(path)

    prompt_text = f"""Extract the following fields from this resume.

    Rules:
    - candidate_name: copy the name EXACTLY as written on the resume. Do NOT paraphrase,
    add commentary, or include any other text. If uncertain, use the first name-like
    string found at the top of the resume. Output only the name itself.
    - github_url / linkedin_url: look for both hyperlinks and plain text URLs.
    - role_title: infer from their most recent job title or career objective.

    Resume text:
    {data["text"][:2000]}   
    """
    with NodeTimer("resume_extractor") as timer:
        try:
            extracted: ResumeExtractorOutput = invoke_with_fallback(extractor_llm, extractor_llm_fb, prompt_text)
            if extracted is None:
                raise ValueError("Structured output returned None")

            # prefer regex-extracted URLs (more reliable) over LLM-extracted
            github_url   = data.get("github_url")   or extracted.github_url   or state.get("github_url")
            linkedin_url = data.get("linkedin_url") or extracted.linkedin_url or state.get("linkedin_url")
            email        = data.get("email")        or extracted.candidate_email or state.get("candidate_email", "")

            # fix all-caps names + strip any LLM commentary the model may have added
            raw_name = extracted.candidate_name or state.get("candidate_name", "")
            # keep only the first line, strip anything after ? or ( or "actually" etc.
            raw_name = raw_name.split("\n")[0].split("?")[0].split("(")[0].strip()
            name = raw_name.title()

            timer.set_extra(candidate=name, role=extracted.role_title)
            log.info("extraction_success",
                candidate=name,
                role=extracted.role_title,
                has_github=bool(github_url),
                has_linkedin=bool(linkedin_url),
            )

            return {
                "resume_text":     data["text"],
                "github_url":      github_url,
                "linkedin_url":    linkedin_url,
                "candidate_email": email,
                "candidate_name":  name,
                "current_role":    extracted.role_title or state.get("current_role", ""),
            }

        except Exception as e:
            print(f"  [resume_extractor structured output failed: {e}]")
            return {
                "resume_text":     data["text"],
                "github_url":      data.get("github_url")   or state.get("github_url"),
                "linkedin_url":    data.get("linkedin_url") or state.get("linkedin_url"),
                "candidate_email": data.get("email")        or state.get("candidate_email", ""),
                "candidate_name":  state.get("candidate_name", ""),
                "current_role":    state.get("current_role", ""),
            }