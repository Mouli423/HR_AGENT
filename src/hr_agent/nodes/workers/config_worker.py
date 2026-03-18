from src.hr_agent.core.state import GraphState
from src.hr_agent.nodes.workers.base_worker import generic_worker
from src.hr_agent.config.settings import WORKER_BATCH_SIZES

CONFIG_WORKER_PROMPT = """
You are a Configuration and Security Analysis Agent evaluating a software engineer's GitHub repositories.

Analyze ONLY the configuration files provided (.env, .cfg, .ini). Do NOT ask for more files.

Extract the following — be concise and evidence-based:
- secret_management: 1 sentence on how secrets and environment variables are handled
- config_tools: list configuration tools explicitly used e.g. dotenv, configparser, AWS SSM
- hardcoded_risks: list any hardcoded values that represent security or configuration risks

Rules:
- Only report what is explicitly present in the files
- Do NOT assume secret management patterns unless shown in code
- Flag hardcoded credentials, API keys, or region names specifically

CRITICAL: Return ONLY structured output. No explanations. No tags.
"""

def config_worker(state: GraphState) -> dict:
    print("---CONFIG_WORKER---")
    return generic_worker(
        state         = state,
        worker_key    = "config_worker",
        system_prompt = CONFIG_WORKER_PROMPT,
        batch_size    = WORKER_BATCH_SIZES["config_worker"],
    )