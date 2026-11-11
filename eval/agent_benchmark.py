"""Benchmark the real agent pipeline, judged by hidden HumanEval+ inputs.

The older `eval.benchmark` measures a bare complete-and-retry loop. This one runs the
actual product pipeline (spec tests first, sandbox verification, diagnosis, repair,
mutation-guided test strengthening, memory) and then asks an independent judge whether
the code it produced is really correct.

The agent never sees the hidden inputs or the judge's verdict, so the headline numbers
are honest answers to three questions:

  1. How often is the final code actually correct?            (hidden pass rate)
  2. When the agent stamps a run VERIFIED, how often is it wrong?   (false-verified rate)
  3. Does it do better the second time it meets a task?       (cold vs warm memory)

Usage:
    python -m eval.agent_benchmark --problems 40 --model openai/gpt-oss-20b
    python -m eval.agent_benchmark --conditions baseline,agent,hardened
"""

import argparse
import json
import os
import random
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# The experiment gets its own database and memory store, so it starts cold and never
# touches the developer's real runs. Must happen before any app module reads its config.
_WORKDIR = os.environ.get("AGENTBENCH_WORKDIR") or tempfile.mkdtemp(prefix="agentbench-")
os.environ["DB_PATH"] = os.path.join(_WORKDIR, "bench.db")
os.environ["MEMORY_DIR"] = os.path.join(_WORKDIR, "memory")
os.environ.setdefault("APP_ENV", "development")
os.environ["MEMORY_ENABLED"] = "true"

from app import db, llm  # noqa: E402
from app.config import MODEL, RESULTS_DIR  # noqa: E402
from app.pipeline import RunSpec, execute_run  # noqa: E402
from eval.benchmark import pct, wilson_interval  # noqa: E402
from eval.plus import judge, load_problems  # noqa: E402

BASELINE_SYSTEM = """You are an expert Python programmer.
Complete the given Python function. Return the complete function (with any imports it needs).
No markdown, no backticks, no explanations, no example usage."""

# name -> (description, RunSpec overrides). Order matters: "warm" reuses what "cold" learned.
CONDITIONS: dict[str, tuple[str, dict]] = {
    "baseline": ("One completion, no tests, no feedback", {}),
    "agent": ("Spec tests + repair loop", {"strengthen": False, "use_memory": False}),
    "hardened": ("+ mutation-guided stricter tests", {"strengthen": True, "use_memory": False}),
    "cold": ("+ memory, first encounter (empty memory)", {"strengthen": True, "use_memory": True}),
    "warm": ("+ memory, second encounter (same tasks again)", {"strengthen": True, "use_memory": True}),
}


def task_text(problem: dict) -> str:
    return (
        "Complete this Python function. Return the whole function, including any imports it needs.\n\n"
        + problem["prompt"]
    )


def run_baseline(problem: dict, model: str) -> dict:
    with llm.track_usage() as usage:
        code = llm.clean_code(llm.chat(
            [{"role": "system", "content": BASELINE_SYSTEM},
             {"role": "user", "content": f"Complete this function:\n\n{problem['prompt']}"}],
            model=model, temperature=0.1, max_tokens=1024,
        ))
        tokens = usage["prompt_tokens"] + usage["completion_tokens"]
    verdict = judge(problem, code)
    return {
        "problem_id": problem["id"], "self_verified": None, "attempts": 1, "first_try": None,
        "hidden_pass": verdict["passed"], "hidden_kind": verdict["kind"], "sandboxed": verdict["sandboxed"],
        "tokens": tokens, "mutation_score": None, "strengthened": None, "memories": 0,
    }


def run_agent(problem: dict, model: str, condition: str, attempts: int) -> dict:
    overrides = CONDITIONS[condition][1]
    # cold and warm share one workspace so the second pass can recall the first
    workspace = "memory" if overrides.get("use_memory") else condition
    spec = RunSpec(
        task=task_text(problem), model=model, max_attempts=attempts, workspace=workspace,
        review=False, **overrides,
    )
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    db.insert_run(run_id, spec.task, final_status="queued")
    db.update_run(run_id, workspace=workspace)
    status = execute_run(run_id, spec)
    crash = next((e["payload"]["crash"] for e in db.get_events(run_id) if e["type"] == "error" and e["payload"].get("crash")), None)
    if crash:
        # Not a verdict on the agent: raising keeps it out of the checkpoint, so a resume retries it
        raise RuntimeError(f"pipeline crashed with {crash}")
    run = db.get_run_with_attempts(run_id) or {}
    tries = run.get("attempts", [])
    passing = next((a for a in tries if a.get("success")), None)
    code = run.get("final_code") or (passing or (tries[-1] if tries else {})).get("generated_code", "")
    events = db.get_events(run_id)

    verdict = judge(problem, code) if code else {"passed": False, "kind": "no_code", "sandboxed": True}
    strengthened = next((e["payload"].get("outcome") for e in events if e["type"] == "tests_strengthened"), None)
    mutation = [e["payload"].get("score") for e in events if e["type"] == "mutation_tested"]
    recalled = next((len(e["payload"].get("memories", [])) for e in events if e["type"] == "memory_recalled"), 0)
    return {
        "problem_id": problem["id"],
        "self_verified": status == "success",
        "status": status,
        "attempts": run.get("total_attempts") or len(tries),
        "first_try": bool(passing and passing["attempt_number"] == 1),
        "hidden_pass": verdict["passed"],
        "hidden_kind": verdict["kind"],
        "sandboxed": verdict["sandboxed"] and all(a.get("sandboxed") in (1, True, None) for a in tries),
        "tokens": (run.get("prompt_tokens") or 0) + (run.get("completion_tokens") or 0),
        "mutation_score": mutation[-1] if mutation else None,
        "strengthened": strengthened,
        "memories": recalled,
    }


class Checkpoint:
    """Finished records, appended as they complete, so a long run survives a restart.

    Free-tier rate limits make a full experiment take hours. Resuming with the same
    AGENTBENCH_WORKDIR picks up where it stopped; crashed records are never saved, so
    they are retried.
    """

    def __init__(self, path: str, signature: dict):
        self.path = path
        self.signature = signature
        self._lock = threading.Lock()
        self.done: dict[tuple[str, str], dict] = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    row = json.loads(line)
                    if row.get("signature") == signature:
                        self.done[(row["condition"], row["record"]["problem_id"])] = row["record"]

    def get(self, condition: str, problem_id: str) -> dict | None:
        return self.done.get((condition, problem_id))

    def save(self, condition: str, record: dict) -> None:
        with self._lock:
            self.done[(condition, record["problem_id"])] = record
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"signature": self.signature, "condition": condition, "record": record}) + "\n")


def summarize_condition(name: str, records: list[dict]) -> dict:
    n = len(records)
    correct = sum(r["hidden_pass"] for r in records)
    known_tokens = [r["tokens"] for r in records if r.get("tokens")]
    summary = {
        "condition": name,
        "description": CONDITIONS[name][0],
        "problems": n,
        "hidden_pass": correct,
        "hidden_pass_rate": pct(correct, n),
        "hidden_pass_ci95": wilson_interval(correct, n),
        "avg_tokens": round(sum(known_tokens) / len(known_tokens)) if known_tokens else None,
        "sandboxed": all(r["sandboxed"] for r in records),
        # Runs that crashed (for example an exhausted rate limit) count as failures; this says how many
        "errors": sum(1 for r in records if str(r.get("hidden_kind") or "").startswith("error:")),
    }
    if name == "baseline":
        return summary

    verified = [r for r in records if r["self_verified"]]
    wrong = [r for r in verified if not r["hidden_pass"]]
    scores = [r["mutation_score"] for r in records if r["mutation_score"] is not None]
    summary.update(
        self_verified=len(verified),
        self_verified_rate=pct(len(verified), n),
        false_verified=len(wrong),
        false_verified_rate=pct(len(wrong), len(verified)),
        false_verified_ci95=wilson_interval(len(wrong), len(verified)),
        false_verified_ids=[r["problem_id"] for r in wrong],
        first_try_rate=pct(sum(r["first_try"] for r in records), n),
        avg_attempts=round(sum(r["attempts"] for r in records) / n, 2) if n else 0,
        avg_mutation_score=round(sum(scores) / len(scores), 3) if scores else None,
        strengthening={
            outcome: sum(1 for r in records if r["strengthened"] == outcome)
            for outcome in ("kept", "found_bug", "discarded")
        },
        runs_that_recalled_memory=sum(1 for r in records if r["memories"]),
    )
    return summary


def pick_problems(count: int, seed: int) -> list[dict]:
    problems = list(load_problems())
    if count and count < len(problems):
        problems = random.Random(seed).sample(problems, count)
    return sorted(problems, key=lambda p: int(p["id"].split("/")[1]))


def run_experiment(
    conditions: list[str],
    count: int = 40,
    model: str = MODEL,
    attempts: int = 3,
    seed: int = 7,
    workers: int = 3,
    progress=None,
) -> dict:
    db.init_db()
    problems = pick_problems(count, seed)
    started = time.monotonic()
    summaries, details = [], {}
    checkpoint = Checkpoint(
        os.path.join(_WORKDIR, "records.jsonl"),
        {"model": model, "attempts": attempts, "seed": seed, "count": count},
    )

    for name in conditions:
        def one(problem, name=name):
            saved = checkpoint.get(name, problem["id"])
            if saved is not None:
                return saved
            try:
                record = run_baseline(problem, model) if name == "baseline" else run_agent(problem, model, name, attempts)
                checkpoint.save(name, record)
            except Exception as e:  # a crashed run is a failed run, not a crashed benchmark
                record = {
                    "problem_id": problem["id"], "self_verified": False, "status": "error", "attempts": 0,
                    "first_try": False, "hidden_pass": False, "hidden_kind": f"error:{type(e).__name__}",
                    "sandboxed": True, "tokens": 0, "mutation_score": None, "strengthened": None, "memories": 0,
                }
            if progress:
                progress(name, record)
            return record

        with ThreadPoolExecutor(max_workers=workers) as pool:
            records = list(pool.map(one, problems))
        details[name] = records
        summaries.append(summarize_condition(name, records))
        if not summaries[-1]["sandboxed"]:
            raise RuntimeError("Benchmark refused: something ran outside the Docker sandbox.")

    now = datetime.now()
    return {
        "eval_id": f"agentbench_{now:%Y-%m-%d}_{uuid.uuid4().hex[:6]}",
        "kind": "agent_benchmark",
        "suite": "humaneval_plus",
        "model": model,
        "date": now.date().isoformat(),
        "run_at": now.isoformat(),
        "duration_s": round(time.monotonic() - started, 1),
        "total_problems": len(problems),
        "max_attempts": attempts,
        "seed": seed,
        "problem_ids": [p["id"] for p in problems],
        "conditions": summaries,
        "records": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--problems", type=int, default=40, help="How many problems (0 = all 164)")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--conditions", default=",".join(CONDITIONS))
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    names = [c.strip() for c in args.conditions.split(",") if c.strip()]
    unknown = set(names) - set(CONDITIONS)
    if unknown:
        parser.error(f"Unknown conditions: {sorted(unknown)}")

    def show(name, record):
        mark = "ok " if record["hidden_pass"] else "BAD"
        verified = {True: "verified", False: "unverified", None: "-"}[record["self_verified"]]
        why = "" if record["hidden_pass"] else f" ({record['hidden_kind']})"
        print(f"[{name:<9}] {record['problem_id']:<14} hidden:{mark} {verified:<10} attempts:{record['attempts']}{why}", flush=True)

    result = run_experiment(names, args.problems, args.model, args.attempts, args.seed, args.workers, show)
    print(json.dumps(result["conditions"], indent=2))
    if not args.no_save:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        path = os.path.join(RESULTS_DIR, f"{result['eval_id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print("saved to", path)


if __name__ == "__main__":
    main()
