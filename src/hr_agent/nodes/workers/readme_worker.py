from src.hr_agent.core.state import GraphState
from src.hr_agent.nodes.workers.base_worker import generic_worker
from src.hr_agent.config.settings import WORKER_BATCH_SIZES

README_WORKER_PROMPT = """
You are a Technical Documentation Analysis Agent evaluating a software engineer's GitHub repositories.

Analyze ONLY the README and markdown files provided. Do NOT ask for more files.

Extract the following — be concise and evidence-based:
- project_summaries: one line per repo in format "<repo_name>: what it does"
- technologies_mentioned: list technologies explicitly named in the documentation
- documentation_quality: 1 sentence on whether setup instructions, architecture, and usage are clearly explained

Rules:
- Base conclusions only on written content
- Do NOT assume undocumented features or capabilities
- Do NOT infer technical decisions not stated in the docs

CRITICAL: Return ONLY structured output. No explanations. No tags.
"""

def readme_worker(state: GraphState) -> dict:
    print("---README_WORKER---")
    return generic_worker(
        state         = state,
        worker_key    = "readme_worker",
        system_prompt = README_WORKER_PROMPT,
        batch_size    = WORKER_BATCH_SIZES["readme_worker"],
    )