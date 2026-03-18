"""
tools/input_validator.py — Input sanitization and validation for the HR Agent.

Validates three inputs before they touch the LLM:
  1. Resume file  — file type, size, content extraction, malicious pattern detection
  2. Job Description — length, content sanity, prompt injection detection
  3. Applied Role — length, format, sanity check

All validators return a ValidationResult with:
  - ok: bool
  - errors: list of blocking errors (must fix before proceeding)
  - warnings: list of non-blocking warnings (shown to HR but pipeline continues)
  - sanitized: cleaned version of the input safe to pass to the pipeline
"""

import re
import os
from dataclasses import dataclass, field
from typing import List, Optional


# ── Constants ─────────────────────────────────────────────────

# Resume file
ALLOWED_EXTENSIONS      = {".pdf", ".docx"}
MAX_FILE_SIZE_MB        = 5
MAX_RESUME_TEXT_CHARS   = 15_000
MIN_RESUME_TEXT_CHARS   = 100

# Job description
MAX_JD_CHARS            = 10_000
MIN_JD_CHARS            = 50

# Applied role
MAX_ROLE_CHARS          = 100
MIN_ROLE_CHARS          = 2

# Prompt injection patterns — attempts to override LLM instructions
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|above|prior)\s+instructions?",
    r"forget\s+(all\s+)?(previous|above|prior)\s+instructions?",
    r"you\s+are\s+now\s+(a\s+)?(different|new|another)",
    r"act\s+as\s+(a\s+)?(different|new|another|unrestricted|jailbroken)",
    r"new\s+instructions?\s*:",
    r"system\s*:\s*you\s+are",
    r"<\s*system\s*>",
    r"\[system\]",
    r"###\s*instructions?\s*###",
    r"do\s+not\s+(follow|obey|comply)\s+(the\s+)?(previous|above|prior)",
    r"bypass\s+(all\s+)?(restrictions?|guidelines?|rules?|filters?)",
    r"jailbreak",
    r"prompt\s+injection",
    r"DAN\s+mode",
    r"developer\s+mode\s+enabled",
]

# Malicious file content patterns
MALICIOUS_PATTERNS = [
    r"<script[\s>]",                        # embedded scripts
    r"javascript\s*:",                       # JS protocol
    r"eval\s*\(",                            # eval calls
    r"exec\s*\(",                            # exec calls
    r"__import__\s*\(",                      # python imports in text
    r"subprocess\s*\.",                      # subprocess calls
    r"os\s*\.\s*system\s*\(",               # os.system
    r"base64\s*\.\s*decode",               # encoded payloads
    r"\x00",                                # null bytes
    r"&lt;script",                           # HTML-encoded script
]

# Suspicious JD patterns — attempts to manipulate scoring
SUSPICIOUS_JD_PATTERNS = [
    r"always\s+(score|rate|give|assign)\s+(100|full|maximum|perfect)",
    r"score\s+(must|should)\s+be\s+(100|maximum|perfect|high)",
    r"ignore\s+(the\s+)?(candidate|resume|github|score)",
    r"approve\s+(all|every)\s+(candidate|applicant)",
    r"automatically\s+(select|approve|accept)\s+(all|every)",
    r"do\s+not\s+(reject|screen|filter)\s+(any|all)",
    r"give\s+(everyone|all\s+candidates)\s+(a\s+)?high\s+score",
]


@dataclass
class ValidationResult:
    ok:        bool         = True
    errors:    List[str]    = field(default_factory=list)
    warnings:  List[str]    = field(default_factory=list)
    sanitized: Optional[str] = None   # cleaned text (for JD and role)

    def fail(self, msg: str):
        self.ok = False
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)


# ── Helpers ───────────────────────────────────────────────────

def _check_injection(text: str, context: str) -> List[str]:
    """Returns list of detected injection pattern descriptions."""
    found = []
    text_lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            found.append(f"Prompt injection pattern detected in {context}: '{pattern}'")
    return found


def _sanitize_text(text: str) -> str:
    """
    Basic sanitization:
    - Strip null bytes and control characters (except newlines/tabs)
    - Normalize excessive whitespace
    - Strip leading/trailing whitespace
    """
    # remove null bytes and non-printable control chars
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # normalize multiple blank lines to max 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # normalize multiple spaces
    text = re.sub(r" {3,}", "  ", text)
    return text.strip()


# ── Validators ────────────────────────────────────────────────

def validate_resume_file(file_path: str, file_name: str) -> ValidationResult:
    """
    Validates the uploaded resume file.
    Checks: extension, file size, text extractability, content length,
            malicious patterns in extracted text.
    Returns ValidationResult with sanitized=extracted_text if ok.
    """
    result = ValidationResult()

    # ── 1. File extension ─────────────────────────────────────
    ext = os.path.splitext(file_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        result.fail(
            f"Unsupported file type '{ext}'. "
            f"Only PDF and DOCX files are accepted."
        )
        return result  # can't continue without valid file type

    # ── 2. File size ──────────────────────────────────────────
    try:
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            result.fail(
                f"File too large ({size_mb:.1f} MB). "
                f"Maximum allowed size is {MAX_FILE_SIZE_MB} MB."
            )
            return result
    except OSError as e:
        result.fail(f"Could not read file: {e}")
        return result

    # ── 3. Text extraction ────────────────────────────────────
    try:
        from src.hr_agent.tools.resume_parser import parse_resume
        parsed = parse_resume(file_path)
        text   = parsed.get("text", "").strip()
    except Exception as e:
        result.fail(f"Failed to extract text from resume: {e}")
        return result

    if not text:
        result.fail(
            "No text could be extracted from the file. "
            "The file may be image-only, corrupted, or password-protected."
        )
        return result

    # ── 4. Text length ────────────────────────────────────────
    if len(text) < MIN_RESUME_TEXT_CHARS:
        result.fail(
            f"Resume appears too short ({len(text)} chars). "
            f"Minimum expected content is {MIN_RESUME_TEXT_CHARS} characters. "
            f"The file may be mostly images or have extraction issues."
        )
        return result

    if len(text) > MAX_RESUME_TEXT_CHARS:
        result.warn(
            f"Resume is very long ({len(text):,} chars). "
            f"Content will be truncated to {MAX_RESUME_TEXT_CHARS:,} characters."
        )
        text = text[:MAX_RESUME_TEXT_CHARS]

    # ── 5. Malicious content patterns ────────────────────────
    text_lower = text.lower()
    for pattern in MALICIOUS_PATTERNS:
        if re.search(pattern, text_lower):
            result.fail(
                f"Potentially malicious content detected in resume. "
                f"The file cannot be processed."
            )
            return result

    # ── 6. Prompt injection in resume text ───────────────────
    injections = _check_injection(text, "resume")
    for msg in injections:
        result.warn(
            "Suspicious instruction-like text found in resume. "
            "The content will still be processed but flagged for HR review."
        )
        break  # one warning is enough

    # ── 7. Basic content sanity — looks like a resume? ────────
    resume_indicators = [
        r"\b(experience|education|skills?|projects?|work|employment)\b",
        r"\b(python|java|sql|excel|degree|university|college|b\.?tech|m\.?tech)\b",
        r"\b(developer|engineer|analyst|manager|intern|student)\b",
    ]
    matched = sum(
        1 for p in resume_indicators
        if re.search(p, text_lower)
    )
    if matched == 0:
        result.warn(
            "The uploaded document does not appear to be a resume. "
            "Please verify you uploaded the correct file."
        )

    result.sanitized = _sanitize_text(text)
    return result


def validate_job_description(jd: str) -> ValidationResult:
    """
    Validates the job description text.
    Checks: length, prompt injection, manipulation attempts, basic sanity.
    Returns ValidationResult with sanitized=cleaned_jd if ok.
    """
    result    = ValidationResult()
    jd_stripped = jd.strip()

    # ── 1. Length checks ──────────────────────────────────────
    if len(jd_stripped) < MIN_JD_CHARS:
        result.fail(
            f"Job description is too short ({len(jd_stripped)} chars). "
            f"Please provide a detailed JD with at least {MIN_JD_CHARS} characters."
        )
        return result

    if len(jd_stripped) > MAX_JD_CHARS:
        result.warn(
            f"Job description is very long ({len(jd_stripped):,} chars). "
            f"It will be truncated to {MAX_JD_CHARS:,} characters."
        )
        jd_stripped = jd_stripped[:MAX_JD_CHARS]

    # ── 2. Prompt injection ───────────────────────────────────
    injections = _check_injection(jd_stripped, "job description")
    if injections:
        result.fail(
            "The job description contains text that appears to be attempting "
            "to manipulate the AI scoring system. Please review and resubmit."
        )
        return result

    # ── 3. Score manipulation attempts ────────────────────────
    jd_lower = jd_stripped.lower()
    for pattern in SUSPICIOUS_JD_PATTERNS:
        if re.search(pattern, jd_lower):
            result.fail(
                "The job description contains instructions that attempt to "
                "manipulate candidate scoring. Please provide a genuine JD."
            )
            return result

    # ── 4. Basic JD sanity — looks like a job description? ───
    jd_indicators = [
        r"\b(responsibilities?|requirements?|qualifications?|skills?|duties)\b",
        r"\b(experience|years?|degree|role|position|candidate|team|company)\b",
        r"\b(engineer|developer|analyst|manager|lead|senior|junior|intern)\b",
    ]
    matched = sum(1 for p in jd_indicators if re.search(p, jd_lower))
    if matched == 0:
        result.warn(
            "The job description does not appear to describe a job role. "
            "Please verify you pasted the correct content."
        )

    result.sanitized = _sanitize_text(jd_stripped)
    return result


def validate_applied_role(role: str) -> ValidationResult:
    """
    Validates the applied role input.
    Checks: length, format, injection, sanity.
    Returns ValidationResult with sanitized=cleaned_role if ok.
    """
    result       = ValidationResult()
    role_stripped = role.strip()

    # ── 1. Length checks ──────────────────────────────────────
    if len(role_stripped) < MIN_ROLE_CHARS:
        result.fail(
            f"Applied role is too short. "
            f"Please enter the role title (e.g. 'Junior AI Engineer')."
        )
        return result

    if len(role_stripped) > MAX_ROLE_CHARS:
        result.fail(
            f"Applied role is too long ({len(role_stripped)} chars). "
            f"Maximum allowed length is {MAX_ROLE_CHARS} characters. "
            f"Please enter just the job title."
        )
        return result

    # ── 2. Format check — should look like a job title ────────
    # Allow letters, numbers, spaces, hyphens, slashes, parentheses
    if not re.match(r"^[a-zA-Z0-9\s\-\/\(\)&,\.]+$", role_stripped):
        result.fail(
            "Applied role contains invalid characters. "
            "Please enter a plain job title (e.g. 'Senior Data Engineer')."
        )
        return result

    # ── 3. Prompt injection ───────────────────────────────────
    injections = _check_injection(role_stripped, "applied role")
    if injections:
        result.fail(
            "The applied role field contains suspicious text. "
            "Please enter a valid job title."
        )
        return result

    # ── 4. Sanity — should look like a job title ──────────────
    # Flag if it's just numbers or a single repeated character
    if re.match(r"^[0-9\s]+$", role_stripped):
        result.fail("Applied role must contain letters, not just numbers.")
        return result

    if len(set(role_stripped.lower().replace(" ", ""))) < 2:
        result.fail("Applied role does not appear to be a valid job title.")
        return result

    result.sanitized = _sanitize_text(role_stripped)
    return result


# ── Combined validator ────────────────────────────────────────

def validate_all(
    file_path: str,
    file_name: str,
    jd: str,
    role: str,
) -> dict:
    """
    Runs all three validators and returns a combined result dict:
    {
        "ok": bool,                    # True only if ALL validators pass
        "resume": ValidationResult,
        "jd":     ValidationResult,
        "role":   ValidationResult,
        "errors": [str],               # all blocking errors combined
        "warnings": [str],             # all warnings combined
    }
    """
    resume_result = validate_resume_file(file_path, file_name)
    jd_result     = validate_job_description(jd)
    role_result   = validate_applied_role(role)

    all_errors   = resume_result.errors + jd_result.errors + role_result.errors
    all_warnings = resume_result.warnings + jd_result.warnings + role_result.warnings

    return {
        "ok":       len(all_errors) == 0,
        "resume":   resume_result,
        "jd":       jd_result,
        "role":     role_result,
        "errors":   all_errors,
        "warnings": all_warnings,
    }