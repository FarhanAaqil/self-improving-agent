import glob
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.code_security_audit import CodeSecurityAudit
from app.config import (
    MODEL,
    RESULTS_DIR,
    SANDBOX_TIMEOUT,
)
from app.critique import critique_code
from app.db import (
    get_latest_eval_run,
    get_run_with_attempts,
    init_db,
    insert_attempt,
    insert_eval_run,
    insert_run,
    list_runs,
    update_attempt_review,
    update_run_status,
)
from app.documentation_agent import document_code
from app.generator import generate_code
from app.metrics import calculate_quality_metrics
from app.performance_agent import analyze_performance
from app.sandbox import _is_docker_available, run_code
from app.schemas import (
    EvalResultOut,
    EvalRunOut,
    EvalRunRequest,
    ExecuteOut,
    ExecuteRequest,
    GenerateAndRepairRequest,
    GenerateOut,
    GenerateRequest,
    RunOut,
)
from app.test_agent import generate_unit_tests

# Ensure SQLite tables exist immediately upon import
init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Self-Improving Code Agent API",
    description="Backend API powering the sandboxed, self-repairing code generation agent.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS enabled for local Vite / React dashboard development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── System ───────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "docker_available": _is_docker_available(),
    }


# ── Endpoint 1: POST /generate ───────────────────────────────

@app.post("/generate", response_model=GenerateOut, tags=["Agent"])
def generate_endpoint(req: GenerateRequest):
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    model_name = req.model or MODEL

    try:
        code = generate_code(req.task_description, model=model_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")

    insert_run(run_id, req.task_description, final_status="generated", total_attempts=1)
    insert_attempt(
        run_id=run_id,
        attempt_number=1,
        generated_code=code,
        model_name=model_name,
        success=False,
    )

    return GenerateOut(run_id=run_id, code=code, model=model_name)


# ── Endpoint 2: POST /execute/{run_id} ───────────────────────

@app.post("/execute/{run_id}", response_model=ExecuteOut, tags=["Agent"])
def execute_endpoint(run_id: str, req: Optional[ExecuteRequest] = None):
    run = get_run_with_attempts(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    # Determine code to execute
    code_to_run = None
    attempt_num = len(run.get("attempts", []))

    if req and req.code_override:
        code_to_run = req.code_override
        attempt_num += 1
    elif run.get("attempts"):
        target_idx = (req.attempt_number - 1) if (req and req.attempt_number) else -1
        code_to_run = run["attempts"][target_idx]["generated_code"]
    else:
        raise HTTPException(status_code=422, detail="No code found in this run to execute.")

    result = run_code(code_to_run, timeout=SANDBOX_TIMEOUT)

    # Persist attempt result
    insert_attempt(
        run_id=run_id,
        attempt_number=attempt_num,
        generated_code=code_to_run,
        stdout=result.get("output"),
        stderr=result.get("error"),
        exit_code=result.get("exit_code"),
        success=result["success"],
        latency_ms=result.get("latency_ms", 0),
    )

    new_status = "success" if result["success"] else "failed"
    update_run_status(run_id, final_status=new_status, total_attempts=attempt_num)

    return ExecuteOut(
        run_id=run_id,
        attempt_number=attempt_num,
        success=result["success"],
        output=result.get("output"),
        error=result.get("error"),
        exit_code=result.get("exit_code"),
        latency_ms=result.get("latency_ms"),
        sandboxed=result.get("sandboxed", True),
    )


# ── Endpoint 3: POST /generate-and-repair ────────────────────

@app.post("/generate-and-repair", response_model=RunOut, tags=["Agent"])
def generate_and_repair_endpoint(req: GenerateAndRepairRequest):
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    model_name = req.model or MODEL

    insert_run(run_id, req.task_description, final_status="running")

    last_error = None
    working_code = None
    working_output = None
    attempts_done = 0
    passing_attempt_id: int | None = None
    last_failed_code: str | None = None

    for attempt in range(1, req.max_attempts + 1):
        attempts_done = attempt
        try:
            code = generate_code(
                task=req.task_description,
                error=last_error,
                attempt=attempt,
                model=model_name,
            )
        except Exception as e:
            insert_attempt(
                run_id=run_id,
                attempt_number=attempt,
                generated_code="# generation error",
                stderr=str(e),
                exit_code=-1,
                success=False,
                model_name=model_name,
            )
            update_run_status(run_id, final_status="failed", total_attempts=attempt)
            raise HTTPException(status_code=500, detail=f"LLM call failed on attempt {attempt}: {str(e)}")

        exec_res = run_code(code, timeout=SANDBOX_TIMEOUT)

        critique_conf = None
        critique_re = None
        should_early_stop = False

        if exec_res["success"]:
            working_code = code
            working_output = exec_res.get("output") or ""
            passing_attempt_id = insert_attempt(
                run_id=run_id,
                attempt_number=attempt,
                generated_code=code,
                stdout=exec_res.get("output"),
                stderr=exec_res.get("error"),
                exit_code=exec_res.get("exit_code"),
                success=True,
                latency_ms=exec_res.get("latency_ms"),
                model_name=model_name,
            )
            break
        else:
            last_error = exec_res.get("error")
            last_failed_code = code
            if "critique" not in req.skip_agents:
                try:
                    c_res = critique_code(
                        task=req.task_description,
                        code=code,
                        output=exec_res.get("error") or exec_res.get("output") or "",
                        model_override=model_name,
                    )
                    critique_conf = c_res.get("confidence")
                    critique_re = c_res.get("reasoning")
                    if critique_conf is not None and critique_conf < 0.3:
                        should_early_stop = True
                except Exception:
                    critique_conf = None
                    critique_re = None

            insert_attempt(
                run_id=run_id,
                attempt_number=attempt,
                generated_code=code,
                stdout=exec_res.get("output"),
                stderr=exec_res.get("error"),
                exit_code=exec_res.get("exit_code"),
                success=False,
                latency_ms=exec_res.get("latency_ms"),
                model_name=model_name,
                critique_confidence=critique_conf,
                critique_reasoning=critique_re,
            )

            if should_early_stop:
                break

    # Post-success review pipeline
    if working_code and passing_attempt_id is not None:
        generated_tests = None
        performance_notes = None
        security_audit = None
        critique_conf = None
        critique_re = None

        if "test" not in req.skip_agents and "tests" not in req.skip_agents:
            try:
                generated_tests = generate_unit_tests(req.task_description, working_code, model_override=model_name)
            except Exception:
                generated_tests = None

        if "performance" not in req.skip_agents:
            try:
                performance_notes = analyze_performance(req.task_description, working_code, model_override=model_name)
            except Exception:
                performance_notes = None

        if "security_audit" not in req.skip_agents and "security" not in req.skip_agents:
            try:
                security_audit = CodeSecurityAudit.audit(req.task_description, working_code, model_override=model_name)
            except Exception:
                security_audit = None

        if "docs" not in req.skip_agents and "documentation" not in req.skip_agents:
            try:
                documented_code = document_code(req.task_description, working_code, model_override=model_name)
                if documented_code:
                    working_code = documented_code
            except Exception:
                pass

        if "critique" not in req.skip_agents:
            try:
                c_res = critique_code(req.task_description, working_code, working_output, model_override=model_name)
                critique_conf = c_res.get("confidence")
                critique_re = c_res.get("reasoning")
            except Exception:
                critique_conf = None
                critique_re = None

        quality_overall_score = None
        quality_report_json = None
        try:
            metrics_report = calculate_quality_metrics(
                code=working_code,
                generated_tests=generated_tests,
                performance_notes=performance_notes,
                security_audit=security_audit,
            )
            quality_overall_score = metrics_report.get("overall_score")
            quality_report_json = json.dumps(metrics_report)
        except Exception:
            pass

        update_attempt_review(
            attempt_id=passing_attempt_id,
            critique_confidence=critique_conf,
            critique_reasoning=critique_re,
            generated_tests=generated_tests,
            performance_notes=performance_notes,
            security_audit=security_audit,
            quality_overall_score=quality_overall_score,
            quality_report_json=quality_report_json,
            generated_code=working_code,
        )

    if working_code:
        final_status = "success"
    elif should_early_stop:
        final_status = "early_stopped"
    else:
        final_status = "max_retries_exceeded"
    update_run_status(run_id, final_status=final_status, total_attempts=attempts_done)

    # On terminal failure, record failure in ChromaDB vector memory for future retrieval
    if not working_code and last_error and last_failed_code:
        try:
            from app.memory import store_failure
            store_failure(
                task=req.task_description,
                code=last_failed_code,
                error=last_error,
            )
        except Exception:
            pass

    full_run = get_run_with_attempts(run_id)
    if not full_run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return RunOut(**full_run)


# ── Endpoint 4: GET /runs/{run_id} & GET /runs ───────────────

@app.get("/runs/{run_id}", response_model=RunOut, tags=["Runs"])
def get_run_endpoint(run_id: str):
    run = get_run_with_attempts(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return RunOut(**run)


@app.get("/runs", tags=["Runs"])
def list_runs_endpoint(limit: int = Query(50, ge=1, le=100)):
    return list_runs(limit=limit)


# ── Endpoint 5: GET /eval/latest ─────────────────────────────

@app.get("/eval/latest", response_model=EvalResultOut, tags=["Evaluation"])
def get_latest_eval_endpoint():
    # Priority 1: Check committed JSON results in results/
    os.makedirs(RESULTS_DIR, exist_ok=True)
    json_files = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.json")), reverse=True)

    if json_files:
        try:
            with open(json_files[0], "r", encoding="utf-8") as f:
                data = json.load(f)
                return EvalResultOut(
                    eval_id=data.get("eval_id", os.path.basename(json_files[0])),
                    benchmark_name=data.get("benchmark", "humaneval"),
                    pass_at_1=data.get("pass_at_1"),
                    pass_at_5=data.get("pass_at_5"),
                    avg_attempts=data.get("avg_attempts"),
                    avg_latency_ms=data.get("avg_latency_ms"),
                    total_problems=data.get("total_problems", len(data.get("results", []))),
                    run_at=data.get("run_at"),
                    raw=data,
                )
        except Exception:
            pass

    # Priority 2: Check SQLite eval_runs table
    latest = get_latest_eval_run()
    if latest:
        raw_dict = json.loads(latest["raw_json"]) if latest.get("raw_json") else None
        return EvalResultOut(
            eval_id=latest["eval_id"],
            benchmark_name=latest["benchmark_name"],
            pass_at_1=latest.get("pass_at_1"),
            pass_at_5=latest.get("pass_at_5"),
            avg_attempts=latest.get("avg_attempts"),
            avg_latency_ms=latest.get("avg_latency_ms"),
            total_problems=latest.get("total_problems"),
            run_at=latest.get("run_at"),
            raw=raw_dict,
        )

    # Empty baseline fallback
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


# ── Endpoint 6: POST /eval/run ───────────────────────────────

def _run_eval_job(eval_id: str, benchmark: str, subset_size: int):
    # Executed as a background worker task
    try:
        from groq import Groq

        from app.config import GROQ_API_KEY
        from eval.evaluate import evaluate_all
        from eval.humaneval_problems import PROBLEMS

        client = Groq(api_key=GROQ_API_KEY)
        subset = PROBLEMS[:subset_size] if subset_size else PROBLEMS
        results = evaluate_all(subset, client, MODEL, max_retries=3)

        insert_eval_run(
            eval_id=eval_id,
            benchmark_name=benchmark,
            pass_at_1=results["agent"]["pass_at_1"],
            avg_attempts=results["agent"]["avg_attempts"],
            total_problems=results["total_problems"],
            raw_json=json.dumps(results),
        )

        # Write to results/ for git commit persistence
        results_file = os.path.join(RESULTS_DIR, f"{eval_id}.json")
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    except Exception as e:
        # Background task error handling
        insert_eval_run(
            eval_id=eval_id,
            benchmark_name=benchmark,
            raw_json=json.dumps({"error": str(e)}),
        )


@app.post("/eval/run", response_model=EvalRunOut, tags=["Evaluation"])
def run_eval_endpoint(req: EvalRunRequest, background_tasks: BackgroundTasks):
    eval_id = f"eval_{uuid.uuid4().hex[:8]}"

    # Dispatch to background task so the API client is not blocked for minutes
    background_tasks.add_task(_run_eval_job, eval_id, req.benchmark, req.subset_size or 50)

    return EvalRunOut(
        eval_id=eval_id,
        status="started",
        message=f"Evaluation {eval_id} started in background for benchmark '{req.benchmark}'.",
    )


# ── Frontend Static Files Mount ──────────────────────────────
_FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

if os.path.exists(_FRONTEND_DIST):
    _assets_dir = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.exists(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        file_path = os.path.join(_FRONTEND_DIST, full_path)
        if full_path and os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        index_file = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend build index.html not found.")

