"""
tools/llm_utils.py — LLM invocation with automatic fallback and structured logging.

All nodes call invoke_with_fallback() instead of llm.invoke() directly.
This gives us:
  - Automatic retry on primary model failure using the fallback model
  - Structured logging of every invocation (success, failure, fallback)
  - Token usage captured via TokenLoggingCallback (registered on the LLMs)
  - Failure and fallback counts accumulated in pipeline_stats
"""

import time
from src.hr_agent.tools.logger import get_logger, pipeline_stats


def invoke_with_fallback(
    primary_llm,
    fallback_llm,
    prompt
) -> any:
    """
    Invokes primary_llm. On any exception, logs the failure, increments
    pipeline_stats.primary_failures, and retries with fallback_llm.

    If fallback also fails, increments pipeline_stats.fallback_failures
    and re-raises so the node's own except block can handle recovery.

    Args:
        primary_llm  : structured output LLM (primary model)
        fallback_llm : structured output LLM (fallback model)
        prompt       : full prompt string to send
        node         : node name for logging (e.g. "resume_scorer")
        candidate    : candidate name for log context (optional)
        model_label  : label for the primary model in logs

    Returns:
        Pydantic model instance from whichever LLM succeeded

    Raises:
        RuntimeError if both primary and fallback fail
    """
    log   = get_logger("Model")
    start = time.time()

    # ── Attempt 1: primary model ──────────────────────────────
    try:
        result = primary_llm.invoke(prompt)

        if result is None:
            raise ValueError("Structured output returned None")

        duration_ms = int((time.time() - start) * 1000)
        log.info(
            "structured_output_success",
            duration_ms=duration_ms,
        )
        return result

    except Exception as primary_err:
        duration_ms = int((time.time() - start) * 1000)
        pipeline_stats.record_primary_failure()

        log.warning(
            "primary_model_failed",
            error_type=primary_err.__class__.__name__,
            error=str(primary_err)[:300],
            duration_ms=duration_ms,
        )

    # ── Attempt 2: fallback model ─────────────────────────────
    fallback_start = time.time()
    try:
        result = fallback_llm.invoke(prompt)

        if result is None:
            raise ValueError("Fallback structured output returned None")

        pipeline_stats.record_fallback_trigger()
        duration_ms = int((time.time() - fallback_start) * 1000)

        log.info(
            "fallback_model_success",
            duration_ms=duration_ms,
        )
        return result

    except Exception as fallback_err:
        pipeline_stats.record_fallback_failure()
        pipeline_stats.record_fallback_trigger()

        duration_ms = int((time.time() - fallback_start) * 1000)
        log.error(
            "fallback_model_failed",
            error_type=fallback_err.__class__.__name__,
            error=str(fallback_err)[:300],
            duration_ms=duration_ms,
        )

        raise RuntimeError(
            f"[Both primary and fallback models failed. "
            f"Fallback error: {fallback_err}"
        ) from fallback_err