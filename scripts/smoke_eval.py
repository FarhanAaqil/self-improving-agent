"""Smoke evaluation runner for CI.

Runs a fast subset (default 8 problems) of HumanEval to detect regressions.
Gated on GROQ_API_KEY being set; skips gracefully for external contributors.
Enforces a regression threshold: fails the build if pass@1 drops more than
10 percentage points below the latest committed benchmark result.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure repo root in sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from eval.humaneval_problems import PROBLEMS  # noqa: E402
from eval.humaneval_runner import run_humaneval_evaluation  # noqa: E402


def get_baseline_pass_at_1(results_dir: Path) -> float:
    """Find the latest committed humaneval results JSON and return pass@1."""
    if not results_dir.exists():
        return 80.0

    result_files = sorted(results_dir.glob("humaneval_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not result_files:
        return 80.0

    try:
        with open(result_files[0], encoding="utf-8") as f:
            data = json.load(f)
            return float(data.get("pass_at_1", 80.0))
    except Exception as e:
        print(f"[Smoke Eval] Warning: Could not read baseline from {result_files[0]}: {e}")
        return 80.0


def run_mock_smoke(num_problems: int) -> dict:
    """Simulate a smoke eval run without external API calls for testing."""
    # 7 out of 8 pass attempt 1 (87.5% pass@1)
    results = []
    for i in range(num_problems):
        passed_at_1 = i != 2  # 1 failure
        results.append({
            "task_id": f"Smoke/{i}",
            "passed": True if passed_at_1 else False,
            "passed_at_attempt": 1 if passed_at_1 else None,
            "attempts_used": 1 if passed_at_1 else 3,
            "latency_ms": 50,
            "final_code": "def solve(): return 42",
        })

    pass_1_cnt = sum(1 for r in results if r["passed_at_attempt"] == 1)
    pass_at_1 = round((pass_1_cnt / num_problems) * 100.0, 2)
    return {
        "total_problems": num_problems,
        "pass_at_1": pass_at_1,
        "pass_at_5": pass_at_1,
        "avg_attempts": 1.25,
        "avg_latency_ms": 50.0,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="CI Smoke Evaluation Runner")
    parser.add_argument("--problems", type=int, default=8, help="Number of problems to smoke test (default 8)")
    parser.add_argument("--threshold-drop", type=float, default=10.0, help="Max allowed drop in pass@1 vs baseline")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode for offline testing")
    args = parser.parse_args()

    api_key = os.getenv("GROQ_API_KEY")
    if not args.mock and (not api_key or not api_key.strip() or api_key == "mock-api-key"):
        print("[Smoke Eval] GROQ_API_KEY is not set or empty. Skipping smoke eval gracefully for fork/PR.")
        sys.exit(0)

    results_dir = _ROOT / "results"
    baseline_pass_at_1 = get_baseline_pass_at_1(results_dir)
    min_acceptable_pass_at_1 = max(0.0, baseline_pass_at_1 - args.threshold_drop)

    print("=" * 60)
    print(f"[Smoke Eval] Starting smoke evaluation on {args.problems} problems...")
    print(f"[Smoke Eval] Baseline pass@1: {baseline_pass_at_1:.1f}%")
    print(f"[Smoke Eval] Minimum acceptable pass@1 threshold: {min_acceptable_pass_at_1:.1f}%")
    print("=" * 60)

    if args.mock:
        payload = run_mock_smoke(args.problems)
    else:
        smoke_subset = PROBLEMS[:args.problems]
        payload = run_humaneval_evaluation(
            problems=smoke_subset,
            output_dir=str(results_dir),
            max_attempts=3,
        )

    pass_at_1 = payload["pass_at_1"]
    pass_at_5 = payload["pass_at_5"]
    print("\n[Smoke Eval] Results Summary:")
    print(f"  Total Problems : {payload['total_problems']}")
    print(f"  Smoke pass@1   : {pass_at_1:.1f}%")
    print(f"  Smoke pass@5   : {pass_at_5:.1f}%")
    print(f"  Avg Attempts   : {payload['avg_attempts']:.2f}")

    if pass_at_1 < min_acceptable_pass_at_1:
        print("\n[Smoke Eval] [FAIL] REGRESSION DETECTED!")
        print(f"  pass@1 ({pass_at_1:.1f}%) dropped > {args.threshold_drop:.1f}% below baseline ({baseline_pass_at_1:.1f}%).")
        print("  Failing CI build to protect baseline performance.")
        sys.exit(1)

    print("\n[Smoke Eval] [OK] PASSED: pass@1 is within acceptable performance threshold.")
    sys.exit(0)


if __name__ == "__main__":
    main()
