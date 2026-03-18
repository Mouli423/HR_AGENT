# 🎯 HR_AGENT — AI-Powered Candidate Screening Pipeline

[![CI](https://github.com/Mouli423/HR_AGENT/actions/workflows/ci.yml/badge.svg)](https://github.com/Mouli423/HR_AGENT/actions/workflows/ci.yml)
[![Deploy](https://github.com/Mouli423/HR_AGENT/actions/workflows/deploy.yml/badge.svg)](https://github.com/Mouli423/HR_AGENTt/actions/workflows/deploy.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock-FF9900.svg)](https://aws.amazon.com/bedrock/)

An end-to-end AI agent that screens technical candidates by analyzing their resume and GitHub profile, scoring them against a job description, routing borderline cases to HR for review, and automatically sending acceptance or rejection emails.

---

## 📋 Table of Contents

- [Demo](#-demo)
- [Architecture](#-architecture)
- [Pipeline Flow](#-pipeline-flow)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Configuration](#-configuration)
- [Running the App](#-running-the-app)
- [Docker](#-docker)
- [CI/CD](#-cicd)
- [Deployment (AWS EC2)](#-deployment-aws-ec2)
- [Performance](#-performance)
- [ROI Analysis](#-roi-analysis)

---

## 🎬 Demo

```
Resume uploaded → Pipeline runs (~90s) → Auto-selected or HR Review → Email sent
```

**Streamlit UI** — upload resume, paste JD, run pipeline, review HITL decisions.  
**CLI** — configure `main.py` and run `python main.py`.

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        HR Agent Pipeline                        │
│                                                                 │
│  Resume PDF/DOCX                                                │
│       ↓                                                         │
│  resume_extractor → resume_scorer                               │
│                          │                                      │
│              ┌───────────┴───────────┐                          │
│         has github_url          no github_url                   │
│              ↓                       ↓                          │
│    profile_extractor          decision_engine                   │
│         │                                                       │
│    ┌────┴────┐                                                  │
│  has repos  0 repos                                             │
│    ↓          ↓                                                 │
│  Workers → decision_engine                                      │
│  (parallel)                                                     │
│  ├── python_worker                                              │
│  ├── readme_worker                                              │
│  ├── infra_worker                                               │
│  ├── config_worker                                              │
│  └── notebook_worker                                            │
│       ↓                                                         │
│  synthesizer → final_review → github_scorer → decision_engine  │
│                                                    │            │
│                                     ┌──────────────┤           │
│                                auto_select        hitl          │
│                                     ↓              ↓           │
│                              acceptance        HR Review UI     │
│                                 email         approve/reject    │
│                                                    ↓           │
│                                             acceptance or       │
│                                             rejection email     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Pipeline Flow

| Step | Node | What It Does | Model | Time |
|------|------|-------------|-------|------|
| 1 | `resume_extractor` | Parses PDF/DOCX (including table layouts), extracts name, email, GitHub URL | GPT-OSS-120B | ~2s |
| 2 | `resume_scorer` | Semantic skills matching against JD, seniority detection, rubric scoring | GPT-OSS-120B | ~5s |
| 3 | `profile_extractor` | Fetches all public GitHub repos (non-fork, non-archived) | — | ~25s |
| 4 | Workers (×5) | Parallel analysis of Python, README, Infra, Config, Notebook files | Nova Lite | ~15s |
| 5 | `synthesizer` | Merges worker outputs into a coherent technical profile | GPT-OSS-120B | ~5s |
| 6 | `final_review` | Professional technical assessment against JD | GPT-OSS-120B | ~3s |
| 7 | `github_scorer` | Scores GitHub profile with originality and seniority signals | GPT-OSS-120B | ~4s |
| 8 | `decision_engine` | Routes to auto-select (both ≥70) or HITL | — | <1s |
| 9 | `email` | Sends acceptance or rejection via SMTP | — | ~1s |

---

## ✨ Features

### Scoring
- **Rubric-based scoring** with 7 bands: Poor → Weak → Moderate → Borderline → Strong → Very Strong → Exceptional
- **Score rationale** — model commits to a band before choosing a score (chain-of-thought variance reduction)
- **±2–3% score variance** across repeated runs (vs ±10–20% for human reviewers)
- **Seniority-aware** — junior candidates not penalized for lacking senior signals
- **Security-aware** — dotenv/hardcoded configs not penalized for junior roles

### Reliability
- **Primary model** (`openai.gpt-oss-120b-1:0`) for high-quality scoring and synthesis
- **Fallback model** (`amazon.nova-lite-v1:0`) automatically used when primary structured output fails
- **Pydantic validators** with `coerce_to_list` — handles dict/string/list responses from any model
- **Partial JSON recovery** — fallback parsing when structured output returns incomplete JSON

### Smart Routing
- No GitHub URL → skip directly to decision engine
- 0 public repos → skip workers, synthesizer, final review
- Not a resume → hard reject immediately (no HITL)
- Both scores ≥ threshold → auto-select, email sent automatically

### Input Validation
- File type and size validation (PDF/DOCX, max 5MB)
- Prompt injection detection in JD and resume
- Score manipulation attempt detection (`"give everyone 100"`)
- Resume content sanity check
- Applied role format and length validation

### Observability
- **Structured logging** with `structlog` — JSONL to `logs/pipeline.jsonl`
- **Token tracking** via LangChain callback handler
- **LangSmith tracing** — full trace of every LLM call
- **Pipeline stats** — primary failures, fallback triggers, node durations per run

---

## 🛠 Tech Stack

| Category | Technology |
|----------|-----------|
| Orchestration | LangGraph 0.2 |
| LLM Framework | LangChain AWS |
| Primary Model | AWS Bedrock — `openai.gpt-oss-120b-1:0` |
| Fallback Model | AWS Bedrock — `amazon.nova-lite-v1:0` |
| UI | Streamlit (FSM pattern) |
| Validation | Pydantic v2 |
| Logging | structlog |
| Tracing | LangSmith |
| Email | SMTP (Gmail / AWS SES) |
| Containerization | Docker + docker-compose |
| CI/CD | GitHub Actions |
| Registry | Amazon ECR |
| Hosting | AWS EC2 |

---

## 📁 Project Structure

```
HR_AGENT/
├── main.py                    # CLI entry point
├── streamlit_app.py           # Streamlit UI (FSM)
├── hitl_bridge.py             # HITL queue bridge (thread-safe)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── ec2_setup.sh               # One-time EC2 setup script
│
├──src/hr_agent
        ├── config/
        │   └── settings.py            # All configuration (models, thresholds, SMTP)
        │
        ├── core/
        │   ├── llm.py                 # LLM instances (primary + fallback + structured outputs)
        │   ├── models.py              # Pydantic models with coerce_to_list validators
        │   └── state.py               # LangGraph GraphState TypedDict
        │
        ├── graph/
        │   └── pipeline.py            # LangGraph graph definition
        │
        ├── nodes/
        │   ├── resume_extractor.py
        │   ├── resume_scorer.py       # Rubric scoring with not_a_resume detection
        │   ├── profile_extractor.py   # GitHub repo fetching
        │   ├── synthesizer.py
        │   ├── final_review.py
        │   ├── github_scorer.py       # Seniority-aware GitHub scoring
        │   ├── decision_engine.py     # Smart routing logic
        │   ├── hitl_node.py           # CLI HITL (input())
        │   ├── email_nodes.py         # SMTP email sending
        │   └── workers/
        │       ├── base_worker.py     # Generic worker with per-worker caps
        │       ├── python_worker.py
        │       ├── readme_worker.py
        │       ├── infra_worker.py
        │       ├── config_worker.py
        │       └── notebook_worker.py
        │
        ├── tools/
        │   ├── github_client.py       # GitHub REST API client
        │   ├── resume_parser.py       # PDF + DOCX parser (handles table layouts)
        │   ├── input_validator.py     # Input sanitization and validation
        │   ├── helpers.py             # _extract_score, _extract_text, log_eval_event
        │   ├── llm_utils.py           # invoke_with_fallback
        │   └── logger.py              # structlog setup, PipelineStats, TokenLoggingCallback
        │
        └── .github/
            └── workflows/
                ├── ci.yml             # Lint + checks on every PR
                └── deploy.yml         # Build → ECR → EC2 on push to main
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- AWS account with Bedrock enabled
- GitHub personal access token
- Gmail account with App Password
- LangSmith account (optional)

### 1. Clone and install

```bash
git clone https://github.com/Mouli423/HR_AGENT.git
cd hr-agent
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# edit .env with your credentials
```

---

## ⚙️ Configuration

Create a `.env` file in the project root:

```env
# ── AWS ──────────────────────────────────────────────────────
# Not needed if running on EC2 with IAM role attached
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# ── GitHub ────────────────────────────────────────────────────
GITHUB_TOKEN=ghp_your_github_token

# ── Email (Gmail) ─────────────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=youremail@gmail.com
SMTP_PASSWORD=abcdefghijklmnop    # 16-char Gmail App Password

# ── LangSmith (optional) ──────────────────────────────────────
LANGSMITH_API_KEY=ls__your_key
LANGCHAIN_PROJECT=hr-agent-dev
```

### Scoring threshold

Edit `config/settings.py`:

```python
SCORE_THRESHOLD = 70   # candidates with both scores >= 70 are auto-selected
```

---

## ▶️ Running the App

### Streamlit UI

```bash
streamlit run streamlit_app.py
# visit http://localhost:8501
```

### CLI

Edit `main.py` with your JD, resume path, and role, then:

```bash
python main.py
```

---

## 🐳 Docker

### Local development

```bash
docker-compose up --build
# visit http://localhost:8501
```

### Build manually

```bash
docker build -t hr-agent .
docker run -p 8501:8501 --env-file .env hr-agent
```

---

## 🔄 CI/CD

Two GitHub Actions workflows:

**`ci.yml`** — runs on every PR and push to `main`:
- Ruff linting
- Syntax checks on all key files
- Pydantic model validation
- Input validator unit tests

**`deploy.yml`** — runs on push to `main`:
- Builds Docker image
- Pushes to Amazon ECR
- SSHes into EC2
- Pulls new image and restarts container
- Health check via `/_stcore/health`

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM user access key |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key |
| `AWS_REGION` | e.g. `us-east-1` |
| `ECR_REGISTRY` | e.g. `123456789.dkr.ecr.us-east-1.amazonaws.com` |
| `EC2_HOST` | EC2 public IP or DNS |
| `EC2_SSH_KEY` | Contents of your `.pem` key file |
| `GITHUB_TOKEN` | GitHub personal access token |
| `LANGSMITH_API_KEY` | LangSmith API key |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASSWORD` | Gmail App Password |

---

## ☁️ Deployment (AWS EC2)

### One-time EC2 setup

Launch a **t3.medium** with **Amazon Linux 2023**, attach an IAM role with:
- `AmazonBedrockFullAccess`
- `AmazonEC2ContainerRegistryReadOnly`

SSH in and run:

```bash
bash ec2_setup.sh us-east-1 123456789.dkr.ecr.us-east-1.amazonaws.com
```

### Security group

Open inbound:
- Port `8501` — restricted to your IP (Streamlit)
- Port `22` — restricted to your IP (SSH)

### Push to deploy

```bash
git push origin main
# GitHub Actions handles the rest
# App available at http://<ec2-ip>:8501
```

---

## 📊 Performance

Benchmarks from **91 production runs** on AWS Bedrock:

| Metric | Value |
|--------|-------|
| P50 latency | 81s |
| P95 latency | ~115s |
| P99 latency | 213s (includes HITL wait) |
| Avg tokens / run | ~88,000 |
| LLM cost / run | ~$0.032 |
| Monthly infra (100 candidates) | ~$33 |
| Monthly infra (500 candidates) | ~$46 |

**Latency breakdown (full GitHub run):**

```
Resume extraction + scoring  :  ~7s
GitHub profile fetch         : ~25s
Parallel workers (×5)        : ~15s
Synthesizer + final review   :  ~8s
GitHub scoring               :  ~4s
Decision + email             :  ~2s
─────────────────────────────────────
Total                        : ~61s pipeline + HITL wait
```

---

## 💰 ROI Analysis

Full analysis in [`HR_Agent_ROI_Analysis.docx`](./HR_Agent_ROI_Analysis.docx).

| Metric | Value |
|--------|-------|
| HR time saved | 98 hours/year (85% reduction) |
| Annual savings | $126,000+ |
| Cost per candidate | $0.33 |
| First-year ROI | 10×–56× |
| Payback period | < 1 month |

---

## 🔒 Security

- Input validation and prompt injection detection on all inputs
- Score manipulation attempts blocked in JD
- Non-resume documents detected and hard-rejected
- No credentials in code — all via environment variables
- EC2 security group restricts access to specific IPs
- Non-root Docker user

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👤 Author

Built by **Nagavenkatachandramouli Etamsetti**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue)](https://linkedin.com/in/moulimsd923)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-black)](https://github.com/Mouli423)