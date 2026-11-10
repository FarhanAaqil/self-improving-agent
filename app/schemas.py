from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.config import AVAILABLE_MODELS

MAX_TASK_CHARS = 4000
MAX_CODE_CHARS = 50_000

ReviewAgent = Literal[
    "critique", "test", "tests", "mutation", "performance", "security_audit", "security", "docs", "documentation"
]


def _check_model(value: str | None) -> str | None:
    if value is not None and value not in AVAILABLE_MODELS:
        raise ValueError(f"Unknown model '{value}'. Choose one of: {', '.join(AVAILABLE_MODELS)}")
    return value

# ── Request models ───────────────────────────────────────────

class GenerateRequest(BaseModel):
    task_description: str = Field(
        ..., min_length=5, max_length=MAX_TASK_CHARS, description="The task to generate Python code for"
    )
    model: str | None = Field(None, description="Override default Groq model")

    @field_validator("model")
    @classmethod
    def _model_ok(cls, value: str | None) -> str | None:
        return _check_model(value)


class ExecuteRequest(BaseModel):
    attempt_number: int | None = Field(
        None, ge=1, description="Optional attempt number to execute (defaults to latest)"
    )
    code_override: str | None = Field(
        None,
        max_length=MAX_CODE_CHARS,
        description="Execute caller-supplied code (requires ALLOW_CODE_OVERRIDE=true on the server)",
    )


class GenerateAndRepairRequest(BaseModel):
    task_description: str = Field(..., min_length=5, max_length=MAX_TASK_CHARS)
    max_attempts: int = Field(3, ge=1, le=10, description="Maximum repair attempts")
    model: str | None = None
    skip_agents: list[ReviewAgent] = Field(
        default_factory=list,
        max_length=8,
        description="Skip any review agent: 'critique', 'test', 'performance', 'security_audit', 'docs'",
    )

    @field_validator("model")
    @classmethod
    def _model_ok(cls, value: str | None) -> str | None:
        return _check_model(value)


class CompareRequest(GenerateAndRepairRequest):
    models: list[str] = Field(..., min_length=2, max_length=4, description="Models to race on the same task")

    @field_validator("models")
    @classmethod
    def _models_ok(cls, value: list[str]) -> list[str]:
        for model in value:
            _check_model(model)
        if len(set(value)) != len(value):
            raise ValueError("Each model may appear once.")
        return value


class EvalRunRequest(BaseModel):
    benchmark: Literal["humaneval"] = Field("humaneval", description="Benchmark to run")
    subset_size: int = Field(10, ge=1, le=50, description="Number of problems to evaluate")


# ── Response models ──────────────────────────────────────────

class GenerateOut(BaseModel):
    run_id: str
    code: str
    model: str


class ExecuteOut(BaseModel):
    run_id: str
    attempt_number: int
    success: bool
    output: str | None = None
    error: str | None = None
    exit_code: int | None = None
    latency_ms: int | None = None
    sandboxed: bool = True


class AttemptOut(BaseModel):
    attempt_id: int | None = None
    attempt_number: int
    generated_code: str
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    success: bool
    latency_ms: int | None = None
    tokens_used: int | None = None
    model_name: str | None = None
    critique_confidence: float | None = None
    critique_reasoning: str | None = None
    generated_tests: str | None = None
    performance_notes: str | None = None
    security_audit: str | None = None
    quality_overall_score: float | None = None
    quality_report_json: str | None = None
    tests_passed: int | None = None
    tests_total: int | None = None
    coverage: float | None = None
    test_report_json: str | None = None
    diagnosis_json: str | None = None
    sandboxed: bool | None = None
    timestamp: str | datetime | None = None


class RunOut(BaseModel):
    run_id: str
    task_description: str
    created_at: str | datetime | None = None
    final_status: str
    total_attempts: int
    model_name: str | None = None
    memories: list[dict[str, Any]] = []
    spec_tests: str | None = None
    final_code: str | None = None
    docs_applied: bool | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finished_at: str | datetime | None = None
    group_id: str | None = None
    attempts: list[AttemptOut] = []


class RunAccepted(BaseModel):
    run_id: str
    status: str = "queued"
    events_url: str


class RunSummary(BaseModel):
    run_id: str
    task_description: str
    created_at: str | datetime | None = None
    final_status: str
    total_attempts: int
    model_name: str | None = None
    passed_on_attempt: int | None = None
    quality_score: float | None = None
    total_latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finished_at: str | datetime | None = None
    group_id: str | None = None


class RunPage(BaseModel):
    items: list[RunSummary]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = {}


class EvalResultOut(BaseModel):
    eval_id: str
    benchmark_name: str
    pass_at_1: float | None = None
    pass_at_5: float | None = None
    avg_attempts: float | None = None
    avg_latency_ms: float | None = None
    total_problems: int | None = None
    run_at: str | datetime | None = None
    raw: dict[str, Any] | None = None


class EvalRunOut(BaseModel):
    eval_id: str
    status: str = "started"
    message: str = "Evaluation run started in background."
