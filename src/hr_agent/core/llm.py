from src.hr_agent.config.settings import  LLM_MODEL,AWS_REGION, LLM_MODEL_FALLBACK, LLM_MODEL_WORKERS
from src.hr_agent.core.models import *
from langchain_aws import ChatBedrockConverse
from src.hr_agent.tools.logger import token_callback
from botocore.config import Config as BotocoreConfig
 
bedrock_config = BotocoreConfig(
    read_timeout=30,        # 30s — prevents long hangs on None responses
    connect_timeout=10,
    retries={"max_attempts": 0},  # no boto retries — fallback handles it
)
# primary
llm = ChatBedrockConverse(
                            model_id=LLM_MODEL,
                            region_name= AWS_REGION,
                            callbacks=[token_callback],
                            config= bedrock_config
                        )

# fallback
llm_fallback =  ChatBedrockConverse(
                            model_id=LLM_MODEL_FALLBACK,
                            region_name= AWS_REGION,
                            callbacks=[token_callback],
                            config=bedrock_config
                        )
# for workers
llm_workers =  ChatBedrockConverse(
                            model_id=LLM_MODEL_WORKERS,
                            region_name= AWS_REGION,
                            callbacks=[token_callback],
                            config=bedrock_config
                        )

# ── Structured output LLMs ────────────────────────────────────
extractor_llm    = llm.with_structured_output(ResumeExtractorOutput, method="json_mode")
resume_llm       = llm.with_structured_output(ResumeScoreOutput, method="json_mode")
github_llm       = llm.with_structured_output(GitHubScoreOutput, method="json_mode")
synthesizer_llm  = llm.with_structured_output(SynthesizerOutput, method="json_mode")
final_review_llm = llm.with_structured_output(FinalReviewOutput, method="json_mode")


# ── Per-worker structured output LLMs ─────────────────────────
python_worker_llm   = llm_workers.with_structured_output(PythonWorkerOutput, method="json_mode")
readme_worker_llm   = llm_workers.with_structured_output(ReadmeWorkerOutput, method="json_mode")
infra_worker_llm    = llm_workers.with_structured_output(InfraWorkerOutput, method="json_mode")
config_worker_llm   = llm_workers.with_structured_output(ConfigWorkerOutput, method="json_mode")
notebook_worker_llm = llm_workers.with_structured_output(NotebookWorkerOutput, method="json_mode")



# structured — fallback
resume_llm_fb       = llm_fallback.with_structured_output(ResumeScoreOutput, method="json_mode")
github_llm_fb       = llm_fallback.with_structured_output(GitHubScoreOutput, method="json_mode")
extractor_llm_fb    = llm_fallback.with_structured_output(ResumeExtractorOutput, method="json_mode")
final_review_llm_fb = llm_fallback.with_structured_output(FinalReviewOutput, method="json_mode")
synthesizer_llm_fb  = llm_fallback.with_structured_output(SynthesizerOutput, method="json_mode")
python_worker_llm_fb   = llm_fallback.with_structured_output(PythonWorkerOutput, method="json_mode")
readme_worker_llm_fb   = llm_fallback.with_structured_output(ReadmeWorkerOutput, method="json_mode")
infra_worker_llm_fb    = llm_fallback.with_structured_output(InfraWorkerOutput, method="json_mode")
config_worker_llm_fb   = llm_fallback.with_structured_output(ConfigWorkerOutput, method="json_mode")
notebook_worker_llm_fb = llm_fallback.with_structured_output(NotebookWorkerOutput, method="json_mode")

























































