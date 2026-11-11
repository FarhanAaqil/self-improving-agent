"""The self-repairing pipeline, shared by the synchronous endpoint, background jobs and evals.

    recall memory → write spec tests → generate → verify in sandbox
        ↳ failed: diagnose → (maybe fix the tests) → repair with code + error + diagnosis
        ↳ passed: review agents → document (kept only if it still passes) → score → remember

Every step is recorded as a run event so the UI can follow along live.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from app import db, llm
from app.code_security_audit import CodeSecurityAudit
from app.config import (
    CRITIQUE_CONFIDENCE_THRESHOLD,
    MEMORY_ENABLED,
    MODEL,
    MUTATION_ENABLED,
    SANDBOX_TIMEOUT,
)
from app.critique import critique_code, diagnose_failure
from app.documentation_agent import document_code
from app.generator import generate_code
from app.harness import Verification, mutation_test, verify
from app.metrics import calculate_quality_metrics
from app.observability import metrics
from app.performance_agent import analyze_performance
from app.static_analysis import bandit_scan, radon_complexity
from app.test_agent import (
    drop_tests,
    generate_spec_tests,
    merge_tests,
    strengthen_tests,
    usable_tests,
)

logger = logging.getLogger("self_improving_agent.pipeline")

# Blaming the tests is allowed once per run; after that the code has to adapt.
MAX_TEST_REWRITES = 1


@dataclass
class RunSpec:
    task: str
    model: str = MODEL
    max_attempts: int = 3
    skip_agents: list[str] = field(default_factory=list)
    workspace: str = "default"
    # A caller's own Groq key: used for this run only, never stored or printed
    groq_key: str | None = field(default=None, repr=False)
    # Benchmarks turn these off to measure one thing at a time
    review: bool = True
    strengthen: bool = True
    use_memory: bool = True

    def skips(self, *names: str) -> bool:
        return any(n in self.skip_agents for n in names)


class Emitter:
    def __init__(self, run_id: str):
        self.run_id = run_id

    def __call__(self, event_type: str, **payload) -> None:
        try:
            db.add_event(self.run_id, event_type, payload)
        except Exception:  # events are best effort; never let them break a run
            logger.warning("Could not record %s event for %s", event_type, self.run_id, exc_info=True)


def _recall(spec: RunSpec, emit: Emitter) -> tuple[list[dict], str]:
    if not MEMORY_ENABLED or not spec.use_memory:
        return [], ""
    try:
        from app.memory import format_memories, mark_used, retrieve_similar_failures

        memories = retrieve_similar_failures(spec.task, workspace=spec.workspace)
        mark_used([m.get("id") for m in memories])
    except Exception:
        logger.warning("Memory recall failed", exc_info=True)
        return [], ""
    public = [
        {k: m.get(k) for k in ("id", "kind", "task", "error", "lesson", "similarity")}
        for m in memories
    ]
    emit("memory_recalled", memories=public)
    return public, format_memories(memories)


def _remember(spec: RunSpec, solved: bool, first_error: str | None, last_error: str | None,
              last_code: str | None, lesson: str | None) -> None:
    if not MEMORY_ENABLED or not spec.use_memory:
        return
    try:
        from app import memory

        if solved and first_error and lesson:
            memory.store_lesson(task=spec.task, error=first_error, lesson=lesson, workspace=spec.workspace)
        elif not solved and last_error and last_code:
            memory.store_failure(task=spec.task, code=last_code, error=last_error, workspace=spec.workspace)
    except Exception:
        logger.warning("Memory write failed", exc_info=True)


def _attempt_record(v: Verification) -> dict:
    return {
        "stdout": v.output,
        "stderr": v.error,
        "exit_code": v.exit_code,
        "success": v.success,
        "latency_ms": v.latency_ms,
        "tests_passed": v.passed if v.total else None,
        "tests_total": v.total or None,
        "coverage": v.coverage,
        "test_report_json": json.dumps(v.report),
        "sandboxed": v.sandboxed,
    }


def _verification_event(v: Verification) -> dict:
    return {
        "success": v.success,
        "passed": v.passed,
        "total": v.total,
        "coverage": v.coverage,
        "failures": v.failures[:5],
        "stdout": (v.output or "")[-4000:],
        "stderr": (v.error or "")[-4000:],
        "exit_code": v.exit_code,
        "latency_ms": v.latency_ms,
        "sandboxed": v.sandboxed,
    }


def _harden(spec: RunSpec, code: str, tests: str, v: Verification, emit: Emitter):
    """
    Mutation-test the passing code and try once to write stricter tests for the gaps.
    Returns (tests, verification, mutation_report, diagnosis). `verification.success` is
    False when the stricter tests exposed a real bug; `diagnosis` is then its explanation.
    """
    report = mutation_test(code, tests)
    emit("mutation_tested", stage="initial", **{k: report.get(k) for k in ("available", "total", "killed", "score")},
         survivors=report.get("survivors", [])[:5])
    if not report.get("available") or not report.get("survivors"):
        return tests, v, report, None

    try:
        extra = strengthen_tests(spec.task, code, tests, report["survivors"], model_override=spec.model)
    except Exception as e:
        logger.warning("Test strengthening failed: %s", e)
        extra = None
    if not extra:
        return tests, v, report, None

    stricter = merge_tests(tests, extra)
    if not usable_tests(stricter):
        return tests, v, report, None
    added = extra.count("def test_")
    recheck = verify(code, stricter, timeout=SANDBOX_TIMEOUT)
    if recheck.success:
        final = mutation_test(code, stricter)
        emit("tests_strengthened", outcome="kept", added=added)
        emit("mutation_tested", stage="final", **{k: final.get(k) for k in ("available", "total", "killed", "score")},
             survivors=final.get("survivors", [])[:5])
        return stricter, recheck, (final if final.get("available") else report), None

    # The stricter tests fail: is the code wrong, or are the new tests?
    diag = None
    if not spec.skips("critique"):
        try:
            diag = diagnose_failure(spec.task, code, recheck.feedback(), stricter, model_override=spec.model)
        except Exception as e:
            logger.warning("Diagnosis of stricter tests failed: %s", e)
    if diag is None or diag["blame"] == "tests":
        emit("tests_strengthened", outcome="discarded", added=added,
             reason=(diag or {}).get("root_cause", "could not confirm the stricter tests"))
        return tests, v, report, None

    emit("tests_strengthened", outcome="found_bug", added=added, reason=diag["summary"])
    return stricter, recheck, report, diag


def _review(spec: RunSpec, run_id: str, attempt_id: int, code: str, tests: str | None,
            verification: Verification, emit: Emitter, mutation: dict | None = None) -> tuple[str, bool]:
    """Run post-success agents. Returns (final_code, docs_applied)."""
    model = spec.model
    reviews: dict = {}

    def agent(name: str, fn, *skip_names: str):
        if not spec.review or spec.skips(name, *skip_names):
            emit("review", agent=name, status="skipped")
            return None
        emit("review", agent=name, status="running")
        try:
            result = fn()
            emit("review", agent=name, status="done", result=result if isinstance(result, str) else None)
            return result
        except Exception as e:
            logger.warning("%s agent failed: %s", name, e)
            emit("review", agent=name, status="error")
            return None

    reviews["performance"] = agent("performance", lambda: analyze_performance(spec.task, code, model_override=model))
    reviews["security"] = agent(
        "security_audit",
        lambda: CodeSecurityAudit.audit(spec.task, code, model_override=model),
        "security",
    )
    critique = agent(
        "critique", lambda: critique_code(spec.task, code, verification.output or "", model_override=model)
    )
    bandit = bandit_scan(code)
    radon = radon_complexity(code)
    emit("static_analysis", bandit_issues=bandit.get("issues", []), complexity=radon.get("max"))

    # Documentation may change code that already passed, so it has to pass again to be kept.
    final_code, docs_applied = code, False
    documented = agent("docs", lambda: document_code(spec.task, code, model_override=model), "documentation")
    if documented and documented.strip() != code.strip():
        recheck = verify(documented, tests, timeout=SANDBOX_TIMEOUT)
        docs_applied = recheck.success
        if docs_applied:
            final_code = documented
        emit("docs_verified", kept=docs_applied, passed=recheck.passed, total=recheck.total)

    metrics = calculate_quality_metrics(
        code=code,
        test_report=verification.report,
        performance_notes=reviews["performance"],
        security_audit=reviews["security"],
        bandit=bandit,
        radon=radon,
        mutation=mutation,
    )
    db.update_attempt_review(
        attempt_id=attempt_id,
        critique_confidence=(critique or {}).get("confidence"),
        critique_reasoning=(critique or {}).get("reasoning"),
        generated_tests=tests,
        performance_notes=reviews["performance"],
        security_audit=reviews["security"],
        quality_overall_score=metrics.get("overall_score"),
        quality_report_json=json.dumps(metrics),
    )
    emit("quality", score=metrics.get("overall_score"), components=metrics.get("components"))
    return final_code, docs_applied


def execute_run(run_id: str, spec: RunSpec) -> str:
    """Run the full pipeline for an existing `runs` row. Returns the final status."""
    emit = Emitter(run_id)
    with llm.groq_key(spec.groq_key), llm.track_usage() as usage:
        try:
            status = _execute(run_id, spec, emit)
        except Exception as e:
            logger.error("Run %s crashed: %s", run_id, e, exc_info=True)
            status = "failed"
            emit("error", message="The pipeline hit an internal error. Check server logs.")
        db.update_run(
            run_id,
            final_status=status,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            finished_at=datetime.now().isoformat(),
        )
        emit("run_finished", status=status, tokens=usage["prompt_tokens"] + usage["completion_tokens"])
        metrics.inc("agent_runs_total", status=status)
        metrics.inc("agent_llm_tokens_total", usage["prompt_tokens"], kind="prompt")
        metrics.inc("agent_llm_tokens_total", usage["completion_tokens"], kind="completion")
    return status


def _write_spec_tests(spec: RunSpec, emit: Emitter, feedback: str | None = None) -> str | None:
    """Spec tests that at least parse and contain a test, or None after two tries."""
    for _ in range(2):
        try:
            tests = generate_spec_tests(spec.task, model_override=spec.model, feedback=feedback)
        except Exception as e:
            logger.warning("Spec test generation failed: %s", e)
            continue
        if usable_tests(tests):
            return tests
        feedback = "The previous answer was not valid Python test code. Return complete test functions only."
    return None


def _triage(spec: RunSpec, code: str, tests: str, v: Verification, diag: dict, emit: Emitter):
    """
    When the diagnosis says specific failing tests contradict the task, drop just those and
    re-check the same code. Returns (tests, verification) on success, otherwise None.
    A minority of tests at most: the diagnosis must not be able to wave everything through.
    """
    failing = {f["test"] for f in v.failures}
    named = [t for t in diag.get("wrong_tests", []) if t in failing]
    if not named or v.total < 2 or len(named) > v.total // 2:
        return None
    try:
        pruned = drop_tests(tests, named)
    except SyntaxError:
        return None
    if not usable_tests(pruned):
        return None
    recheck = verify(code, pruned, timeout=SANDBOX_TIMEOUT)
    emit("tests_triaged", dropped=named, passed=recheck.success, reason=diag.get("root_cause", ""))
    return (pruned, recheck) if recheck.success else None


def _diagnose(spec: RunSpec, code: str, feedback: str, tests: str | None, attempt: int, emit: Emitter) -> dict | None:
    if spec.skips("critique"):
        return None
    emit("diagnosing", attempt=attempt)
    try:
        return diagnose_failure(spec.task, code, feedback, tests, model_override=spec.model)
    except Exception as e:
        logger.warning("Diagnosis failed: %s", e)
        return None


def _execute(run_id: str, spec: RunSpec, emit: Emitter) -> str:
    db.update_run(run_id, final_status="running", model_name=spec.model)
    emit("run_started", task=spec.task, model=spec.model, max_attempts=spec.max_attempts)

    memories, memory_context = _recall(spec, emit)
    db.update_run(run_id, memories_json=json.dumps(memories))

    tests: str | None = None
    if not spec.skips("test", "tests"):
        emit("tests_writing")
        tests = _write_spec_tests(spec, emit)
        db.update_run(run_id, spec_tests=tests)
        emit("tests_ready", tests=tests, count=(tests or "").count("def test_"))
        if tests is None:
            # Without tests nothing can be verified, and a clean exit must not be stamped as proof
            emit("error", message="I couldn't write usable spec tests for this task, so there is nothing to verify against.")
            return "failed"

    feedback = diagnosis_text = previous_code = None
    first_error: str | None = None
    lesson: str | None = None
    test_rewrites = 0
    hardened = triaged = False
    mutation: dict | None = None

    for attempt in range(1, spec.max_attempts + 1):
        db.update_run(run_id, total_attempts=attempt)
        emit("attempt_started", attempt=attempt)

        try:
            code = generate_code(
                task=spec.task,
                error=feedback,
                attempt=attempt,
                memory_context=memory_context,
                model=spec.model,
                use_memory=False,  # recall already happened above, with events
                previous_code=previous_code,
                tests=tests,
                diagnosis=diagnosis_text,
            )
        except llm.EmptyCompletion:
            code = ""
        emit("code_generated", attempt=attempt, code=code)

        emit("sandbox_started", attempt=attempt)
        v = verify(code, tests, timeout=SANDBOX_TIMEOUT)
        emit("sandbox_result", attempt=attempt, **_verification_event(v))

        diag = None
        if not v.success:
            diag = _diagnose(spec, code, v.feedback(), tests, attempt, emit)
            # Tests that contradict the task are removed, and the same code gets a fair re-check
            if diag and tests and diag["blame"] == "tests" and not triaged:
                triaged = True
                rescued = _triage(spec, code, tests, v, diag, emit)
                if rescued:
                    tests, v = rescued
                    diag = None
                    db.update_run(run_id, spec_tests=tests)

        if v.success and tests and not hardened and MUTATION_ENABLED and spec.strengthen and not spec.skips("mutation"):
            hardened = True  # one hardening round per run
            tests, v, mutation, diag = _harden(spec, code, tests, v, emit)
            db.update_run(run_id, spec_tests=tests)

        if v.success:
            attempt_id = db.insert_attempt(
                run_id=run_id, attempt_number=attempt, generated_code=code, model_name=spec.model,
                **_attempt_record(v),
            )
            emit("verified", attempt=attempt, passed=v.passed, total=v.total, coverage=v.coverage)
            final_code, docs_applied = _review(spec, run_id, attempt_id, code, tests, v, emit, mutation)
            db.update_run(run_id, final_code=final_code, docs_applied=docs_applied)
            _remember(spec, True, first_error, None, None, lesson)
            return "success"

        feedback = v.feedback()
        first_error = first_error or feedback
        previous_code = code

        db.insert_attempt(
            run_id=run_id, attempt_number=attempt, generated_code=code, model_name=spec.model,
            critique_confidence=(diag or {}).get("confidence"),
            critique_reasoning=(diag or {}).get("reasoning"),
            diagnosis_json=json.dumps(diag) if diag else None,
            **_attempt_record(v),
        )
        if not diag:
            diagnosis_text = None
            continue

        emit("diagnosis", attempt=attempt, summary=diag["summary"], root_cause=diag["root_cause"],
             fix_plan=diag["fix_plan"], blame=diag["blame"], confidence=diag["confidence"])
        diagnosis_text = f"Root cause: {diag['root_cause']}\nFix plan: {diag['fix_plan']}"
        lesson = diag["fix_plan"] or diag["root_cause"] or lesson

        if diag["confidence"] < CRITIQUE_CONFIDENCE_THRESHOLD:
            emit("early_stop", attempt=attempt, reason=diag["summary"])
            _remember(spec, False, first_error, feedback, code, None)
            return "early_stopped"

        if tests and diag["blame"] == "tests" and test_rewrites < MAX_TEST_REWRITES:
            test_rewrites += 1
            rewritten = _write_spec_tests(spec, emit, feedback=diag["root_cause"])
            if rewritten:
                tests = rewritten
                db.update_run(run_id, spec_tests=tests)
                emit("tests_rewritten", tests=tests, reason=diag["root_cause"])

    _remember(spec, False, first_error, feedback, previous_code, None)
    return "max_retries_exceeded"
