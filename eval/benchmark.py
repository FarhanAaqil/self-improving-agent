"""Benchmark runner: official HumanEval (164 problems) and the repo's custom task suite.

Design rules that keep the numbers honest:
- Hidden tests are the official `check(candidate)` functions, run in the Docker sandbox.
- On failure the agent only learns the exception type (plus the message for errors raised
  by its own code). It never sees the assertion source, so it cannot fit to the tests.
- Baseline = one single-shot completion per problem; agent = up to k attempts with repair.
- Every result records whether it actually ran sandboxed; the run refuses to publish
  unsandboxed numbers unless explicitly allowed.

Usage:
    python -m eval.benchmark --problems 20 --attempts 3
    python -m eval.benchmark --suite custom
"""

import argparse
import glob
import gzip
import json
import math
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Callable

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app import llm  # noqa: E402
from app.config import MODEL, RESULTS_DIR, SANDBOX_TIMEOUT  # noqa: E402
from app.sandbox import run_code  # noqa: E402

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "HumanEval.jsonl.gz")
CUSTOM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_tasks")

SYSTEM = """You are an expert Python programmer.
Complete the given Python function. Return the complete function (with any imports it needs).
No markdown, no backticks, no explanations, no example usage."""


# ── Problem sets ─────────────────────────────────────────────

def load_humaneval(limit: int | None = None) -> list[dict[str, Any]]:
    with gzip.open(DATA_FILE, "rt", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    problems = [
        {
            "id": r["task_id"],
            "prompt": r["prompt"],
            "entry_point": r["entry_point"],
            "test": r["test"] + f"\n\ncheck({r['entry_point']})\n",
        }
        for r in rows
    ]
    return problems[:limit] if limit else problems


def load_custom(limit: int | None = None) -> list[dict[str, Any]]:
    import yaml

    problems = []
    for path in sorted(glob.glob(os.path.join(CUSTOM_DIR, "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if "task_id" in data:
            problems.append({
                "id": data["task_id"],
                "prompt": data["prompt"],
                "entry_point": data.get("entry_point", ""),
                "test": data["test"],
            })
    return problems[:limit] if limit else problems


SUITES: dict[str, Callable[[int | None], list[dict]]] = {"humaneval": load_humaneval, "custom": load_custom}


# ── Statistics ───────────────────────────────────────────────

def estimate_pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimator (Chen et al., 2021): 1 - C(n-c, k) / C(n, k)."""
    if n <= 0 or k <= 0 or n < k:
        return 0.0
    if c >= n or n - c < k:
        return 1.0
    return round(1.0 - math.comb(n - c, k) / math.comb(n, k), 4)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval, in percent. Honest error bars for small samples."""
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (round(max(0.0, centre - margin) * 100, 1), round(min(1.0, centre + margin) * 100, 1))


def pct(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


# ── Execution ────────────────────────────────────────────────

def build_program(problem: dict, completion: str) -> str:
    # The prompt goes first so helper functions it defines are available; a full
    # function in the completion simply redefines the stub.
    return f"{problem['prompt']}\n    pass\n\n{completion}\n\n{problem['test']}"


def safe_feedback(stderr: str | None, timed_out: bool) -> str:
    """Summarise a hidden-test failure without revealing the test source or values."""
    if timed_out:
        return "Hidden tests timed out. Your solution is probably too slow or loops forever."
    lines = [ln for ln in (stderr or "").strip().splitlines() if ln.strip()]
    last = lines[-1].strip() if lines else ""
    if not last:
        return "Hidden tests failed."
    if last.startswith("AssertionError"):
        return "Hidden tests failed: a returned value was wrong (AssertionError). Re-read the spec and edge cases."
    exc_type = last.split(":", 1)[0]
    # Only quote the message when the error was raised from the candidate's own code
    raised_in_test = any("in check" in ln for ln in lines[-6:])
    detail = "" if raised_in_test else last[:200]
    return f"Hidden tests failed with {exc_type}. {detail}".strip()


def _complete(prompt: str, model: str, feedback: str | None = None, previous: str | None = None) -> str:
    user = f"Complete this function:\n\n{prompt}"
    if feedback and previous:
        user += f"\n\nYour previous attempt:\n{previous}\n\nIt failed: {feedback}\nFix it."
    return llm.clean_code(llm.chat(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        model=model, temperature=0.1, max_tokens=1024,
    ))


def _run(problem: dict, completion: str) -> dict:
    result = run_code(build_program(problem, completion), timeout=SANDBOX_TIMEOUT)
    timed_out = "timed out" in (result.get("error") or "")
    return {
        "passed": bool(result["success"]),
        "sandboxed": bool(result.get("sandboxed")),
        "latency_ms": int(result.get("latency_ms") or 0),
        "feedback": None if result["success"] else safe_feedback(result.get("error"), timed_out),
    }


def evaluate_problem(problem: dict, model: str, attempts: int) -> dict:
    record: dict[str, Any] = {"problem_id": problem["id"], "entry_point": problem["entry_point"]}

    try:
        baseline_code = _complete(problem["prompt"], model)
        baseline = _run(problem, baseline_code)
    except Exception as e:
        baseline = {"passed": False, "sandboxed": False, "latency_ms": 0, "feedback": f"error: {e}"}
    record["baseline_passed"] = baseline["passed"]

    passed_at = None
    feedback = previous = None
    sandboxed = baseline["sandboxed"]
    latency = 0
    for attempt in range(1, attempts + 1):
        try:
            # Attempt 1 is an independent sample from the baseline, not a copy of it
            code = _complete(problem["prompt"], model, feedback, previous)
            outcome = _run(problem, code)
        except Exception as e:
            outcome = {"passed": False, "sandboxed": sandboxed, "latency_ms": 0, "feedback": f"error: {e}"}
            code = previous or ""
        sandboxed = sandboxed and outcome["sandboxed"]
        latency += outcome["latency_ms"]
        if outcome["passed"]:
            passed_at = attempt
            break
        feedback, previous = outcome["feedback"], code

    record.update(
        passed=passed_at is not None,
        passed_at_attempt=passed_at,
        attempts_used=passed_at or attempts,
        latency_ms=latency,
        sandboxed=sandboxed,
        last_feedback=None if passed_at else feedback,
    )
    return record


def summarize(results: list[dict], model: str, suite: str, attempts: int, usage: dict,
              eval_id: str, started: float) -> dict:
    n = len(results)
    first = sum(1 for r in results if r["passed_at_attempt"] == 1)
    solved = sum(1 for r in results if r["passed"])
    base = sum(1 for r in results if r["baseline_passed"])
    now = datetime.now()
    return {
        "eval_id": eval_id,
        "benchmark": suite,
        "suite": "official" if suite == "humaneval" else suite,
        "model": model,
        "date": now.date().isoformat(),
        "run_at": now.isoformat(),
        "duration_s": round(time.monotonic() - started, 1),
        "total_problems": n,
        "max_attempts": attempts,
        "sandboxed": all(r["sandboxed"] for r in results) if results else False,
        "baseline": {"pass_at_1": pct(base, n), "passed": base, "ci95": wilson_interval(base, n)},
        "agent": {
            "pass_at_1": pct(first, n),
            "solve_at_k": pct(solved, n),
            "k": attempts,
            "passed": solved,
            "ci95": wilson_interval(solved, n),
            "avg_attempts": round(sum(r["attempts_used"] for r in results) / n, 2) if n else 0.0,
        },
        "repair_gain_pct": round(pct(solved, n) - pct(base, n), 1),
        # Flat fields kept for the dashboard and older readers
        "pass_at_1": pct(first, n),
        "pass_at_5": pct(solved, n),
        "avg_attempts": round(sum(r["attempts_used"] for r in results) / n, 2) if n else 0.0,
        "avg_latency_ms": round(sum(r["latency_ms"] for r in results) / n, 1) if n else 0.0,
        "tokens": {"prompt": usage["prompt_tokens"], "completion": usage["completion_tokens"]},
        "results": results,
    }


def run_benchmark(
    suite: str = "humaneval",
    limit: int | None = 20,
    attempts: int = 3,
    model: str = MODEL,
    eval_id: str | None = None,
    allow_unsandboxed: bool = False,
    progress: Callable[[int, int, dict], None] | None = None,
) -> dict:
    problems = SUITES[suite](limit)
    eval_id = eval_id or f"{suite}_{datetime.now():%Y-%m-%d}_{uuid.uuid4().hex[:6]}"
    started = time.monotonic()
    results = []
    with llm.track_usage() as usage:
        for i, problem in enumerate(problems, 1):
            record = evaluate_problem(problem, model, attempts)
            if not record["sandboxed"] and not allow_unsandboxed:
                raise RuntimeError(
                    "Benchmark refused: code did not run in the Docker sandbox. "
                    "Start Docker or pass --allow-unsandboxed for a local, unpublished run."
                )
            results.append(record)
            if progress:
                progress(i, len(problems), record)
        return summarize(results, model, suite, attempts, usage, eval_id, started)


def save_results(summary: dict, results_dir: str = RESULTS_DIR) -> str:
    os.makedirs(results_dir, exist_ok=True)
    path = os.path.join(results_dir, f"{summary['eval_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agent benchmark.")
    parser.add_argument("--suite", choices=sorted(SUITES), default="humaneval")
    parser.add_argument("--problems", type=int, default=20, help="Number of problems (0 = all)")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--allow-unsandboxed", action="store_true")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    def show(i, total, record):
        mark = "PASS" if record["passed"] else "FAIL"
        print(f"[{i:>3}/{total}] {record['problem_id']:<16} {mark} "
              f"(attempt {record['passed_at_attempt'] or '-'}, baseline {'ok' if record['baseline_passed'] else 'x'})")

    summary = run_benchmark(
        suite=args.suite,
        limit=args.problems or None,
        attempts=args.attempts,
        model=args.model,
        allow_unsandboxed=args.allow_unsandboxed,
        progress=show,
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    if not args.no_save and summary["sandboxed"]:
        print("saved to", save_results(summary))


if __name__ == "__main__":
    main()
