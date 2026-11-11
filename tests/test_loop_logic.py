"""Pipeline behaviour: test-first repair loop, diagnosis, early stop, docs re-verification, memory."""

import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.harness import Verification
from app.main import app

client = TestClient(app)

SPEC_TESTS = "def test_answer():\n    assert solve() == 42\n"


def passed(total=1, coverage=1.0, output="42"):
    return Verification(True, output, None, 0, 10, True, total=total, passed=total, coverage=coverage)


def failed(error="ZeroDivisionError: division by zero", total=1):
    return Verification(
        False, None, error, 1, 12, True, total=total, passed=0,
        failures=[{"test": "test_answer", "error": error}],
    )


def diagnosis(confidence=0.8, blame="code"):
    return {
        "summary": "My code divides by zero.",
        "root_cause": "Division by zero on empty input",
        "fix_plan": "Guard the empty case",
        "blame": blame,
        "confidence": confidence,
        "reasoning": "My code divides by zero.",
        "raw": "{}",
    }


NO_MUTANTS = {"available": False, "total": 0, "killed": 0, "score": None, "survivors": [], "error": None}
GAP = {"available": True, "total": 4, "killed": 2, "score": 0.5, "error": None,
       "survivors": [{"line": 1, "source": "return 42", "change": "`42` became `43`"}]}
TIGHT = {"available": True, "total": 4, "killed": 4, "score": 1.0, "survivors": [], "error": None}
EXTRA_TESTS = "def test_answer():\n    assert solve() != 43\n"


def run_pipeline(codes, verifications, *, diag=None, skip=None, docs=None, tests=SPEC_TESTS, extra=None,
                 mutations=None, extra_tests=None):
    """Drive /generate-and-repair with every external dependency mocked."""
    mocks = {
        "generate_code": MagicMock(side_effect=codes),
        "verify": MagicMock(side_effect=verifications),
        "diagnose_failure": MagicMock(return_value=diag or diagnosis()),
        "generate_spec_tests": MagicMock(return_value=tests),
        "analyze_performance": MagicMock(return_value="OPTIMIZED"),
        "document_code": MagicMock(return_value=docs),
        "critique_code": MagicMock(return_value={"confidence": 0.95, "reasoning": "Clean"}),
        "mutation_test": MagicMock(side_effect=mutations or [NO_MUTANTS] * 4),
        "strengthen_tests": MagicMock(return_value=extra_tests),
    }
    with ExitStack() as stack:
        for name, mock in mocks.items():
            stack.enter_context(patch(f"app.pipeline.{name}", mock))
        audit = stack.enter_context(patch("app.pipeline.CodeSecurityAudit.audit", return_value="SECURE"))
        mocks["audit"] = audit
        for target, value in (extra or {}).items():
            stack.enter_context(patch(target, value))
        resp = client.post(
            "/generate-and-repair",
            json={"task_description": "Write solve() returning 42", "max_attempts": 3, "skip_agents": skip or []},
        )
    assert resp.status_code == 200, resp.text
    return resp.json(), mocks


def test_repair_loop_retry_to_success_feeds_code_error_and_diagnosis_back():
    data, m = run_pipeline(
        ["def solve(): return 1 / 0", "def solve(): return 42"],
        [failed(), passed()],
    )
    assert data["final_status"] == "success"
    assert data["total_attempts"] == 2
    assert [a["success"] for a in data["attempts"]] == [False, True]
    assert data["attempts"][0]["critique_confidence"] == 0.8
    assert data["spec_tests"] == SPEC_TESTS

    repair_call = m["generate_code"].call_args_list[1].kwargs
    assert repair_call["previous_code"] == "def solve(): return 1 / 0"
    assert "ZeroDivisionError" in repair_call["error"]
    assert "Guard the empty case" in repair_call["diagnosis"]
    assert repair_call["tests"] == SPEC_TESTS


def test_success_requires_tests_to_actually_pass():
    """Exit code 0 is not enough: the harness verdict decides."""
    data, _ = run_pipeline(["def solve(): return 41"] * 3, [failed("test_answer: AssertionError")] * 3)
    assert data["final_status"] == "max_retries_exceeded"
    assert data["attempts"][0]["tests_passed"] == 0
    assert data["attempts"][0]["tests_total"] == 1


def test_repair_loop_early_stop_on_low_confidence():
    data, m = run_pipeline(["def solve(): raise RuntimeError()"], [failed()], diag=diagnosis(confidence=0.1))
    assert data["final_status"] == "early_stopped"
    assert data["total_attempts"] == 1
    assert m["generate_code"].call_count == 1


def test_repair_loop_max_retries_exceeded():
    data, m = run_pipeline(["def solve(): pass"] * 3, [failed()] * 3)
    assert data["final_status"] == "max_retries_exceeded"
    assert len(data["attempts"]) == 3
    assert m["generate_code"].call_count == 3


def test_skip_all_agents_leaves_code_untouched():
    code = "def solve(): return 42"
    data, m = run_pipeline(
        [code], [passed(total=0)], tests=None,
        skip=["test", "performance", "security_audit", "docs", "critique"],
    )
    assert data["final_status"] == "success"
    assert data["final_code"] == code
    assert data["spec_tests"] is None
    for name in ("generate_spec_tests", "analyze_performance", "document_code", "critique_code", "audit"):
        m[name].assert_not_called()


def test_documented_code_is_kept_only_when_it_still_passes():
    raw, doc = "def solve(): return 42", 'def solve():\n    """Answer."""\n    return 42'

    kept, _ = run_pipeline([raw], [passed(), passed()], docs=doc)
    assert kept["final_code"] == doc
    assert kept["docs_applied"] is True
    # The attempt keeps the exact code that was verified
    assert kept["attempts"][0]["generated_code"] == raw

    dropped, _ = run_pipeline([raw], [passed(), failed("SyntaxError")], docs="def solve(:")
    assert dropped["final_code"] == raw
    assert dropped["docs_applied"] is False


def test_quality_metrics_come_from_measured_data():
    data, _ = run_pipeline(["def solve(): return 42"], [passed(total=4, coverage=0.75)])
    attempt = data["attempts"][0]
    report = json.loads(attempt["quality_report_json"])
    assert report["tests_passed"] == 4
    assert report["estimated_coverage"] == 0.75
    assert attempt["quality_overall_score"] is not None


def test_tests_blamed_by_diagnosis_are_rewritten_once():
    data, m = run_pipeline(
        ["def solve(): return 42"] * 3,
        [failed(), failed(), passed()],
        diag=diagnosis(blame="tests"),
    )
    assert data["final_status"] == "success"
    # Initial spec tests + exactly one rewrite
    assert m["generate_spec_tests"].call_count == 2


def test_terminal_failure_is_remembered():
    store = MagicMock()
    data, _ = run_pipeline(
        ["def broken(): raise ValueError('Fatal')"] * 3,
        [failed("ValueError: Fatal")] * 3,
        skip=["critique"],
        extra={"app.pipeline.MEMORY_ENABLED": True, "app.memory.store_failure": store,
               "app.memory.retrieve_similar_failures": MagicMock(return_value=[])},
    )
    assert data["final_status"] == "max_retries_exceeded"
    store.assert_called_once()
    assert "ValueError: Fatal" in store.call_args.kwargs["error"]
    assert "def broken()" in store.call_args.kwargs["code"]


def test_fix_after_failure_is_remembered_as_a_lesson():
    lesson = MagicMock()
    recalled = [{"id": "m1", "kind": "fix", "task": "t", "code": "", "error": "e", "lesson": "l", "similarity": 0.9}]
    data, _ = run_pipeline(
        ["def solve(): return 1/0", "def solve(): return 42"],
        [failed(), passed()],
        extra={"app.pipeline.MEMORY_ENABLED": True, "app.memory.store_lesson": lesson,
               "app.memory.mark_used": MagicMock(),
               "app.memory.retrieve_similar_failures": MagicMock(return_value=recalled)},
    )
    assert data["final_status"] == "success"
    assert data["memories"][0]["id"] == "m1"
    lesson.assert_called_once()
    assert lesson.call_args.kwargs["lesson"] == "Guard the empty case"


def test_pipeline_crash_marks_run_failed_instead_of_hanging():
    with patch("app.pipeline.generate_spec_tests", side_effect=RuntimeError("groq down")), \
         patch("app.pipeline.generate_code", side_effect=RuntimeError("groq down")):
        resp = client.post("/generate-and-repair", json={"task_description": "anything at all"})
    assert resp.status_code == 200
    assert resp.json()["final_status"] == "failed"


def test_events_are_recorded_and_streamed():
    data, _ = run_pipeline(["def solve(): return 1/0", "def solve(): return 42"], [failed(), passed()])
    with client.stream("GET", f"/runs/{data['run_id']}/events") as resp:
        body = "".join(resp.iter_text())
    for event in ("run_started", "tests_ready", "attempt_started", "sandbox_result",
                  "diagnosis", "verified", "quality", "run_finished"):
        assert f"event: {event}" in body

    # Resuming after the last seen id only replays what came later
    last_id = int([ln for ln in body.splitlines() if ln.startswith("id: ")][-2].split()[1])
    with client.stream("GET", f"/runs/{data['run_id']}/events", headers={"Last-Event-ID": str(last_id)}) as resp:
        tail = "".join(resp.iter_text())
    assert "event: run_started" not in tail
    assert "event: run_finished" in tail


def test_async_run_returns_immediately_and_lists_in_summaries():
    with patch("app.main.submit_run") as submit:
        resp = client.post("/runs", json={"task_description": "Write solve() returning 42"})
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]
    submit.assert_called_once()
    assert client.get(f"/runs/{run_id}").json()["final_status"] == "queued"

    page = client.get("/runs", params={"q": run_id}).json()
    assert page["total"] == 1
    assert page["items"][0]["run_id"] == run_id
    assert "attempts" not in page["items"][0]


def test_runs_listing_paginates_and_filters():
    for _ in range(3):
        run_pipeline(["def solve(): return 42"], [passed()])
    page = client.get("/runs", params={"page_size": 2, "status": "success"}).json()
    assert len(page["items"]) == 2
    assert page["total"] >= 3
    assert all(item["final_status"] == "success" for item in page["items"])
    assert client.get("/runs", params={"status": "bogus"}).status_code == 422


def test_stricter_tests_are_kept_when_the_code_still_passes():
    data, m = run_pipeline(
        ["def solve(): return 42"], [passed(), passed(total=2)],
        mutations=[GAP, TIGHT], extra_tests=EXTRA_TESTS,
    )
    assert data["final_status"] == "success"
    # The extra test was renamed instead of shadowing the original
    assert "def test_answer_strict(" in data["spec_tests"] and "def test_answer(" in data["spec_tests"]
    report = json.loads(data["attempts"][0]["quality_report_json"])
    assert report["components"]["mutation"] == 1.0
    assert report["mutation"]["killed"] == 4
    assert m["strengthen_tests"].call_args.args[3] == GAP["survivors"]


def test_stricter_tests_that_expose_a_real_bug_send_the_code_back_for_repair():
    data, m = run_pipeline(
        ["def solve(): return 42", "def solve(): return 42  # fixed"],
        [passed(), failed("AssertionError: boundary"), passed(total=2)],
        mutations=[GAP], extra_tests=EXTRA_TESTS, diag=diagnosis(blame="code"),
    )
    assert data["final_status"] == "success"
    assert [a["success"] for a in data["attempts"]] == [False, True]
    # The repair saw the stricter tests and the diagnosis, and the bug was diagnosed only once
    repair = m["generate_code"].call_args_list[1].kwargs
    assert "test_answer_strict" in repair["tests"]
    assert m["diagnose_failure"].call_count == 1


def test_stricter_tests_blamed_by_the_diagnosis_are_dropped():
    data, m = run_pipeline(
        ["def solve(): return 42"], [passed(), failed("AssertionError: bogus")],
        mutations=[GAP], extra_tests=EXTRA_TESTS, diag=diagnosis(blame="tests"),
    )
    assert data["final_status"] == "success"
    assert data["total_attempts"] == 1
    assert data["spec_tests"] == SPEC_TESTS
    assert m["generate_code"].call_count == 1


def test_hardening_can_be_skipped():
    data, m = run_pipeline(["def solve(): return 42"], [passed()], skip=["mutation"])
    assert data["final_status"] == "success"
    m["mutation_test"].assert_not_called()
