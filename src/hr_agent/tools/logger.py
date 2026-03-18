

"""
tools/logger.py — Centralised structured logging for the HR Agent pipeline.

Usage:
    from tools.logger import get_logger, pipeline_stats, configure_logger

    configure_logger()                        # call once in main.py
    log = get_logger("resume_scorer")
    log.info("scoring_complete", score=91, duration_ms=3200)

Token counts are captured automatically via TokenLoggingCallback —
register it on any ChatBedrock instance to get input/output token tracking
without touching the structured output chain.
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


# ── Pipeline-level stats (thread-safe counters) ───────────────

class PipelineStats:
    """
    Accumulates token usage and failure counts across the entire pipeline run.
    Thread-safe — workers run in parallel so we use a lock.
    """
    def __init__(self):
        self._lock               = threading.Lock()
        self.total_input_tokens  = 0
        self.total_output_tokens = 0
        self.primary_failures    = 0
        self.fallback_triggers   = 0
        self.fallback_failures   = 0
        self.node_durations: Dict[str, List[float]] = {}
        self.pipeline_start_time: Optional[float]   = None

    def reset(self):
        with self._lock:
            self.total_input_tokens  = 0
            self.total_output_tokens = 0
            self.primary_failures    = 0
            self.fallback_triggers   = 0
            self.fallback_failures   = 0
            self.node_durations      = {}
            self.pipeline_start_time = time.time()

    def add_tokens(self, input_tokens: int, output_tokens: int):
        with self._lock:
            self.total_input_tokens  += input_tokens
            self.total_output_tokens += output_tokens

    def record_primary_failure(self):
        with self._lock:
            self.primary_failures += 1

    def record_fallback_trigger(self):
        with self._lock:
            self.fallback_triggers += 1

    def record_fallback_failure(self):
        with self._lock:
            self.fallback_failures += 1

    def record_node_duration(self, node: str, duration_ms: float):
        with self._lock:
            self.node_durations.setdefault(node, []).append(duration_ms)

    def total_duration_ms(self) -> int:
        if self.pipeline_start_time is None:
            return 0
        return int((time.time() - self.pipeline_start_time) * 1000)

    def summary(self) -> dict:
        with self._lock:
            return {
                "total_input_tokens":  self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_tokens":        self.total_input_tokens + self.total_output_tokens,
                "primary_failures":    self.primary_failures,
                "fallback_triggers":   self.fallback_triggers,
                "fallback_failures":   self.fallback_failures,
                "total_duration_ms":   self.total_duration_ms(),
                "node_durations":      dict(self.node_durations),
            }


# global singleton — imported by all nodes and llm_utils
pipeline_stats = PipelineStats()


# ── LangChain callback — captures token counts from raw LLM responses ──

class TokenLoggingCallback(BaseCallbackHandler):
    """
    Registered on ChatBedrock instances to capture token usage metadata.

    Handles two Bedrock response formats:
      - Tool-calling mode : usage in response.llm_output["usage"]
      - json_mode / chat  : usage in generations[0][0].message.response_metadata
    Also handles amazon-bedrock-invocationMetrics key format.
    """

    def _extract_usage(self, response: LLMResult) -> tuple:
        usage = {}

        # path 1 — llm_output (tool-calling mode)
        if response.llm_output:
            usage = response.llm_output.get("usage", {})

        # path 2 — response_metadata on the generation message (json_mode)
        if not usage and response.generations:
            try:
                gen  = response.generations[0][0]
                msg  = getattr(gen, "message", None)
                meta = getattr(msg, "response_metadata", {}) or {}
                usage = (
                    meta.get("usage") or
                    meta.get("amazon-bedrock-invocationMetrics") or
                    {}
                )
            except Exception:
                pass

        input_tokens  = int(usage.get("inputTokens",  usage.get("input_tokens",  usage.get("inputTokenCount",  0))))
        output_tokens = int(usage.get("outputTokens", usage.get("output_tokens", usage.get("outputTokenCount", 0))))
        return input_tokens, output_tokens

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        try:
            input_tokens, output_tokens = self._extract_usage(response)

            if input_tokens or output_tokens:
                pipeline_stats.add_tokens(input_tokens, output_tokens)
                log = get_logger("token_tracker")
                log.debug(
                    "llm_token_usage",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                )
        except Exception:
            pass  # never let logging break the pipeline

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        try:
            log = get_logger("token_tracker")
            log.warning("llm_error", error_type=error.__class__.__name__, error=str(error)[:200])
        except Exception:
            pass


# singleton callback instance — passed to ChatBedrock at construction time
token_callback = TokenLoggingCallback()


# ── structlog configuration ───────────────────────────────────

def configure_logger(
    log_file: str = "logs/pipeline.jsonl",
    level: str    = "INFO",
) -> None:
    """
    Call once at startup in main.py.

    Configures two outputs:
      - Console  : human-readable with colours (ConsoleRenderer)
      - JSONL file: machine-readable, one JSON object per line
    """
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # stdlib logging — routes to both console and file
    log_level = getattr(logging, level.upper(), logging.INFO)

    # file handler — JSONL
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)

    # console handler — human readable
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    logging.basicConfig(
        level=log_level,
        handlers=[file_handler, console_handler],
        format="%(message)s",
    )

    # silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "botocore", "boto3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # branch: file gets JSON, console gets pretty
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # file formatter — pure JSON lines
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
    )
    file_handler.setFormatter(file_formatter)

    # console formatter — coloured key=value
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
    )
    console_handler.setFormatter(console_formatter)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Returns a structlog logger bound to the given node/component name."""
    return structlog.get_logger(name)


# ── Node timing context manager ───────────────────────────────

class NodeTimer:
    """
    Context manager for timing a node and logging start/end automatically.

    Usage:
        with NodeTimer("resume_scorer", candidate="John") as timer:
            data = invoke_with_fallback(...)
            timer.set_extra(score=data.score)
    """
    def __init__(self, node: str, **context):
        self.node      = node
        self.context   = context
        self.extra     = {}
        self._start    = None
        self.log       = get_logger(node)

    def set_extra(self, **kwargs):
        """Add extra fields to the completion log event."""
        self.extra.update(kwargs)

    def __enter__(self):
        self._start = time.time()
        self.log.info("node_start", **self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self._start) * 1000)
        pipeline_stats.record_node_duration(self.node, duration_ms)

        if exc_type:
            self.log.error(
                "node_failed",
                duration_ms=duration_ms,
                error_type=exc_type.__name__,
                error=str(exc_val)[:300],
                **self.context,
                **self.extra,
            )
        else:
            self.log.info(
                "node_complete",
                duration_ms=duration_ms,
                **self.context,
                **self.extra,
            )
        return False  # don't suppress exceptions