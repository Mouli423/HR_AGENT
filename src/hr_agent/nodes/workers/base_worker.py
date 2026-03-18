import json
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import Send
from src.hr_agent.core.state import GraphState
from src.hr_agent.core.llm import llm
from src.hr_agent.tools.github_client import fetch_file_content
from src.hr_agent.config.settings import MAX_FILES_PER_WORKER, WORKER_BATCH_SIZES
from src.hr_agent.core.llm import *
from src.hr_agent.tools.logger import get_logger, NodeTimer
from src.hr_agent.tools.llm_utils import invoke_with_fallback

def extract_notebook_code(ipynb_content: str) -> str:
    """
    Extracts only meaningful code cells from a Jupyter notebook.
    Strips: output cells, markdown, raw cells, import-only blocks.
    Caps at 20 cells max to prevent token overload on large notebooks.
    """
    try:
        nb    = json.loads(ipynb_content)
        cells = []
        for cell in nb.get("cells", []):
            if cell.get("cell_type") != "code":
                continue
            source = "".join(cell.get("source", [])).strip()
            if not source:
                continue
            # skip cells that are only imports or comments
            lines = [l for l in source.splitlines() if l.strip() and not l.strip().startswith("#")]
            if not lines:
                continue
            if all(l.startswith("import ") or l.startswith("from ") for l in lines):
                continue
            cells.append(source)
            if len(cells) >= 20:
                break
        return "\n\n".join(cells) if cells else ipynb_content[:1000]
    except Exception:
        return ipynb_content[:1000]
 

def generic_worker(
    state: GraphState,
    worker_key: str,
    system_prompt: str,
    batch_size: int = 10,
) -> dict:
    
    log       = get_logger(worker_key)
    candidate = state.get("candidate_name", "")
    urls            = state.get("routed_files", [])
    batch_summaries = []
    with NodeTimer(worker_key, candidate=candidate, files=len(urls)) as timer:
        for i in range(0, len(urls), batch_size):
            batch       = urls[i:i + batch_size]
            code_blocks = []

            for url in batch:
                try:
                    content = fetch_file_content(url)
                    if worker_key == "notebook_worker":
                        content = extract_notebook_code(content)
                    # truncate very large files
                    if len(content) > 5000:
                        content = content[:5000] + "\n... [truncated]"
                    code_blocks.append(f"\n### File: {url}\n```\n{content}\n```")
                except Exception:
                    continue

            if not code_blocks:
                continue

            prompt = (
                f"{system_prompt}\n\n"
                f"Analyze the following files:\n"
                + "\n".join(code_blocks)
            )
            if worker_key == "python_worker":
                structured_llm=python_worker_llm
                fallback_llm= python_worker_llm_fb
            elif worker_key == "config_worker":
                structured_llm=config_worker_llm
                fallback_llm=config_worker_llm_fb
            elif worker_key == "notebook_worker":
                structured_llm = notebook_worker_llm
                fallback_llm=notebook_worker_llm_fb
            elif worker_key == "infra_worker":
                structured_llm=infra_worker_llm
                fallback_llm=infra_worker_llm_fb
            elif worker_key == "readme_worker":
                structured_llm = readme_worker_llm
                fallback_llm=readme_worker_llm_fb
            try:
                response=invoke_with_fallback(structured_llm,fallback_llm,prompt)

                if response is None:
                    raise ValueError("Structured output returned None")
                batch_summaries.append(response)
            except Exception as e:
                log.error("worker_batch_failed",
                    worker=worker_key,
                    batch=i // batch_size + 1,
                    error_type=e.__class__.__name__,
                    error=str(e)[:200],
                )
                response = llm.invoke(prompt)
                batch_summaries.append({"raw": response.content[:1000]})
 


        if not batch_summaries:
            summary = f"No relevant files found for {worker_key}."
            log.info("worker_no_files", worker=worker_key, files=len(urls))
            timer.set_extra(batches=0)
            return {"summaries": [summary]}
        
        elif len(batch_summaries) == 1:
            summary = batch_summaries[0]
        else:
            # consolidate multiple batch summaries into one
            consolidation = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", """You have analyzed files in multiple batches.
            Here are the batch analyses:

            {batch_summaries}

            Consolidate into a single coherent technical summary.
            Remove duplication. Preserve all concrete technical evidence."""),
                    ])
            final   = llm.invoke(consolidation.format(
                batch_summaries="\n\n---\n\n".join(
                    f"Batch {i+1}:\n{s}" for i, s in enumerate(batch_summaries)
                )
            ))
            summary = final.content

        timer.set_extra(batches=len(batch_summaries))
        log.info("worker_complete",
            worker=worker_key,
            files=len(urls),
            batches=len(batch_summaries),
        )
        print(f"  Worker Name: {worker_key} has Finished | files={len(urls)} | batches={len(batch_summaries)}")
        
        return {"summaries": [{worker_key: summary}]}


def dispatch_workers(state: GraphState) -> list:
    """Fans out to all workers simultaneously via Send."""
    print("--- DISPATCH WORKERS (parallel) ---")

    routed_files = state.get("routed_files", [])

    worker_extensions = {
        "python_worker":   (".py",),
        "readme_worker":   ("readme.md",),
        "infra_worker":    ("dockerfile", ".yml", ".yaml"),
        "config_worker":   (".env", ".cfg", ".ini"),
        "notebook_worker": (".ipynb",),
    }

    sends = []
    for worker, extensions in worker_extensions.items():
        matched = [u for u in routed_files if u.lower().endswith(extensions)]

        if len(matched) > MAX_FILES_PER_WORKER:
            print(f"  Capping {worker}: {len(matched)} → {MAX_FILES_PER_WORKER} files")
            matched = matched[:MAX_FILES_PER_WORKER]

        if matched:
            print(f"  → dispatching {worker} ({len(matched)} files)")
            sends.append(Send(worker, {**state, "routed_files": matched}))

    if not sends:
        print("  → no files found, routing directly to synthesizer")
        return [Send("synthesizer", state)]

    return sends