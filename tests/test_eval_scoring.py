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
