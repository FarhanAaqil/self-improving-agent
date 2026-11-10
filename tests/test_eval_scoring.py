"""Benchmark statistics and the no-leakage feedback contract."""

import math

from eval.benchmark import (
    build_program,
    estimate_pass_at_k,
    load_custom,
    load_humaneval,
    safe_feedback,
    summarize,
    wilson_interval,
)


def test_estimate_pass_at_k_exact_values():
    assert estimate_pass_at_k(1, 1, 1) == 1.0
    assert estimate_pass_at_k(5, 0, 1) == 0.0
    assert estimate_pass_at_k(10, 3, 1) == 0.3
    expected = 1 - math.comb(7, 5) / math.comb(10, 5)
    assert math.isclose(estimate_pass_at_k(10, 3, 5), round(expected, 4))


def test_estimate_pass_at_k_boundary_conditions():
    assert estimate_pass_at_k(0, 0, 1) == 0.0
    assert estimate_pass_at_k(3, 1, 5) == 0.0  # fewer samples than k
    assert estimate_pass_at_k(5, 3, 3) == 1.0  # cannot draw k failures


def test_wilson_interval_is_sane():
    low, high = wilson_interval(8, 10)
    assert 40 < low < 80 < high <= 100
    assert wilson_interval(0, 0) == (0.0, 0.0)
    narrow = wilson_interval(80, 100)
    assert narrow[1] - narrow[0] < high - low  # more samples, tighter bars


def test_feedback_never_reveals_hidden_test_source():
    stderr = (
        "Traceback (most recent call last):\n"
        '  File "<stdin>", line 40, in <module>\n'
        '  File "<stdin>", line 30, in check\n'
        "    assert candidate([1.0, 2.0, 3.9], 0.3) == True, 'secret expectation'\n"
        "AssertionError: secret expectation\n"
    )
    feedback = safe_feedback(stderr, timed_out=False)
    assert "candidate" not in feedback
    assert "secret" not in feedback
    assert "3.9" not in feedback
    assert "AssertionError" in feedback


def test_feedback_for_timeouts_and_own_errors():
    assert "timed out" in safe_feedback(None, timed_out=True)
    own = safe_feedback('  File "<stdin>", line 3, in solve\nNameError: name \'foo\' is not defined', False)
    assert "NameError" in own and "foo" in own


def test_official_dataset_is_vendored_and_complete():
    problems = load_humaneval()
    assert len(problems) == 164
    assert all(p["test"].rstrip().endswith(f"check({p['entry_point']})") for p in problems)
    assert len(load_custom()) >= 10


def test_program_keeps_prompt_helpers_available():
    problem = {"prompt": "def helper():\n    return 1\n\ndef f():\n    \"\"\"doc\"\"\"\n", "test": "assert f() == 1"}
    program = build_program(problem, "def f():\n    return helper()")
    compile(program, "<program>", "exec")
    namespace: dict = {}
    exec(program, namespace)  # trusted literal: proves the stub is overridden


def test_summary_separates_baseline_first_try_and_repair():
    results = [
        {"problem_id": "a", "baseline_passed": True, "passed": True, "passed_at_attempt": 1,
         "attempts_used": 1, "latency_ms": 400, "sandboxed": True},
        {"problem_id": "b", "baseline_passed": False, "passed": True, "passed_at_attempt": 2,
         "attempts_used": 2, "latency_ms": 900, "sandboxed": True},
        {"problem_id": "c", "baseline_passed": False, "passed": False, "passed_at_attempt": None,
         "attempts_used": 3, "latency_ms": 1300, "sandboxed": True},
        {"problem_id": "d", "baseline_passed": True, "passed": True, "passed_at_attempt": 1,
         "attempts_used": 1, "latency_ms": 350, "sandboxed": True},
    ]
    s = summarize(results, "m", "humaneval", 3, {"prompt_tokens": 10, "completion_tokens": 5}, "id", 0.0)
    assert s["baseline"]["pass_at_1"] == 50.0
    assert s["agent"]["pass_at_1"] == 50.0
    assert s["agent"]["solve_at_k"] == 75.0
    assert s["repair_gain_pct"] == 25.0
    assert s["sandboxed"] is True
    assert s["suite"] == "official"
    assert s["avg_attempts"] == 1.75


def test_agent_benchmark_summary_separates_real_correctness_from_self_verification():
    import os

    os.environ.setdefault("AGENTBENCH_WORKDIR", os.path.join(os.environ["RESULTS_DIR"], "..", "agentbench"))
    from eval.agent_benchmark import summarize_condition

    def record(pid, verified, correct, first_try=True, attempts=1, score=0.9, memories=0):
        return {
            "problem_id": pid, "self_verified": verified, "attempts": attempts, "first_try": first_try,
            "hidden_pass": correct, "hidden_kind": None if correct else "wrong_value", "sandboxed": True,
            "tokens": 1000, "mutation_score": score, "strengthened": "kept" if correct else None, "memories": memories,
        }

    records = [
        record("a", True, True),
        record("b", True, False),            # stamped verified, actually wrong
        record("c", False, False, first_try=False, attempts=3),
        record("d", True, True, first_try=False, attempts=2, memories=1),
    ]
    s = summarize_condition("cold", records)
    assert s["hidden_pass_rate"] == 50.0
    assert s["self_verified"] == 3 and s["false_verified"] == 1
    assert s["false_verified_rate"] == 33.3 and s["false_verified_ids"] == ["b"]
    assert s["first_try_rate"] == 50.0 and s["avg_attempts"] == 1.75
    assert s["strengthening"]["kept"] == 2 and s["runs_that_recalled_memory"] == 1
    assert s["errors"] == 0

    baseline = summarize_condition("baseline", [{**record("a", None, True), "mutation_score": None}])
    assert "false_verified" not in baseline and baseline["hidden_pass_rate"] == 100.0


def test_agent_benchmark_endpoint_lists_results_without_raw_records():
    import json
    import os

    from fastapi.testclient import TestClient

    from app.config import RESULTS_DIR
    from app.main import app

    os.makedirs(RESULTS_DIR, exist_ok=True)
    payload = {
        "eval_id": "agentbench_test", "kind": "agent_benchmark", "model": "m", "run_at": "2026-01-01T00:00:00",
        "conditions": [{"condition": "agent", "hidden_pass_rate": 50.0}],
        "records": {"agent": [{"problem_id": "HumanEval/1", "hidden_pass": True, "self_verified": True, "tokens": 9}]},
    }
    with open(os.path.join(RESULTS_DIR, "agentbench_test.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f)

    items = TestClient(app).get("/eval/agent").json()["items"]
    item = next(i for i in items if i["eval_id"] == "agentbench_test")
    assert "records" not in item
    assert item["grid"]["agent"] == [{"id": "HumanEval/1", "correct": True, "verified": True}]


def test_hidden_test_feedback_from_the_plus_judge_never_reveals_inputs():
    from eval.plus import candidate_program, load_problems, safe_feedback

    assert "input" in safe_feedback({"kind": "wrong_value"}) and "[" not in safe_feedback({"kind": "wrong_value"})
    assert "TypeError" in safe_feedback({"kind": "exception", "detail": "TypeError"})
    problems = load_problems()
    assert len(problems) == 164 and all(len(p["inputs"]) > 0 for p in problems)
    program = candidate_program(problems[0], "def has_close_elements(numbers, threshold):\n    return False")
    compile(program, "<candidate>", "exec")
