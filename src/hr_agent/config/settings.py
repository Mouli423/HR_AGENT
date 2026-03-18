import os
from dotenv import load_dotenv
load_dotenv()

# ── API Keys ──────────────────────────────────────────────────
GROQ_API_KEY      = os.getenv("GROQ_API_KEY",      "")
GITHUB_TOKEN      = os.getenv("GITHUB_TOKEN",      "")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
AWS_REGION            = os.getenv("AWS_REGION",            "")
# ── SMTP ──────────────────────────────────────────────────────
SMTP_HOST     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER",     "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# ── LLM ───────────────────────────────────────────────────────

LLM_MODEL = "openai.gpt-oss-120b-1:0"
LLM_MODEL_FALLBACK = "amazon.nova-lite-v1:0" 
LLM_MODEL_WORKERS  = "amazon.nova-lite-v1:0"

# ── Scoring ───────────────────────────────────────────────────
SCORE_THRESHOLD = 70   # HR can raise/lower this

# ── GitHub traversal ──────────────────────────────────────────
MAX_FILES_PER_WORKER = 50
MAX_FILES_PER_REPO   = 100
MAX_TOTAL_FILES      = 500

WORKER_BATCH_SIZES = {
    "python_worker":   5,
    "notebook_worker": 3,
    "readme_worker":   10,
    "infra_worker":    10,
    "config_worker":   20,
}


RELEVANT_EXTENSIONS = {
    ".py", ".ipynb", ".md", ".yml", ".yaml", 
    "dockerfile", ".env", ".cfg", ".ini"
}


SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv",
    "venv", "env", "dist", "build", ".idea", ".vscode",
    "vendor", "assets", "images", "img", "static", "media",
}

# ── GitHub API ────────────────────────────────────────────────
GITHUB_API = "https://api.github.com"
GITHUB_HEADERS = {
    "Accept":               "application/vnd.github+json",
    "Authorization":        f"Bearer {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}