from src.hr_agent.core.state import GraphState
from src.hr_agent.nodes.workers.base_worker import generic_worker
from src.hr_agent.config.settings import WORKER_BATCH_SIZES


INFRA_WORKER_PROMPT = """
You are an Infrastructure and DevOps Analysis Agent evaluating a software engineer's GitHub repositories.

Analyze ONLY the infrastructure files provided (Dockerfiles, YAML, CI/CD configs). Do NOT ask for more files.

Extract the following — be concise and evidence-based:
- containerisation: list Docker, Kubernetes, or compose files found
- ci_cd: list CI/CD tools and pipeline files found e.g. GitHub Actions workflows
- cloud_services: list cloud services explicitly configured in these files
- deployment_gaps: 1 sentence on missing production infrastructure e.g. no IaC, no health checks, no secrets management

Rules:
- Only report what is explicitly defined in the files
- Do NOT infer cloud usage unless it is configured in the provided files
- If infrastructure is minimal, state that clearly

CRITICAL: Return ONLY structured output. No explanations. No tags.
"""

def infra_worker(state: GraphState) -> dict:
    print("---INFRA_WORKER---")
    return generic_worker(
        state         = state,
        worker_key    = "infra_worker",
        system_prompt = INFRA_WORKER_PROMPT,
        batch_size    = WORKER_BATCH_SIZES["infra_worker"],
    )