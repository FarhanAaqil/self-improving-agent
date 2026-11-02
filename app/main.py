import asyncio
import glob
import json
import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.config import (
    ALLOW_CODE_OVERRIDE,
    ALLOW_UNSAFE_HOST_SUBPROCESS,
    ALLOWED_ORIGINS,
    AVAILABLE_MODELS,
    DEMO_MODE,
    MEMORY_ENABLED,
    MODEL,
    RESULTS_DIR,
    SANDBOX_TIMEOUT,
)
from app.generator import generate_code
from app.jobs import recover_interrupted_runs, submit_run
from app.pipeline import RunSpec, execute_run
from app.sandbox import SANDBOX_IMAGE, _is_docker_available, docker_run_args, run_code
from app.schemas import (
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
from app.security import auth_mode, rate_limited, verify_api_access

logger = logging.getLogger("self_improving_agent")

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


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
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
    if request.url.path.startswith(("/generate", "/execute", "/runs", "/eval", "/memory")):
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


def _load_run(run_id: str) -> dict:
    run = db.get_run_with_attempts(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return run


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


# ── Generate only ────────────────────────────────────────────

@app.post(
    "/generate",
    response_model=GenerateOut,
    dependencies=[Depends(verify_api_access), Depends(rate_limited)],
    tags=["Agent"],
)
def generate_endpoint(req: GenerateRequest):
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    model_name = req.model or MODEL

    try:
        code = generate_code(req.task_description, model=model_name)
    except Exception as e:
        logger.error("LLM generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail="The language model call failed. Try again shortly.")

    db.insert_run(run_id, req.task_description, final_status="generated", total_attempts=1)
    db.update_run(run_id, model_name=model_name)
    db.insert_attempt(run_id=run_id, attempt_number=1, generated_code=code, model_name=model_name, success=False)
    return GenerateOut(run_id=run_id, code=code, model=model_name)


# ── Execute existing code ───────────────────────────────────

@app.post(
    "/execute/{run_id}",
    response_model=ExecuteOut,
    dependencies=[Depends(verify_api_access), Depends(rate_limited)],
    tags=["Agent"],
)
def execute_endpoint(run_id: str, req: Optional[ExecuteRequest] = None):
    run = _load_run(run_id)
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

def _spec(req: GenerateAndRepairRequest) -> RunSpec:
    return RunSpec(
        task=req.task_description,
        model=req.model or MODEL,
        max_attempts=req.max_attempts,
        skip_agents=list(req.skip_agents),
    )


@app.post(
    "/generate-and-repair",
    response_model=RunOut,
    dependencies=[Depends(verify_api_access), Depends(rate_limited)],
    tags=["Agent"],
)
def generate_and_repair_endpoint(req: GenerateAndRepairRequest):
    """Synchronous version: blocks until the run finishes. Prefer POST /runs for UIs."""
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    db.insert_run(run_id, req.task_description, final_status="queued")
    execute_run(run_id, _spec(req))
    return _run_out(_load_run(run_id))


@app.post(
    "/runs",
    response_model=RunAccepted,
    status_code=202,
    dependencies=[Depends(verify_api_access), Depends(rate_limited)],
    tags=["Runs"],
)
def create_run(req: GenerateAndRepairRequest):
    """Start a run in the background and return immediately; follow it via /runs/{id}/events."""
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    spec = _spec(req)
    db.insert_run(run_id, req.task_description, final_status="queued")
    db.update_run(run_id, model_name=spec.model)
    submit_run(run_id, spec)
    return RunAccepted(run_id=run_id, events_url=f"/runs/{run_id}/events")


@app.get("/runs", response_model=RunPage, dependencies=[Depends(verify_api_access)], tags=["Runs"])
def list_runs_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None, max_length=200),
    status: Optional[str] = Query(None, pattern="^(success|failed|early_stopped|running)$"),
):
    return db.list_run_summaries(page=page, page_size=page_size, q=q, status=status)


@app.get(
    "/runs/{run_id}",
    response_model=RunOut,
    dependencies=[Depends(verify_api_access)],
    tags=["Runs"],
)
def get_run_endpoint(run_id: str):
    return _run_out(_load_run(run_id))


def _sse(event_id: int, event_type: str, payload: dict) -> str:
    return f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


@app.get("/runs/{run_id}/events", dependencies=[Depends(verify_api_access)], tags=["Runs"])
async def run_events(run_id: str, request: Request, after: int = Query(0, ge=0)):
    """Server-sent events for a run. Replays history, then streams until the run finishes."""
    if not await asyncio.to_thread(db.get_run, run_id):
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
def create_pull_request_endpoint(run_id: str, repo: Optional[str] = None):
    from app.github_agent import open_pull_request_for_run

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
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    kind: Optional[str] = Query(None, pattern="^(failure|fix)$"),
):
    return _memory_or_503().list_memories(limit=limit, offset=offset, kind=kind)


@app.get("/memory/stats", dependencies=[Depends(verify_api_access)], tags=["Memory"])
def memory_stats():
    return _memory_or_503().memory_stats()


@app.get("/memory/search", dependencies=[Depends(verify_api_access)], tags=["Memory"])
def search_memory(
    q: str = Query(..., min_length=3, max_length=500),
    threshold: float = Query(0.3, ge=0.0, le=1.0),
):
    """What does the agent remember about this? Uses a looser threshold than generation."""
    return {"items": _memory_or_503().retrieve_similar_failures(q, top_k=10, similarity_threshold=threshold)}


@app.delete("/memory/{memory_id}", dependencies=[Depends(verify_api_access)], tags=["Memory"])
def delete_memory(memory_id: str):
    if not _memory_or_503().delete_memory(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"deleted": memory_id}


@app.post("/memory/{memory_id}/pin", dependencies=[Depends(verify_api_access)], tags=["Memory"])
def pin_memory(memory_id: str, pinned: bool = True):
    if not _memory_or_503().set_pinned(memory_id, pinned):
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"id": memory_id, "pinned": pinned}


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
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

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
