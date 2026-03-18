import re
import json
from datetime import datetime


def _extract_text(response) -> str:
    """Extracts plain text from LLM response regardless of format."""
    content = response.content if hasattr(response, "content") else response
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "")
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
        )
    return str(content)


def _extract_score(text: str) -> float:
    """
    Extracts numeric score from LLM response.
    Tries JSON parsing first (handles partial structured output failures),
    then falls back to regex patterns on plain text.
    """
    # ── 1. JSON parsing — handles partial structured output ───
    try:
        cleaned = re.sub(r"```json|```", "", text).strip()
        match   = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            data  = json.loads(match.group(0))
            score = data.get("score",
                    data.get("overall_score",
                    data.get("github_score",
                    data.get("resume_score", None))))
            if isinstance(score, (int, float)) and 0 <= float(score) <= 100:
                return float(score)
    except Exception:
        pass

    # ── 2. Regex fallbacks on plain text ──────────────────────
    text_lower = text.lower()

    # "score: 88" or "score of 88"
    match = re.search(r'score[\s:of]*(\d{1,3})', text_lower)
    if match:
        score = int(match.group(1))
        if 0 <= score <= 100:
            return float(score)

    # "88/100"
    match = re.search(r'(\d{1,3})\s*/\s*100', text_lower)
    if match:
        score = int(match.group(1))
        if 0 <= score <= 100:
            return float(score)

    # "overall_score": 54
    match = re.search(r'overall_score["\s:]+(\d{1,3})', text_lower)
    if match:
        score = int(match.group(1))
        if 0 <= score <= 100:
            return float(score)

    # "88 out of 100"
    match = re.search(r'(\d{1,3})\s+out\s+of\s+100', text_lower)
    if match:
        score = int(match.group(1))
        if 0 <= score <= 100:
            return float(score)

    return 0.0


