from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


# ── Request models ───────────────────────────────────────────

class GenerateRequest(BaseModel):
    task_description: str = Field(..., min_length=5, description="The task to generate Python code for")
    model: str | None = Field(None, description="Override default Groq model")


class ExecuteRequest(BaseModel):
    attempt_number: int | None = Field(None, description="Optional attempt number to execute (defaults to latest)")
    code_override: str | None = Field(None, description="Execute arbitrary code within the run context")


class GenerateAndRepairRequest(BaseModel):
    task_description: str = Field(..., min_length=5)
    max_attempts: int = Field(3, ge=1, le=10, description="Maximum repair attempts")
    model: str | None = None
    skip_agents: list[str] = Field(
        default_factory=list,
        description="Skip any review agent: 'test', 'performance', 'security_audit', 'docs'",
    )


class EvalRunRequest(BaseModel):
    benchmark: str = Field("humaneval", description="'humaneval' or 'custom'")
    subset_size: int | None = Field(50, description="Number of problems to evaluate (default 50)")
    skip_agents: list[str] = Field(default_factory=list)


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
    generated_tests: str | None = None
    performance_notes: str | None = None
    security_audit: str | None = None
    quality_overall_score: float | None = None
    quality_report_json: str | None = None
    timestamp: str | datetime | None = None


class RunOut(BaseModel):
    run_id: str
    task_description: str
    created_at: str | datetime | None = None
    final_status: str
    total_attempts: int
    attempts: list[AttemptOut] = []


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
