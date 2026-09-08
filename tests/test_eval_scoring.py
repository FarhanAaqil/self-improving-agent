import math

from eval.humaneval_runner import (
    calculate_pass_at_k_metrics,
    calculate_unbiased_benchmark_pass_at_k,
    estimate_pass_at_k,
)


def test_estimate_pass_at_k_exact_values():
    """Verify unbiased pass@k estimator matches exact combinatorial formulas."""
    # n=1, c=1 -> 1.0
    assert estimate_pass_at_k(n=1, c=1, k=1) == 1.0

    # n=1, c=0 -> 0.0
    assert estimate_pass_at_k(n=1, c=0, k=1) == 0.0

    # n=10, c=5, k=1 -> 1 - comb(5, 1)/comb(10, 1) = 1 - 5/10 = 0.5
    assert estimate_pass_at_k(n=10, c=5, k=1) == 0.5

    # n=10, c=5, k=5 -> 1 - comb(5, 5)/comb(10, 5) = 1 - 1/252 ~= 0.9960
    expected_k5 = round(1.0 - (math.comb(5, 5) / math.comb(10, 5)), 4)
    assert estimate_pass_at_k(n=10, c=5, k=5) == expected_k5

    # If c == n, pass@k is always 1.0
    assert estimate_pass_at_k(n=5, c=5, k=2) == 1.0


def test_estimate_pass_at_k_boundary_conditions():
    """Verify edge cases: n < k, non-positive inputs, zero successes."""
    assert estimate_pass_at_k(n=3, c=2, k=5) == 0.0
    assert estimate_pass_at_k(n=0, c=0, k=1) == 0.0
    assert estimate_pass_at_k(n=5, c=0, k=2) == 0.0


def test_calculate_pass_at_k_metrics_with_fixture():
    """Test metrics calculator on known list of 4 problem outcomes."""
    fixture_results = [
        # Problem 1: solved on attempt 1 (passed@1 and passed@5)
        {"passed": True, "passed_at_attempt": 1, "attempts_used": 1, "latency_ms": 100},
        # Problem 2: solved on attempt 3 (not passed@1, but passed@5)
        {"passed": True, "passed_at_attempt": 3, "attempts_used": 3, "latency_ms": 300},
        # Problem 3: solved on attempt 1 (passed@1 and passed@5)
        {"passed": True, "passed_at_attempt": 1, "attempts_used": 1, "latency_ms": 120},
        # Problem 4: failed (not passed at all)
        {"passed": False, "passed_at_attempt": None, "attempts_used": 3, "latency_ms": 280},
    ]

    metrics = calculate_pass_at_k_metrics(fixture_results)

    # 2 out of 4 solved at attempt 1 -> 50.0%
    assert metrics["pass_at_1"] == 50.0
    # 3 out of 4 solved within <= 5 attempts -> 75.0%
    assert metrics["pass_at_5"] == 75.0
    # (1 + 3 + 1 + 3) / 4 = 8 / 4 = 2.0
    assert metrics["avg_attempts"] == 2.0
    # (100 + 300 + 120 + 280) / 4 = 800 / 4 = 200.0
    assert metrics["avg_latency_ms"] == 200.0


def test_calculate_pass_at_k_metrics_empty():
    metrics = calculate_pass_at_k_metrics([])
    assert metrics["pass_at_1"] == 0.0
    assert metrics["pass_at_5"] == 0.0
    assert metrics["avg_attempts"] == 0.0


def test_calculate_unbiased_benchmark_pass_at_k():
    """Test population-level unbiased pass@k calculation."""
    sample_population = {
        "task_1": [True, True, True, True],     # 4/4 correct -> pass@1 = 1.0, pass@2 = 1.0
        "task_2": [False, False, False, False], # 0/4 correct -> pass@1 = 0.0, pass@2 = 0.0
        "task_3": [True, False, False, False],  # 1/4 correct -> pass@1 = 0.25, pass@2 = 0.5
    }

    rates = calculate_unbiased_benchmark_pass_at_k(sample_population, k_list=[1, 2])

    # pass@1 expected: avg(1.0, 0.0, 0.25) * 100 = (1.25 / 3) * 100 ~= 41.67%
    expected_p1 = round((1.25 / 3) * 100, 2)
    assert rates["pass@1"] == expected_p1

    # pass@2 expected: task_3 pass@2 = 1 - comb(3, 2)/comb(4, 2) = 1 - 3/6 = 0.5
    # avg(1.0, 0.0, 0.5) * 100 = (1.5 / 3) * 100 = 50.0%
    assert rates["pass@2"] == 50.0
