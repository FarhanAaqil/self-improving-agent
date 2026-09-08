# ── eval/humaneval_runner.py ─────────────────────────────────
# HumanEval evaluation runner driving problems through /generate-and-repair.

import argparse
import json
import math
import os
import sys
from datetime import date
from typing import Any

# Ensure project root is in path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.config import MODEL, RESULTS_DIR, SANDBOX_TIMEOUT  # noqa: E402
from app.sandbox import run_code  # noqa: E402
from eval.humaneval_problems import PROBLEMS  # noqa: E402


def estimate_pass_at_k(n: int, c: int, k: int) -> float:
    """
    Calculate unbiased pass@k estimator:
    pass@k = 1.0 - (comb(n - c, k) / comb(n, k))
    Returns 1.0 if n - c < k (all failure combos impossible).
    """
    if n <= 0 or k <= 0 or n < k:
        return 0.0
    if c >= n or n - c < k:
        return 1.0
    try:
        comb_fail = math.comb(n - c, k)
        comb_total = math.comb(n, k)
        return round(1.0 - (comb_fail / comb_total), 4)
    except (ValueError, ZeroDivisionError):
        return 0.0


def calculate_unbiased_benchmark_pass_at_k(
    samples_per_problem: dict[str, list[bool]],
    k_list: list[int] = (1, 5),
) -> dict[str, float]:
    """
    Compute aggregate unbiased pass@k across all problems:
    average of estimate_pass_at_k(n, c, k) for each problem.
    """
    if not samples_per_problem:
        return {f"pass@{k}": 0.0 for k in k_list}

    aggregates: dict[int, list[float]] = {k: [] for k in k_list}
    for _pid, outcomes in samples_per_problem.items():
        n = len(outcomes)
        c = sum(1 for passed in outcomes if passed)
        for k in k_list:
            if n >= k:
                aggregates[k].append(estimate_pass_at_k(n, c, k))

    return {
        f"pass@{k}": round((sum(vals) / len(vals)) * 100.0, 2) if vals else 0.0
        for k, vals in aggregates.items()
    }


def calculate_pass_at_k_metrics(problem_results: list[dict[str, Any]]) -> dict[str, float]:
    """
    Calculate pass@1, pass@5, avg_attempts, and avg_latency_ms from problem results.
    For an iterative repair agent:
      pass@1 is the fraction of problems solved on attempt 1.
      pass@5 is the fraction of problems solved in <= 5 attempts.
    """
    if not problem_results:
        return {
            "pass_at_1": 0.0,
            "pass_at_5": 0.0,
            "avg_attempts": 0.0,
            "avg_latency_ms": 0.0,
        }

    total = len(problem_results)
    pass_1_count = sum(1 for r in problem_results if r.get("passed_at_attempt") == 1)
    pass_5_count = sum(
        1 for r in problem_results
        if r.get("passed") and (r.get("passed_at_attempt", 999) <= 5)
    )

    total_attempts = sum(r.get("attempts_used", 1) for r in problem_results)
    total_latency = sum(r.get("latency_ms", 0) for r in problem_results)

    return {
        "pass_at_1": round((pass_1_count / total) * 100.0, 2),
        "pass_at_5": round((pass_5_count / total) * 100.0, 2),
        "avg_attempts": round(total_attempts / total, 2),
        "avg_latency_ms": round(total_latency / total, 1),
    }


def run_humaneval_evaluation(
    problems: list[dict[str, Any]],
    output_dir: str = RESULTS_DIR,
    model: str = MODEL,
    max_attempts: int = 5,
    api_client: Any = None,
) -> dict[str, Any]:
    """Run problems through /generate-and-repair and write dated results JSON."""
    os.makedirs(output_dir, exist_ok=True)
    today_str = date.today().isoformat()
    eval_id = f"humaneval_{today_str}"

    results = []

    for idx, prob in enumerate(problems):
        task_prompt = f"Complete the following Python function:\n\n{prob['prompt']}"
        test_script = prob["test"]

        # Call generate and repair endpoint or test client
        passed = False
        passed_attempt = None
        attempts_used = 0
        total_latency = 0
        final_code = ""

        try:
            if api_client is not None:
                resp = api_client.post(
                    "/generate-and-repair",
                    json={
                        "task_description": task_prompt,
                        "max_attempts": max_attempts,
                        "model": model,
                    },
                )
                run_data = resp.json()
                attempts_used = run_data.get("total_attempts", 1)
                attempts_list = run_data.get("attempts", [])
                for att in attempts_list:
                    total_latency += att.get("latency_ms") or 0
                    test_exec = run_code(
                        f"{att['generated_code']}\n\n{test_script}",
                        timeout=SANDBOX_TIMEOUT,
                    )
                    if test_exec["success"]:
                        passed = True
                        passed_attempt = att["attempt_number"]
                        final_code = att["generated_code"]
                        break
            else:
                from fastapi.testclient import TestClient

                from app.main import app
                client = TestClient(app)
                resp = client.post(
                    "/generate-and-repair",
                    json={
                        "task_description": task_prompt,
                        "max_attempts": max_attempts,
                        "model": model,
                    },
                )
                run_data = resp.json()
                attempts_used = run_data.get("total_attempts", 1)
                attempts_list = run_data.get("attempts", [])
                for att in attempts_list:
                    total_latency += att.get("latency_ms") or 0
                    test_exec = run_code(
                        f"{att['generated_code']}\n\n{test_script}",
                        timeout=SANDBOX_TIMEOUT,
                    )
                    if test_exec["success"]:
                        passed = True
                        passed_attempt = att["attempt_number"]
                        final_code = att["generated_code"]
                        break
        except Exception as e:
            passed = False
            attempts_used = 1
            final_code = str(e)

        results.append({
            "task_id": prob.get("task_id", f"HumanEval/{idx}"),
            "passed": passed,
            "passed_at_attempt": passed_attempt,
            "attempts_used": attempts_used,
            "latency_ms": total_latency,
            "final_code": final_code,
        })

    metrics = calculate_pass_at_k_metrics(results)

    eval_payload = {
        "eval_id": eval_id,
        "benchmark": "humaneval",
        "date": today_str,
        "model": model,
        "total_problems": len(problems),
        "pass_at_1": metrics["pass_at_1"],
        "pass_at_5": metrics["pass_at_5"],
        "avg_attempts": metrics["avg_attempts"],
        "avg_latency_ms": metrics["avg_latency_ms"],
        "results": results,
    }

    out_file = os.path.join(output_dir, f"{eval_id}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(eval_payload, f, indent=2)

    return eval_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HumanEval evaluation runner")
    parser.add_argument("--subset", type=int, default=50, help="Subset size (default 50)")
    parser.add_argument("--model", type=str, default=MODEL)
    args = parser.parse_args()

    subset_problems = PROBLEMS[:args.subset] if args.subset else PROBLEMS
    payload = run_humaneval_evaluation(subset_problems, model=args.model)
    print(f"Completed evaluation: pass@1={payload['pass_at_1']}%, pass@5={payload['pass_at_5']}%")
