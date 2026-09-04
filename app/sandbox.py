# ── app/sandbox.py ──────────────────────────────────────────
# Sandbox execution layer.
# Moved from root sandbox.py into app/ with updated imports.
#
# NOTE: This version still uses subprocess.run() directly — the
# UNSANDBOXED baseline. Day 2 replaces this entirely with a
# Docker-based implementation using:
#   --network none, --memory=256m, --cpus=0.5,
#   --read-only, --tmpfs /tmp, host-side timeout.
#
# Do NOT add features here. This file is scheduled for full
# rewrite on Day 2 — any changes here will be thrown away.

import subprocess
import sys
import tempfile
import os
from app.config import SANDBOX_TIMEOUT


def run_code(code: str) -> dict:
    """
    Write code to a temp file and run it in a subprocess.

    Returns a dict with:
        success  (bool) — did it run without errors?
        output   (str)  — stdout if success
        error    (str)  — full traceback if failure
        exit_code (int) — process exit code
        latency_ms (int) — wall-clock time in milliseconds

    TODO Day 2: replace this with Docker sandbox execution.
    """
    import time

    # Windows defaults to cp1252; force utf-8 so unicode in generated code doesn't explode
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name

    start = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=SANDBOX_TIMEOUT,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if result.returncode == 0:
            return {
                "success": True,
                "output": result.stdout.strip(),
                "error": None,
                "exit_code": 0,
                "latency_ms": elapsed_ms,
            }
        else:
            return {
                "success": False,
                "output": None,
                "error": result.stderr.strip(),
                "exit_code": result.returncode,
                "latency_ms": elapsed_ms,
            }

    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "output": None,
            "error": f"Execution timed out after {SANDBOX_TIMEOUT} seconds.",
            "exit_code": -1,
            "latency_ms": elapsed_ms,
        }

    except Exception as e:
        return {"success": False, "output": None, "error": str(e), "exit_code": -1, "latency_ms": 0}

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
