# ── app/schemas.py ──────────────────────────────────────────
# Pydantic request/response models for all 6 FastAPI endpoints.
# Placeholder for Day 1 — fleshed out with real validation on Day 4.

from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


# ── Request models ───────────────────────────────────────────

class GenerateRequest(BaseModel):
    task_description: str = Field(..., min_length=10, description="The task to generate Python code for")
    model: str | None = Field(None, description="Override the default Groq model")


class GenerateAndRepairRequest(BaseModel):
    task_description: str = Field(..., min_length=10)
    max_attempts: int = Field(3, ge=1, le=10, description="Maximum repair attempts")
    model: str | None = None
    skip_agents: list[str] = Field(
        default_factory=list,
        description="Skip any of: 'test', 'performance', 'security_audit', 'docs'",
    )


class EvalRunRequest(BaseModel):
    benchmark: str = Field("humaneval", description="'humaneval' or 'custom'")
    subset_size: int | None = Field(None, description="Limit problems (e.g. 50 for smoke run)")
    skip_agents: list[str] = Field(default_factory=list)


# ── Attempt response ─────────────────────────────────────────

class AttemptOut(BaseModel):
    attempt_id: int
    attempt_number: int
    generated_code: str
    stdout: str | None
    stderr: str | None
    exit_code: int | None
    success: bool
    latency_ms: int | None
    tokens_used: int | None
    model_name: str | None
    critique_confidence: float | None
    generated_tests: str | None
    performance_notes: str | None
    security_audit: str | None
    quality_overall_score: float | None
    quality_report_json: str | None
    timestamp: datetime | None


# ── Run response ─────────────────────────────────────────────

class RunOut(BaseModel):
    run_id: str
    task_description: str
    created_at: datetime | None
    final_status: str   # success | failed | max_retries_exceeded | running
    total_attempts: int
    attempts: list[AttemptOut] = []


# ── Generate response (no attempts yet — just the first code) ─

class GenerateOut(BaseModel):
    run_id: str
    code: str


# ── Eval response ─────────────────────────────────────────────

class EvalResultOut(BaseModel):
    eval_id: str
    benchmark_name: str
    pass_at_1: float | None
    pass_at_5: float | None
    avg_attempts: float | None
    avg_latency_ms: float | None
    total_problems: int | None
    run_at: datetime | None
    raw: dict[str, Any] | None = None   # full JSON from results/*.json


class EvalRunOut(BaseModel):
    eval_id: str
    status: str = "started"
    message: str = "Eval run triggered. Poll /eval/latest for results."
