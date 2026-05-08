# ── benchmark.py ───────────────────────────────────────────
# Week 4: Benchmarking — Windows + Linux compatible
# Measures runtime (timeit) and memory (tracemalloc) before/after critique.

import timeit
import tracemalloc
import subprocess
import sys
import tempfile
import os
import json
from datetime import datetime
from config import BENCHMARK_RUNS, BENCHMARK_TIMEOUT, LOG_DIR


def _write_temp(code: str) -> str:
    """
    Write code to a UTF-8 temp file. Returns the file path.
    Explicit UTF-8 encoding fixes Windows cp1252 UnicodeEncodeError.
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8",   # ← fix: force utf-8, never cp1252
    ) as f:
        f.write(code)
        return f.name


def benchmark_code(code: str, runs: int = BENCHMARK_RUNS) -> dict:
    """
    Benchmark a piece of Python code.
    Returns avg/min/max runtime in ms and peak memory in KB.
    """
    wrapped = (
        "import tracemalloc, json, sys\n"
        "tracemalloc.start()\n\n"
        f"{code}\n\n"
        "current, peak = tracemalloc.get_traced_memory()\n"
        "tracemalloc.stop()\n"
        'print("__BENCH__:" + json.dumps({"peak_bytes": peak}), file=sys.stderr)\n'
    )

    tmp = _write_temp(wrapped)
    runtimes = []
    peak_kb  = 0.0
    error    = None

    try:
        # ── Collect peak memory on first run ─────────────────
        try:
            result = subprocess.run(
                [sys.executable, tmp],
                capture_output=True,
                text=True,
                encoding="utf-8",       # ← fix: explicit utf-8 on subprocess output
                errors="replace",       # ← replace any undecodable chars safely
                timeout=BENCHMARK_TIMEOUT,
            )
            if result.returncode == 0:
                for line in result.stderr.splitlines():
                    if line.startswith("__BENCH__:"):
                        data    = json.loads(line.replace("__BENCH__:", ""))
                        peak_kb = data["peak_bytes"] / 1024
            else:
                error = result.stderr
        except subprocess.TimeoutExpired:
            error = f"Timed out after {BENCHMARK_TIMEOUT}s"

        # ── Collect timing across N runs ──────────────────────
        if not error:
            timer = timeit.Timer(
                stmt=f"subprocess.run([r'{sys.executable}', r'{tmp}'], capture_output=True)",
                setup="import subprocess",
            )
            try:
                times_sec = timer.repeat(repeat=runs, number=1)
                runtimes  = [round(t * 1000, 2) for t in times_sec]
            except Exception as e:
                error = str(e)

    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

    if error or not runtimes:
        return {
            "success":        False,
            "avg_runtime_ms": 0,
            "min_runtime_ms": 0,
            "max_runtime_ms": 0,
            "peak_memory_kb": 0,
            "runs":           0,
            "error":          error or "No timing data collected",
        }

    return {
        "success":        True,
        "avg_runtime_ms": round(sum(runtimes) / len(runtimes), 2),
        "min_runtime_ms": round(min(runtimes), 2),
        "max_runtime_ms": round(max(runtimes), 2),
        "peak_memory_kb": round(peak_kb, 2),
        "runs":           len(runtimes),
        "error":          None,
    }


def benchmark_memory_only(code: str) -> float:
    """
    Fast memory-only benchmark using tracemalloc in a subprocess.
    Returns peak memory in KB, or 0.0 on failure.
    """
    wrapped = (
        "import tracemalloc, json, sys\n"
        "tracemalloc.start()\n\n"
        f"{code}\n\n"
        "current, peak = tracemalloc.get_traced_memory()\n"
        "tracemalloc.stop()\n"
        'print(json.dumps({"peak_bytes": peak}))\n'
    )

    tmp = _write_temp(wrapped)
    try:
        result = subprocess.run(
            [sys.executable, tmp],
            capture_output=True,
            text=True,
            encoding="utf-8",       # ← fix
            errors="replace",
            timeout=BENCHMARK_TIMEOUT,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            return round(data["peak_bytes"] / 1024, 2)
    except Exception:
        pass
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return 0.0


def compare(before: dict, after: dict) -> dict:
    """Compare two benchmark results. Returns deltas and improvement flags."""
    if not before["success"] or not after["success"]:
        return {"valid": False}

    runtime_delta = before["avg_runtime_ms"] - after["avg_runtime_ms"]
    memory_delta  = before["peak_memory_kb"] - after["peak_memory_kb"]

    runtime_pct = (runtime_delta / before["avg_runtime_ms"] * 100) if before["avg_runtime_ms"] > 0 else 0
    memory_pct  = (memory_delta  / before["peak_memory_kb"]  * 100) if before["peak_memory_kb"]  > 0 else 0

    return {
        "valid":            True,
        "runtime_delta_ms": round(runtime_delta, 2),
        "runtime_improved": runtime_delta > 0,
        "runtime_pct":      round(runtime_pct, 1),
        "memory_delta_kb":  round(memory_delta, 2),
        "memory_improved":  memory_delta > 0,
        "memory_pct":       round(memory_pct, 1),
        "overall_improved": runtime_delta > 0 or memory_delta > 0,
    }


def log_benchmark(task: str, before: dict, after: dict, comparison: dict):
    """Append benchmark results to logs/benchmarks.jsonl"""
    os.makedirs(LOG_DIR, exist_ok=True)
    entry = {
        "timestamp":  datetime.now().isoformat(),
        "task":       task,
        "before":     before,
        "after":      after,
        "comparison": comparison,
    }
    with open(os.path.join(LOG_DIR, "benchmarks.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")