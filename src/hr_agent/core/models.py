from pydantic import BaseModel, Field, field_validator
from typing import List


# ── Shared coercion utility ────────────────────────────────────

def coerce_to_list(v) -> list:
    """
    Coerces any value the LLM might return into a clean List[str].
    Handles: list, dict, comma-separated string, or anything else.
    """
    if isinstance(v, list):
        return [str(i).strip() for i in v if str(i).strip()]
    if isinstance(v, dict):
        return [str(i).strip() for i in v.values() if str(i).strip()]
    if isinstance(v, str):
        return [i.strip() for i in v.split(",") if i.strip()]
    return []


# ── Resume models ─────────────────────────────────────────────

class ResumeExtractorOutput(BaseModel):
    candidate_name:  str = Field(description="Full name of the candidate")
    candidate_email: str = Field(description="Email address or empty string")
    github_url:      str = Field(description="GitHub profile URL or empty string")
    linkedin_url:    str = Field(description="LinkedIn profile URL or empty string")
    role_title:      str = Field(description=(
        "Most recent or target job title inferred from experience or objective. "
        "Examples: 'Junior AI Engineer', 'Data Analyst', 'Senior ML Engineer'"
    ))


class ResumeScoreOutput(BaseModel):
    not_a_resume:         bool      = Field(default=False, description="True if the document is not a resume")
    detected_seniority:   str       = Field(description="junior | mid | senior | founding")
    score_rationale:      str       = Field(description=(
        "Which rubric band was selected (e.g. Borderline 65-72) and the single "
        "most important reason for that band — state this BEFORE the score"
    ))
    score:                int        = Field(description="0-100")
    matched_skills:       List[str] = Field(default_factory=list)
    missing_skills:       List[str] = Field(default_factory=list)
    nice_to_have_matched: List[str] = Field(default_factory=list)
    seniority_alignment:  str       = Field(description="strong | partial | mismatch")
    domain_alignment:     str       = Field(description="strong | partial | mismatch")
    summary:              str       = Field(description="2-3 sentence assessment")

    @field_validator("matched_skills", "missing_skills", "nice_to_have_matched", mode="before")
    @classmethod
    def _coerce(cls, v): return coerce_to_list(v)


# ── Worker output models ───────────────────────────────────────

class PythonWorkerOutput(BaseModel):
    stack:            List[str] = Field(
        default_factory=list,
        description="Languages, frameworks, libraries explicitly imported e.g. ['LangChain', 'FastAPI', 'boto3']"
    )
    design_patterns:  List[str] = Field(
        default_factory=list,
        description="Architectural patterns observed e.g. ['RAG', 'agent loop', 'factory', 'retry']"
    )
    code_quality:     str       = Field(
        description="1-2 sentences on modularity, error handling, type hints, and test coverage"
    )
    maturity_signals: str       = Field(
        description="1-2 sentences on production-readiness — what is strong and what is missing"
    )
    cloud_platforms:  List[str] = Field(
        default_factory=list,
        description="Cloud services explicitly imported or referenced e.g. ['AWS Bedrock', 'S3', 'Lambda']"
    )

    @field_validator("stack", "design_patterns", "cloud_platforms", mode="before")
    @classmethod
    def _coerce(cls, v): return coerce_to_list(v)


class ReadmeWorkerOutput(BaseModel):
    project_summaries:      List[str] = Field(
        default_factory=list,
        description="One line per repo: '<repo_name>: what it does'"
    )
    technologies_mentioned: List[str] = Field(
        default_factory=list,
        description="Technologies explicitly named in the documentation"
    )
    documentation_quality:  str       = Field(
        description="1 sentence on README completeness — setup instructions, architecture explanation, usage examples"
    )

    @field_validator("project_summaries", "technologies_mentioned", mode="before")
    @classmethod
    def _coerce(cls, v): return coerce_to_list(v)


class InfraWorkerOutput(BaseModel):
    containerisation: List[str] = Field(
        default_factory=list,
        description="Docker, Kubernetes, compose files found e.g. ['Dockerfile', 'docker-compose.yml']"
    )
    ci_cd:            List[str] = Field(
        default_factory=list,
        description="CI/CD tools and pipeline files found e.g. ['GitHub Actions', '.github/workflows']"
    )
    cloud_services:   List[str] = Field(
        default_factory=list,
        description="Cloud services configured in infra files e.g. ['AWS Lambda', 'S3', 'ECR']"
    )
    deployment_gaps:  str       = Field(
        description="1 sentence on missing production infrastructure e.g. no IaC, no health checks, no secrets management"
    )

    @field_validator("containerisation", "ci_cd", "cloud_services", mode="before")
    @classmethod
    def _coerce(cls, v): return coerce_to_list(v)


class ConfigWorkerOutput(BaseModel):
    secret_management: str       = Field(
        description="1 sentence on how secrets and env vars are handled e.g. dotenv, SSM, hardcoded"
    )
    config_tools:      List[str] = Field(
        default_factory=list,
        description="Config tools found e.g. ['dotenv', 'configparser', 'AWS SSM']"
    )
    hardcoded_risks:   List[str] = Field(
        default_factory=list,
        description="Hardcoded values that are security or config risks e.g. ['AWS region', 'model IDs', 'bucket names']"
    )

    @field_validator("config_tools", "hardcoded_risks", mode="before")
    @classmethod
    def _coerce(cls, v): return coerce_to_list(v)


class NotebookWorkerOutput(BaseModel):
    topics:                List[str] = Field(
        default_factory=list,
        description="ML/AI topics covered e.g. ['RAG', 'fine-tuning', 'embeddings', 'classification']"
    )
    libraries:             List[str] = Field(
        default_factory=list,
        description="Libraries imported in notebooks e.g. ['sklearn', 'transformers', 'LangChain']"
    )
    experimentation_depth: str       = Field(
        description="1 sentence: exploratory demo vs structured experiment with evaluation"
    )

    @field_validator("topics", "libraries", mode="before")
    @classmethod
    def _coerce(cls, v): return coerce_to_list(v)


# ── GitHub scoring models ──────────────────────────────────────

class GitHubScoreOutput(BaseModel):
    detected_seniority: str       = Field(description="junior | mid | senior | founding")
    score_rationale:    str       = Field(description=(
        "Which rubric band was selected (e.g. Strong 73-84) and the single "
        "most important reason for that band — state this BEFORE the score"
    ))
    score:              int        = Field(description="0-100")
    relevant_projects:  List[str] = Field(default_factory=list)
    originality_signal: str       = Field(description="high | medium | low")
    summary:            str       = Field(description="2-3 sentence assessment")

    @field_validator("relevant_projects", mode="before")
    @classmethod
    def _coerce(cls, v): return coerce_to_list(v)


# ── Synthesizer & final review models ─────────────────────────

class SynthesizerOutput(BaseModel):
    technical_stack:       str = Field(description="Comma-separated list of all confirmed technologies across all workers")
    project_highlights:    str = Field(description="2-3 sentences on the most technically significant projects")
    engineering_practices: str = Field(description="2-3 sentences on code quality, testing, CI/CD, deployment evidence")
    strengths:             str = Field(description="2-3 sentences on strongest and most consistent technical signals")
    concerns:              str = Field(description="2-3 sentences on gaps, risks, or weak areas observed across workers")
    overall_profile:       str = Field(description="2-3 sentence overall technical summary for the decision engine")


class FinalReviewOutput(BaseModel):
    candidate_summary:   str = Field(description="Who this candidate is technically")
    role_fit_assessment: str = Field(description="How well they fit the specific JD")
    key_evidence:        str = Field(description="Concrete GitHub evidence supporting assessment")
    recommendation:      str = Field(description="Clear recommendation for decision engine")