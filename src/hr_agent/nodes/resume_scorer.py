from src.hr_agent.core.state import GraphState
from src.hr_agent.core.llm import resume_llm, llm ,resume_llm_fb
from src.hr_agent.core.models import ResumeScoreOutput
from src.hr_agent.tools.helpers import _extract_text, _extract_score
from src.hr_agent.tools.llm_utils import invoke_with_fallback
from src.hr_agent.tools.logger import get_logger, NodeTimer, pipeline_stats

RESUME_SCORER_PROMPT = """
You are an expert Technical Recruiter and Resume Evaluator.
 
── STEP 0: Verify this is a resume ───────────────────────────
Before scoring, check if the uploaded document is actually a resume/CV.
A resume must contain at least some of: candidate name, contact info,
education, work experience, skills, or projects.
 
If the document is NOT a resume (e.g. it is a research paper, invoice,
legal document, image description, random text, or any non-resume content):
- Set not_a_resume: true
- Set score: 0
- Set score_rationale: "Not a resume: <brief description of what the document actually is>"
- Set summary: a brief explanation of why this is not a resume
- Leave all other fields empty
- STOP — do not attempt to score it
 
If it IS a resume, set not_a_resume: false and continue to STEP 1.
 
── STEP 1: Detect seniority from the JD ──────────────────────
Read the JD carefully and classify into ONE of:
- JUNIOR   (0-2 yrs): demos and projects acceptable, learning trajectory matters
- MID      (2-4 yrs): mix of learning + some production signals expected
- SENIOR   (4+ yrs) : production evidence, system design, architecture ownership required
- FOUNDING           : all of senior + business judgment, hiring, vision
 
── STEP 2: Score using the rubric below RELATIVE to detected seniority ──
 
The rubric uses compressed bands at the bottom (precision is not needed for
clear rejects) and fine-grained bands near and above the threshold (70),
where the auto-select vs HITL decision is made.
 
Score | Band        | Criteria
------|-------------|----------------------------------------------------------
 0-39 | Poor        | Fundamentally misaligned — wrong domain, fabricated profile,
      |             | or no relevant skills whatsoever
40-54 | Weak        | Some overlap but significant gaps in core required skills.
      |             | Surface-level mentions without depth or evidence
55-64 | Moderate    | Partial fit — has some required skills with real evidence
      |             | but missing several key requirements
65-72 | Borderline  | Close to threshold. Most core skills present but 1-2
      |             | notable gaps or seniority mismatch. Needs HITL review
73-84 | Strong      | Meets most requirements with genuine evidence of experience.
      |             | Minor gaps only in non-critical areas
85-89 | Very Strong | Exceeds most requirements. Covers ALL required skills with
      |             | real evidence PLUS several nice-to-have skills. Use 85
      |             | unless there is clear evidence for a higher score.
90-95 | Exceptional | ALL required skills covered with strong evidence AND most
      |             | nice-to-have skills present AND clear production/deployment
      |             | experience. Must justify every point above 90 explicitly.
96-100| Rare        | Reserved for a near-perfect match — every required and
      |             | nice-to-have skill covered with deep, verifiable evidence.
 
── STEP 3: Scoring rules to reduce variance ──────────────────
- Assign a SINGLE integer score. Do not hedge with ranges.
- Junior candidate for senior JD (under-experienced): cap score at 64 regardless
  of tech stack — production ownership and mentorship signals are required
- Senior candidate for junior JD (overqualified): do NOT penalize — score purely
  on skill and domain alignment, seniority_alignment should reflect "mismatch"
  but the score itself should not be capped
- Strong domain alignment with missing tools: score 55-72, not below
- Weak domain alignment with strong tools: score 40-54
- Missing ALL production evidence for a senior JD: score 40-54 maximum
- Do NOT penalize for missing nice-to-have skills when core skills are present
- Default entry point for Very Strong band is 85 — only go higher if you can
  name a specific piece of evidence that justifies each additional point
- Scores 86-89: ALL required skills present with real evidence
- Scores 90-92: ALL required skills + at least 4 nice-to-have skills confirmed
- Scores 93-95: ALL required skills + ALL nice-to-have skills confirmed with evidence
- Scores 96-100: reserved for perfect matches only — do not use unless every
  single required and nice-to-have skill has deep verifiable evidence
- When in doubt between two scores, always pick the LOWER one
 
── STEP 4: Fill score_rationale BEFORE score ─────────────────
Before writing the score integer, fill score_rationale with:
  "<band name> (<range>): <single most important reason>"
Example: "Borderline (65-72): Strong RAG and LangGraph experience but
  missing production ownership required for senior role"
 
The score integer MUST fall within the range stated in score_rationale.
This ensures your reasoning and score are always consistent.
 
Respond with valid JSON only. No explanation, no markdown, no code blocks.
"""
 
def resume_scorer(state: GraphState) -> dict:
    print("--- RESUME SCORER ---")

    candidate   = state.get("candidate_name", "")
    resume_text = state.get("resume_text", "")
    jd          = state.get("job_description", "")
    log         = get_logger("resume_scorer")
 
    if not resume_text:
        log.warning("no_resume_text", candidate=candidate)
        return {"resume_score": 0.0, "resume_analysis": "No resume text available."}
    if not jd:
        log.warning("no_job_description", candidate=candidate)
        return {"resume_score": 0.0, "resume_analysis": "No job description provided."}
 

    prompt_text = f"""{RESUME_SCORER_PROMPT}

    Job Description:
    {jd}

    Candidate Resume:
    {resume_text}
    """
    
    with NodeTimer("resume_scorer", candidate=candidate) as timer:
        try:
            data: ResumeScoreOutput = invoke_with_fallback(resume_llm, resume_llm_fb, prompt_text)
            if data is None:
                raise ValueError("Structured output returned None")
            
            # ── not a resume — hard reject immediately ────────
            if data.not_a_resume:
                log.warning("not_a_resume",
                    candidate=candidate,
                    rationale=data.score_rationale,
                )
                analysis = (
                    f"Candidate Name     : {candidate}\n"
                    f"Score              : 0/100\n"
                    f"Score Rationale    : {data.score_rationale}\n\n"
                    f"Summary: {data.summary}"
                )
                timer.set_extra(score=0, band="Not a resume")
                return {
                    "resume_score":    0.0,
                    "resume_analysis": analysis,
                    "not_a_resume":    True,
                }
            
            
            analysis = (
                f"Candidate Name     : {state.get('candidate_name', '')}\n"
                f"Detected Seniority : {data.detected_seniority}\n"
                f"Score              : {data.score}/100\n"
                f"Score Rationale    : {data.score_rationale}\n"
                f"Seniority Alignment: {data.seniority_alignment}\n"
                f"Domain Alignment   : {data.domain_alignment}\n\n"
                f"Matched Skills     : {', '.join(data.matched_skills)}\n"
                f"Missing Skills     : {', '.join(data.missing_skills)}\n"
                f"Nice-to-Have Found : {', '.join(data.nice_to_have_matched)}\n\n"
                f"Summary: {data.summary}"
            )

            timer.set_extra(score=data.score, band=data.score_rationale.split(":")[0])
            log.info("resume_scored",
                candidate=candidate,
                score=data.score,
                seniority=data.detected_seniority,
                domain_alignment=data.domain_alignment,
                rationale=data.score_rationale,
            )
            return {
                "resume_score":    float(data.score),
                "resume_analysis": analysis,
            }

        except Exception as e:
            log.error("resume_scorer_failed. RECOVERY STARTED...",
                candidate=candidate,
                error_type=e.__class__.__name__,
                error=str(e)[:300],
            )
            
            try:
                response = llm.invoke(prompt_text)
                raw_text = _extract_text(response)
                score    = _extract_score(raw_text)
                timer.set_extra(score=score, recovered=True)
                return {
                    "resume_score":    score,
                    "resume_analysis": raw_text,
                }
            except Exception as fallback_err:
                log.error("resume_scorer_recovery_failed",
                    candidate=candidate,
                    error=str(fallback_err)[:200],
                )
                timer.set_extra(score=0.0, recovered=False)
                return {
                    "resume_score":    0.0,
                    "resume_analysis": "Resume analysis unavailable — all recovery attempts failed.",
                }