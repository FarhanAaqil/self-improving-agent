# ── eval/custom_runner.py ───────────────────────────────────
# Custom developer tasks runner — same shape as humaneval_runner.py.

import argparse
import glob
import json
import os
import sys
from datetime import date
from typing import Any

import yaml

# Ensure project root is in path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.config import MODEL, RESULTS_DIR, SANDBOX_TIMEOUT  # noqa: E402
from app.sandbox import run_code  # noqa: E402
from eval.humaneval_runner import calculate_pass_at_k_metrics  # noqa: E402

CUSTOM_TASKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_tasks")


def load_custom_tasks(tasks_dir: str = CUSTOM_TASKS_DIR) -> list[dict[str, Any]]:
    """Load all YAML task specifications from custom_tasks directory."""
    files = sorted(glob.glob(os.path.join(tasks_dir, "*.yaml")))
    tasks = []
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data and "task_id" in data:
                tasks.append(data)
    return tasks


def run_custom_evaluation(
    tasks: list[dict[str, Any]] | None = None,
    output_dir: str = RESULTS_DIR,
    model: str = MODEL,
    max_attempts: int = 5,
    api_client: Any = None,
) -> dict[str, Any]:
    """Run all custom YAML tasks through /generate-and-repair and write dated JSON."""
    if tasks is None:
        tasks = load_custom_tasks()

    os.makedirs(output_dir, exist_ok=True)
    today_str = date.today().isoformat()
    eval_id = f"custom_{today_str}"

    results = []

    for task in tasks:
        task_id = task.get("task_id", "custom_task")
        task_prompt = f"Write Python code to solve this task:\n\n{task['prompt']}"
        test_script = task["test"]

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
            "task_id": task_id,
            "name": task.get("name", task_id),
            "passed": passed,
            "passed_at_attempt": passed_attempt,
            "attempts_used": attempts_used,
            "latency_ms": total_latency,
            "final_code": final_code,
        })

    metrics = calculate_pass_at_k_metrics(results)

    eval_payload = {
        "eval_id": eval_id,
        "benchmark": "custom_tasks",
        "date": today_str,
        "model": model,
        "total_problems": len(tasks),
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
    parser = argparse.ArgumentParser(description="Custom tasks evaluation runner")
    parser.add_argument("--tasks-dir", type=str, default=CUSTOM_TASKS_DIR)
    parser.add_argument("--model", type=str, default=MODEL)
    args = parser.parse_args()

    loaded_tasks = load_custom_tasks(args.tasks_dir)
    payload = run_custom_evaluation(loaded_tasks, model=args.model)
    print(f"Custom evaluation complete: pass@1={payload['pass_at_1']}%, pass@5={payload['pass_at_5']}%")
