import asyncio
import glob
import json
import logging
import os
import secrets
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import db, llm
from app.certificate import badge_svg, build_certificate
from app.config import (
    ALLOW_BYO_GROQ_KEY,
    ALLOW_CODE_OVERRIDE,
    ALLOW_UNSAFE_HOST_SUBPROCESS,
    ALLOWED_ORIGINS,
    AVAILABLE_MODELS,
    DAILY_TOKEN_BUDGET,
    DEMO_MODE,
    MEMORY_ENABLED,
    MODEL,
    RESULTS_DIR,
    SANDBOX_TIMEOUT,
)
from app.generator import generate_code
from app.jobs import recover_interrupted_runs, submit_run
from app.observability import configure_logging, metrics, new_request_id, request_id
from app.pipeline import RunSpec, execute_run
from app.sandbox import SANDBOX_IMAGE, _is_docker_available, docker_run_args, run_code
from app.schemas import (
    CompareRequest,
    EvalResultOut,
    EvalRunOut,
    EvalRunRequest,
    ExecuteOut,
    ExecuteRequest,
    GenerateAndRepairRequest,
    GenerateOut,
    GenerateRequest,
    RunAccepted,
    RunOut,
    RunPage,
)
from app.security import auth_mode, groq_key_of, rate_limited, verify_api_access, workspace_of

logger = logging.getLogger("self_improving_agent")
configure_logging()

VERSION = "2.0.0"
TERMINAL_STATUSES = {"success", "failed", "max_retries_exceeded", "early_stopped"}

# Ensure SQLite tables exist immediately upon import (TestClient skips lifespan)
db.init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    interrupted = recover_interrupted_runs()
    if interrupted:
        logger.warning("Marked %d interrupted run(s) as failed", interrupted)
    yield


app = FastAPI(
    title="Self-Improving Code Agent API",
    description="Backend API powering the sandboxed, self-repairing code generation agent.",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # auth is header-based; cookies are never needed
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization", "Last-Event-ID"],
)


_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_API_DOC_PATHS = ("/docs", "/redoc", "/openapi.json", "/assets/")


def _wants_app_shell(request: Request) -> bool:
    """A browser navigation (Accept: text/html) gets the React app, even on paths like
    /runs/{id} or /memory that are also API routes. fetch() calls never send text/html."""
    return (
        request.method == "GET"
        and "text/html" in request.headers.get("accept", "")
        and not request.url.path.startswith(_API_DOC_PATHS)
        and Path(request.url.path).suffix == ""
        and (_FRONTEND_DIST / "index.html").exists()
    )


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    rid = new_request_id(request.headers.get("x-request-id"))
    token = request_id.set(rid)
    started = time.monotonic()
    try:
        if _wants_app_shell(request):
            response = FileResponse(str(_FRONTEND_DIST / "index.html"))
        else:
            response = await call_next(request)
    finally:
        request_id.reset(token)
    route = request.scope.get("route")
    path = getattr(route, "path", "unmatched")
    metrics.inc("agent_http_requests_total", method=request.method, route=path, status=str(response.status_code))
    metrics.inc("agent_http_request_seconds_sum", time.monotonic() - started, route=path)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # The same URL can be a page (Accept: text/html) or JSON, so caches must key on Accept,
    # and the app shell itself must never be reused as an API response.
    response.headers["Vary"] = "Accept"
    if request.url.path.startswith(
        ("/generate", "/execute", "/runs", "/eval", "/memory", "/compare", "/shared", "/usage", "/stats", "/metrics")
    ) or _wants_app_shell(request):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


def _run_out(run: dict) -> RunOut:
    memories = []
    if run.get("memories_json"):
        try:
            memories = json.loads(run["memories_json"])
        except ValueError:
            memories = []
    return RunOut(**{**run, "memories": memories})


def _load_run(run_id: str, request: Request | None = None) -> dict:
    run = db.get_run_with_attempts(run_id)
    # Another workspace's run looks exactly like a missing one
    if not run or (request is not None and (run.get("workspace") or "default") != workspace_of(request)):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return run


def _check_budget(request: Request) -> None:
    if DAILY_TOKEN_BUDGET <= 0:
        return
    spent = db.tokens_today(workspace_of(request))
    if spent >= DAILY_TOKEN_BUDGET:
        raise HTTPException(
            status_code=429,
            detail=f"Daily token budget reached ({spent:,} of {DAILY_TOKEN_BUDGET:,}). It resets at midnight UTC.",
        )


# ── System ───────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health_check():
    from app.github_agent import IS_GITHUB_CONFIGURED

    return {
        "status": "healthy",
        "version": VERSION,
        "docker_available": _is_docker_available(),
        "demo_mode": DEMO_MODE,
        "github_configured": IS_GITHUB_CONFIGURED,
        "auth": auth_mode(),
        "code_override_enabled": ALLOW_CODE_OVERRIDE,
        "memory_enabled": MEMORY_ENABLED,
        "byo_groq_key": ALLOW_BYO_GROQ_KEY,
        "daily_token_budget": DAILY_TOKEN_BUDGET,
        "models": AVAILABLE_MODELS,
        "default_model": MODEL,
    }


@app.get("/models", tags=["System"])
def list_models():
    return {"default": MODEL, "models": AVAILABLE_MODELS}


@app.get("/sandbox/config", tags=["System"])
def sandbox_config():
    """The exact docker command every snippet runs under, so the UI never overclaims."""
    return {
        "docker_available": _is_docker_available(),
        "image": SANDBOX_IMAGE,
        "timeout_seconds": SANDBOX_TIMEOUT,
        "command": docker_run_args("sandbox-<id>"),
        "host_fallback_enabled": ALLOW_UNSAFE_HOST_SUBPROCESS,
    }


@app.get("/sandbox/attacks", tags=["System"])
def sandbox_attacks():
    from app.attacks import list_attacks

    return {"items": list_attacks()}


@app.post(
    "/sandbox/attacks/{name}",
    dependencies=[Depends(verify_api_access), Depends(rate_limited)],
    tags=["System"],
)
def sandbox_attack(name: str):
    """Run one of the curated adversarial scripts against the live sandbox."""
    from app.attacks import run_attack

    if not _is_docker_available():
        raise HTTPException(status_code=503, detail="Docker is not available on this server.")
    result = run_attack(name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown attack '{name}'.")
    return result


# ── Generate only ────────────────────────────────────────────

@app.post(
    "/generate",
    response_model=GenerateOut,
    dependencies=[Depends(verify_api_access), Depends(rate_limited)],
    tags=["Agent"],
)
def generate_endpoint(req: GenerateRequest, request: Request):
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    model_name = req.model or MODEL
    _check_budget(request)

    try:
        with llm.groq_key(groq_key_of(request)):
            code = generate_code(req.task_description, model=model_name)
    except Exception as e:
        logger.error("LLM generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail="The language model call failed. Try again shortly.")

    db.insert_run(run_id, req.task_description, final_status="generated", total_attempts=1)
    db.update_run(run_id, model_name=model_name, workspace=workspace_of(request))
    db.insert_attempt(run_id=run_id, attempt_number=1, generated_code=code, model_name=model_name, success=False)
    return GenerateOut(run_id=run_id, code=code, model=model_name)


# ── Execute existing code ───────────────────────────────────

@app.post(
    "/execute/{run_id}",
    response_model=ExecuteOut,
    dependencies=[Depends(verify_api_access), Depends(rate_limited)],
    tags=["Agent"],
)
def execute_endpoint(run_id: str, request: Request, req: Optional[ExecuteRequest] = None):
    run = _load_run(run_id, request)
    attempts = run.get("attempts", [])
    # Every execution is recorded as a brand-new attempt, never reusing a number
    attempt_num = max((a["attempt_number"] for a in attempts), default=0) + 1

    if req and req.code_override:
        if not ALLOW_CODE_OVERRIDE:
            raise HTTPException(
                status_code=403,
                detail="code_override is disabled on this server (ALLOW_CODE_OVERRIDE=false).",
            )
        code_to_run = req.code_override
    elif attempts:
        if req and req.attempt_number:
            source = next((a for a in attempts if a["attempt_number"] == req.attempt_number), None)
            if source is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Attempt {req.attempt_number} does not exist in run '{run_id}'.",
                )
        else:
            source = attempts[-1]
        code_to_run = source["generated_code"]
    else:
        raise HTTPException(status_code=422, detail="No code found in this run to execute.")

    result = run_code(code_to_run, timeout=SANDBOX_TIMEOUT)
    db.insert_attempt(
        run_id=run_id,
        attempt_number=attempt_num,
        generated_code=code_to_run,
        stdout=result.get("output"),
        stderr=result.get("error"),
        exit_code=result.get("exit_code"),
        success=result["success"],
        latency_ms=result.get("latency_ms", 0),
        sandboxed=result.get("sandboxed"),
    )
    db.update_run_status(
        run_id, final_status="success" if result["success"] else "failed", total_attempts=attempt_num
    )

    return ExecuteOut(
        run_id=run_id,
        attempt_number=attempt_num,
        success=result["success"],
        output=result.get("output"),
        error=result.get("error"),
        exit_code=result.get("exit_code"),
        latency_ms=result.get("latency_ms"),
        sandboxed=result.get("sandboxed", False),
    )


# ── Full pipeline ────────────────────────────────────────────

def _spec(req: GenerateAndRepairRequest, request: Request, model: str | None = None) -> RunSpec:
    return RunSpec(
        task=req.task_description,
        model=model or req.model or MODEL,
        max_attempts=req.max_attempts,
        skip_agents=list(req.skip_agents),
        workspace=workspace_of(request),
        groq_key=groq_key_of(request),
    )


def _new_run(spec: RunSpec, group_id: str | None = None) -> str:
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    db.insert_run(run_id, spec.task, final_status="queued")
    db.update_run(run_id, model_name=spec.model, workspace=spec.workspace, group_id=group_id)
    return run_id


@app.post(
    "/generate-and-repair",
    response_model=RunOut,
    dependencies=[Depends(verify_api_access), Depends(rate_limited)],
    tags=["Agent"],
)
def generate_and_repair_endpoint(req: GenerateAndRepairRequest, request: Request):
    """Synchronous version: blocks until the run finishes. Prefer POST /runs for UIs."""
    _check_budget(request)
    spec = _spec(req, request)
    run_id = _new_run(spec)
    execute_run(run_id, spec)
    return _run_out(_load_run(run_id, request))


@app.post(
    "/runs",
    response_model=RunAccepted,
    status_code=202,
    dependencies=[Depends(verify_api_access), Depends(rate_limited)],
    tags=["Runs"],
)
def create_run(req: GenerateAndRepairRequest, request: Request):
    """Start a run in the background and return immediately; follow it via /runs/{id}/events."""
    _check_budget(request)
    spec = _spec(req, request)
    run_id = _new_run(spec)
    submit_run(run_id, spec)
    return RunAccepted(run_id=run_id, events_url=f"/runs/{run_id}/events")


@app.post(
    "/compare",
    status_code=202,
    dependencies=[Depends(verify_api_access), Depends(rate_limited)],
    tags=["Runs"],
)
def compare_models(req: CompareRequest, request: Request):
    """Run the same task on several models side by side; follow with GET /compare/{group_id}."""
    _check_budget(request)
    group_id = f"cmp_{uuid.uuid4().hex[:8]}"
    runs = []
    for model in req.models:
        spec = _spec(req, request, model=model)
        run_id = _new_run(spec, group_id=group_id)
        submit_run(run_id, spec)
        runs.append({"run_id": run_id, "model": model})
    return {"group_id": group_id, "runs": runs}


@app.get("/compare/{group_id}", dependencies=[Depends(verify_api_access)], tags=["Runs"])
def get_comparison(group_id: str, request: Request):
    runs = db.list_group_runs(group_id, workspace=workspace_of(request))
    if not runs:
        raise HTTPException(status_code=404, detail=f"Comparison '{group_id}' not found.")
    return {"group_id": group_id, "task": runs[0]["task_description"], "runs": runs}


@app.get("/runs", response_model=RunPage, dependencies=[Depends(verify_api_access)], tags=["Runs"])
def list_runs_endpoint(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None, max_length=200),
    status: Optional[str] = Query(None, pattern="^(success|failed|early_stopped|running)$"),
):
    return db.list_run_summaries(page=page, page_size=page_size, q=q, status=status, workspace=workspace_of(request))


@app.get(
    "/runs/{run_id}",
    response_model=RunOut,
    dependencies=[Depends(verify_api_access)],
    tags=["Runs"],
)
def get_run_endpoint(run_id: str, request: Request):
    return _run_out(_load_run(run_id, request))


@app.get("/runs/{run_id}/certificate", dependencies=[Depends(verify_api_access)], tags=["Runs"])
def run_certificate(run_id: str, request: Request):
    """A portable, optionally HMAC-signed record of what was verified and under which sandbox."""
    certificate = build_certificate(_load_run(run_id, request))
    if certificate is None:
        raise HTTPException(status_code=409, detail="Only verified runs get a certificate.")
    return certificate


def _badge(run: dict | None) -> Response:
    if run and run.get("final_status") == "success":
        passing = next((a for a in run["attempts"] if a.get("success")), {})
        detail = f"{passing.get('tests_passed')}/{passing.get('tests_total')} tests" if passing.get("tests_total") else ""
        svg = badge_svg("verified", detail)
    else:
        svg = badge_svg("unverified", "")
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "no-cache"})


@app.post("/runs/{run_id}/share", dependencies=[Depends(verify_api_access)], tags=["Runs"])
def share_run(run_id: str, request: Request):
    """Create (or return) a read-only public link for this run."""
    run = _load_run(run_id, request)
    token = run.get("share_token") or secrets.token_urlsafe(16)
    db.update_run(run_id, share_token=token)
    return {"token": token, "url": f"/shared/{token}", "badge": f"/shared/{token}/badge.svg"}


@app.delete("/runs/{run_id}/share", dependencies=[Depends(verify_api_access)], tags=["Runs"])
def unshare_run(run_id: str, request: Request):
    _load_run(run_id, request)
    db.update_run(run_id, share_token=None)
    return {"shared": False}


@app.get("/shared/{token}", tags=["Runs"])
def get_shared_run(token: str):
    """Public, read-only view of a run its owner chose to share."""
    run = db.get_run_by_share_token(token) if len(token) <= 64 else None
    if not run:
        raise HTTPException(status_code=404, detail="This share link doesn't exist or was revoked.")
    out = _run_out(run).model_dump()
    out["certificate"] = build_certificate(run)
    return out


@app.get("/shared/{token}/badge.svg", tags=["Runs"])
def shared_badge(token: str):
    return _badge(db.get_run_by_share_token(token) if len(token) <= 64 else None)


def _sse(event_id: int, event_type: str, payload: dict) -> str:
    return f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


@app.get("/runs/{run_id}/events", dependencies=[Depends(verify_api_access)], tags=["Runs"])
async def run_events(run_id: str, request: Request, after: int = Query(0, ge=0)):
    """Server-sent events for a run. Replays history, then streams until the run finishes."""
    owner = await asyncio.to_thread(db.run_workspace, run_id)
    if owner is None or owner != workspace_of(request):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    header = request.headers.get("last-event-id", "")
    start = int(header) if header.isdigit() else after

    async def stream():
        last, quiet = start, 0.0
        while not await request.is_disconnected():
            events = await asyncio.to_thread(db.get_events, run_id, last)
            for event in events:
                last = event["event_id"]
                yield _sse(last, event["type"], event["payload"])
                if event["type"] == "run_finished":
                    return
            if not events:
                run = await asyncio.to_thread(db.get_run, run_id)
                if run and run["final_status"] in TERMINAL_STATUSES:
                    # Older runs (or ones finished without events) still get a clean ending
                    yield _sse(last, "run_finished", {"status": run["final_status"]})
                    return
                quiet += 0.5
                if quiet >= 15:
                    quiet = 0.0
                    yield ": keep-alive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


# ── PR automation ────────────────────────────────────────────

@app.post(
    "/runs/{run_id}/pr",
    dependencies=[Depends(verify_api_access), Depends(rate_limited)],
    tags=["Runs"],
)
def create_pull_request_endpoint(run_id: str, request: Request, repo: Optional[str] = None):
    from app.github_agent import open_pull_request_for_run

    _load_run(run_id, request)
    result = open_pull_request_for_run(run_id=run_id, repo=repo)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


# ── Memory ───────────────────────────────────────────────────

def _memory_or_503():
    if not MEMORY_ENABLED:
        raise HTTPException(status_code=503, detail="Vector memory is disabled on this server.")
    from app import memory

    return memory


@app.get("/memory", dependencies=[Depends(verify_api_access)], tags=["Memory"])
def list_memory(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    kind: Optional[str] = Query(None, pattern="^(failure|fix)$"),
):
    return _memory_or_503().list_memories(limit=limit, offset=offset, kind=kind, workspace=workspace_of(request))


@app.get("/memory/stats", dependencies=[Depends(verify_api_access)], tags=["Memory"])
def memory_stats(request: Request):
    return _memory_or_503().memory_stats(workspace=workspace_of(request))


@app.get("/memory/search", dependencies=[Depends(verify_api_access)], tags=["Memory"])
def search_memory(
    request: Request,
    q: str = Query(..., min_length=3, max_length=500),
    threshold: float = Query(0.3, ge=0.0, le=1.0),
):
    """What does the agent remember about this? Uses a looser threshold than generation."""
    memory = _memory_or_503()
    return {
        "items": memory.retrieve_similar_failures(
            q, top_k=10, similarity_threshold=threshold, workspace=workspace_of(request)
        )
    }


@app.delete("/memory/{memory_id}", dependencies=[Depends(verify_api_access)], tags=["Memory"])
def delete_memory(memory_id: str, request: Request):
    if not _memory_or_503().delete_memory(memory_id, workspace=workspace_of(request)):
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"deleted": memory_id}


@app.post("/memory/{memory_id}/pin", dependencies=[Depends(verify_api_access)], tags=["Memory"])
def pin_memory(memory_id: str, request: Request, pinned: bool = True):
    if not _memory_or_503().set_pinned(memory_id, pinned, workspace=workspace_of(request)):
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"id": memory_id, "pinned": pinned}


# ── Insight ──────────────────────────────────────────────────

@app.get("/usage", dependencies=[Depends(verify_api_access)], tags=["Insight"])
def usage(request: Request):
    spent = db.tokens_today(workspace_of(request))
    return {
        "workspace": workspace_of(request),
        "tokens_today": spent,
        "daily_budget": DAILY_TOKEN_BUDGET or None,
        "remaining": max(0, DAILY_TOKEN_BUDGET - spent) if DAILY_TOKEN_BUDGET else None,
    }


@app.get("/stats/improvement", dependencies=[Depends(verify_api_access)], tags=["Insight"])
def improvement(request: Request, days: int = Query(60, ge=7, le=365)):
    """Is the agent getting better? Daily first-try and solve rates, and the effect of memory."""
    ws = workspace_of(request)
    daily = db.run_stats_by_day(days=days, workspace=ws)
    for row in daily:
        row["first_try_rate"] = round(row["first_try"] / row["runs"], 3) if row["runs"] else None
        row["solve_rate"] = round(row["solved"] / row["runs"], 3) if row["runs"] else None
    return {"daily": daily, "memory_effect": db.memory_effect(workspace=ws)}


@app.get("/metrics", dependencies=[Depends(verify_api_access)], tags=["Insight"], include_in_schema=False)
def prometheus_metrics():
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")


# ── Evaluation ───────────────────────────────────────────────

_eval_progress: dict[str, dict] = {}
_eval_lock = threading.Lock()


def _result_files() -> list[dict]:
    """Committed result JSONs (top level only; results/legacy is ignored)."""
    out = []
    for path in glob.glob(os.path.join(RESULTS_DIR, "*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if "agent" in data and "baseline" in data:
            out.append(data)
    return out


def _all_evals() -> list[dict]:
    """Every known eval, newest first by its recorded run time (not by file name)."""
    with db.get_connection() as conn:
        rows = conn.execute("SELECT raw_json FROM eval_runs ORDER BY run_at DESC LIMIT 50").fetchall()
    evals, seen = [], set()
    for row in rows:
        try:
            data = json.loads(row["raw_json"] or "{}")
        except ValueError:
            continue
        if "agent" in data:
            evals.append(data)
            seen.add(data.get("eval_id"))
    evals += [d for d in _result_files() if d.get("eval_id") not in seen]
    return sorted(evals, key=lambda d: d.get("run_at", ""), reverse=True)


def _eval_out(data: dict) -> EvalResultOut:
    return EvalResultOut(
        eval_id=data.get("eval_id", "unknown"),
        benchmark_name=data.get("benchmark", "humaneval"),
        pass_at_1=data.get("pass_at_1"),
        pass_at_5=data.get("pass_at_5"),
        avg_attempts=data.get("avg_attempts"),
        avg_latency_ms=data.get("avg_latency_ms"),
        total_problems=data.get("total_problems"),
        run_at=data.get("run_at"),
        raw=data,
    )


@app.get("/eval/latest", response_model=EvalResultOut, tags=["Evaluation"])
def get_latest_eval_endpoint():
    evals = _all_evals()
    if evals:
        return _eval_out(evals[0])
    return EvalResultOut(
        eval_id="none",
        benchmark_name="humaneval",
        pass_at_1=0.0,
        pass_at_5=0.0,
        avg_attempts=0.0,
        avg_latency_ms=0.0,
        total_problems=0,
        raw={"message": "No evaluations executed yet. Run POST /eval/run to trigger."},
    )


@app.get("/eval/history", tags=["Evaluation"])
def eval_history(limit: int = Query(20, ge=1, le=50)):
    return {"items": [{k: v for k, v in d.items() if k != "results"} for d in _all_evals()[:limit]]}


@app.get("/eval/status/{eval_id}", tags=["Evaluation"])
def eval_status(eval_id: str):
    with _eval_lock:
        state = _eval_progress.get(eval_id)
    if not state:
        raise HTTPException(status_code=404, detail="Unknown or expired evaluation id.")
    return state


def _run_eval_job(eval_id: str, benchmark: str, subset_size: int):
    from eval.benchmark import run_benchmark, save_results

    def progress(done: int, total: int, record: dict):
        with _eval_lock:
            state = _eval_progress[eval_id]
            state.update(done=done, total=total)
            state["recent"] = ([{"id": record["problem_id"], "passed": record["passed"]}] + state["recent"])[:12]

    with _eval_lock:
        _eval_progress[eval_id] = {
            "eval_id": eval_id, "status": "running", "done": 0, "total": subset_size, "recent": [],
        }
    try:
        summary = run_benchmark(suite=benchmark, limit=subset_size, eval_id=eval_id, progress=progress)
        db.insert_eval_run(
            eval_id=eval_id,
            benchmark_name=benchmark,
            pass_at_1=summary["pass_at_1"],
            pass_at_5=summary["pass_at_5"],
            avg_attempts=summary["avg_attempts"],
            avg_latency_ms=summary["avg_latency_ms"],
            total_problems=summary["total_problems"],
            raw_json=json.dumps(summary),
        )
        save_results(summary)
        with _eval_lock:
            _eval_progress[eval_id]["status"] = "done"
    except Exception as e:
        logger.error("Eval background job %s failed: %s", eval_id, e, exc_info=True)
        with _eval_lock:
            _eval_progress[eval_id].update(status="failed", error=str(e)[:300])


@app.post(
    "/eval/run",
    response_model=EvalRunOut,
    dependencies=[Depends(verify_api_access), Depends(rate_limited)],
    tags=["Evaluation"],
)
def run_eval_endpoint(req: EvalRunRequest):
    eval_id = f"{req.benchmark}_{uuid.uuid4().hex[:8]}"
    threading.Thread(
        target=_run_eval_job, args=(eval_id, req.benchmark, req.subset_size), daemon=True
    ).start()
    return EvalRunOut(
        eval_id=eval_id,
        status="started",
        message=f"Evaluation {eval_id} started on {req.subset_size} {req.benchmark} problems.",
    )


# ── Frontend Static Files Mount ──────────────────────────────
if _FRONTEND_DIST.exists():
    _assets_dir = _FRONTEND_DIST / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        dist_root = _FRONTEND_DIST.resolve()
        if full_path:
            # Reject path traversal attempts
            if ".." in full_path or "%2e" in full_path.lower():
                raise HTTPException(status_code=403, detail="Forbidden: Path traversal not permitted.")

            target = (_FRONTEND_DIST / full_path).resolve()
            try:
                target.relative_to(dist_root)
            except ValueError:
                raise HTTPException(status_code=403, detail="Forbidden: Path traversal not permitted.")

            if target.is_file():
                return FileResponse(str(target))

            # If an explicit file with extension was requested but not found, 404 instead of SPA fallback
            if target.suffix or ("." in target.name and not target.name.startswith(".")):
                raise HTTPException(status_code=404, detail="File not found.")

        index_file = dist_root / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        raise HTTPException(status_code=404, detail="Frontend build index.html not found.")
