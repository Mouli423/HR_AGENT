from src.hr_agent.core.state import GraphState
from src.hr_agent.nodes.workers.base_worker import generic_worker
from src.hr_agent.config.settings import WORKER_BATCH_SIZES

NOTEBOOK_WORKER_PROMPT = """
You are a Notebook and Experimentation Analysis Agent evaluating a software engineer's GitHub repositories.

Analyze ONLY the Jupyter notebook source code provided (output cells removed). Do NOT ask for more files.

Extract the following — be concise and evidence-based:
- topics: list ML/AI topics covered e.g. RAG, fine-tuning, embeddings, classification, LLM evaluation
- libraries: list libraries explicitly imported in the notebooks
- experimentation_depth: 1 sentence on whether this is a surface demo or a structured experiment with evaluation

Rules:
- Treat all notebooks as experimental by default
- Only include topics and libraries that are explicitly present
- Do NOT infer results, model performance, or production readiness

CRITICAL: Return ONLY structured output. No explanations. No tags.
"""

def notebook_worker(state: GraphState) -> dict:
    print("---NOTEBOOK_WORKER---")
    return generic_worker(
        state         = state,
        worker_key    = "notebook_worker",
        system_prompt = NOTEBOOK_WORKER_PROMPT,
        batch_size    = WORKER_BATCH_SIZES["notebook_worker"],
    )