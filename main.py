"""
main.py — entry point for running the HR agent pipeline.

Usage:
    python main.py

To resume after HITL pause:
    from graph.pipeline import graph
    from langgraph.types import Command

    graph.invoke(
        Command(resume={"outcome": "approved", "reason": "Strong profile."}),
        {"configurable": {"thread_id": "<same THREAD_ID>"}},
    )
"""
import os
import uuid
from src.hr_agent.graph.pipeline import graph
from langgraph.types import Command
from src.hr_agent.tools.logger import configure_logger, get_logger, pipeline_stats
from dotenv import load_dotenv
load_dotenv()

os.environ["LANGSMITH_API_KEY"]=os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"]="true"
os.environ["LANGCHAIN_PROJECT"]="HR Agent"

# ── Configuration — edit these ────────────────────────────────
JD = """

Job Title: Junior AI / GenAI Engineer
Company: TechForward AI (Series B, 120 employees)
Location: Remote (US/UK/India)

About the Role
We are looking for a Junior AI Engineer to join our growing AI team. You will work on building and deploying LLM-powered applications, RAG pipelines, and agentic workflows that serve real business use cases across our product suite.

Responsibilities

Build and maintain RAG pipelines using vector databases (FAISS, Chroma, Pinecone)
Develop LLM-powered agents using LangChain and LangGraph
Integrate with LLM providers such as OpenAI, Groq, Anthropic, and AWS Bedrock
Build interactive demos and internal tools using Streamlit or FastAPI
Write clean, modular Python code following best practices
Collaborate with senior engineers on prompt engineering and evaluation frameworks
Deploy AI services to cloud platforms (AWS or Azure or GCP)
Participate in code reviews and contribute to documentation


Required Skills

Python (1-2 years experience)
LangChain or LangGraph (any hands-on experience)
Experience with at least one LLM provider API (OpenAI, Groq, Anthropic, Bedrock)
Basic understanding of RAG — document loaders, chunking, embeddings, vector stores
Familiarity with Git and GitHub
Basic cloud exposure (AWS, Azure, or GCP)


Nice to Have

Experience with Streamlit or FastAPI for building UIs or APIs
Exposure to Docker or containerization
Understanding of prompt engineering techniques
Any fine-tuning experience (LoRA, PEFT)
CI/CD basics (GitHub Actions)
Familiarity with agentic patterns (tool use, multi-agent, HITL)


What We Offer

Competitive salary ($65k–$85k USD or equivalent)
Remote-first culture
Learning budget ($1,500/year)
Access to GPU compute for personal projects
Direct mentorship from senior AI engineers


"""

RESUME_PATH  = "./sample_resumes/pdfresume.pdf"
APPLIED_ROLE = "AI Engineer"
#THREAD_ID    = str(uuid.uuid4())

INITIAL_STATE = {
    "job_description":  JD,
    "resume_path":      RESUME_PATH,
    "applied_role":     APPLIED_ROLE,
    # everything below is auto-populated by the pipeline
    "resume_text":        "",
    "candidate_name":     "",
    "candidate_email":    "",
    "current_role":       "",
    "github_url":         None,
    "linkedin_url":       None,
    "routed_files":       [],
    "analyzed_repos":     [],
    "summaries":          {},
    "next_action":        "",
    "final_summary":      "",
    "final_profile":      "",
    "security_red_flags": [],
    "resume_score":       0.0,
    "resume_analysis":    "",
    "not_a_resume":       False,
    "github_score":       0.0,
    "github_analysis":    "",
    "decision":           "hitl",
    "hitl_outcome":       None,
    "hitl_reason":        None,
    "hitl_packet":        None,
    "rejection_reason":   "",
    "next_steps":         "",
    "email_sent":         False,
}


# def run():
#     print(f"\nThread ID : {THREAD_ID}")
#     print("Starting HR Agent pipeline...\n")

#     result = graph.invoke(
#         INITIAL_STATE,
#         {"configurable": {"thread_id": THREAD_ID}},
#     )

#     print(f"\nCandidate : {result.get('candidate_name')}")
#     print(f"Decision  : {result.get('decision')}")
#     print(f"Resume    : {result.get('resume_score')}/100")
#     print(f"GitHub    : {result.get('github_score')}/100")

#     if result.get("decision") == "hitl":
#         print("\nPipeline paused — awaiting HR review.")
#         print(f"HR Packet preview: {result.get('hitl_packet', {}).get('review_reason')}")
#         print(f"\nTo resume:\n"
#               f"  graph.invoke(\n"
#               f"    Command(resume={{\"outcome\": \"approved\", \"reason\": \"...\"}},\n"
#               f"    {{\"configurable\": {{\"thread_id\": \"{THREAD_ID}\"}}}}\n"
#               f"  )\n")


# if __name__ == "__main__":
#     run()

def run():

    configure_logger(log_file="logs/pipeline.jsonl", level="INFO")
    pipeline_stats.reset()
    log = get_logger("pipeline")

    # ── Input validation ──────────────────────────────────────
    from src.hr_agent.tools.input_validator import validate_all
    validation = validate_all(
        file_path = RESUME_PATH,
        file_name = os.path.basename(RESUME_PATH),
        jd        = JD,
        role      = APPLIED_ROLE,
    )
    for w in validation["warnings"]:
        print(f"  [WARNING] {w}")
    if not validation["ok"]:
        for e in validation["errors"]:
            print(f"  [ERROR] {e}")
        print("\nPipeline aborted due to validation errors.")
        return
 
    # use sanitized inputs
    INITIAL_STATE["job_description"] = validation["jd"].sanitized
    INITIAL_STATE["applied_role"]    = validation["role"].sanitized
 
 
    log.info("=========== HR AGENT EXECUTION PIPELINE STARTED =============",
        
        applied_role=APPLIED_ROLE,
        resume_path=RESUME_PATH,
    )
 
    print("Starting HR Agent pipeline...\n")

    result = graph.invoke(INITIAL_STATE)
    
    stats = pipeline_stats.summary()
    log.info("pipeline_complete",
        candidate=result.get("candidate_name"),
        decision=result.get("decision", "").upper(),
        resume_score=result.get("resume_score"),
        github_score=result.get("github_score"),
        email_sent=result.get("email_sent"),
        **stats,
    )
    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"Candidate : {result.get('candidate_name')}")
    print(f"Decision  : {result.get('decision', '').upper()}")
    print(f"Resume    : {result.get('resume_score')}/100")
    print(f"GitHub    : {result.get('github_score')}/100")
    print(f"Email     : {'Sent' if result.get('email_sent') else 'Not sent'}")
    print(f"{'='*60}")
    print(f"Tokens    : {stats['total_input_tokens']} in / {stats['total_output_tokens']} out")
    print(f"Failures  : {stats['primary_failures']} primary / {stats['fallback_triggers']} fallbacks")
    print(f"Duration  : {stats['total_duration_ms']}ms")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run()