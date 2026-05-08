# ── sandbox.py ─────────────────────────────────────────────
# The Sandbox: runs generated code in a subprocess with a timeout.
# Week 1 uses subprocess (no Docker needed).
# Week 2 will upgrade this to a Docker-isolated container.

import subprocess
import sys
import tempfile
import os
from config import SANDBOX_TIMEOUT


def run_code(code: str) -> dict:
    """
    Write code to a temp file and run it in a subprocess.
    Returns a dict with:
        success (bool)   — did it run without errors?
        output  (str)    — stdout if success
        error   (str)    — full traceback if failure
    """

    # Write code to a temporary .py file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],   # run with current Python interpreter
            capture_output=True,
            text=True,
            timeout=SANDBOX_TIMEOUT,
        )

        if result.returncode == 0:
            return {
                "success": True,
                "output": result.stdout.strip(),
                "error": None,
            }
        else:
            # returncode != 0 means the script crashed — stderr has the traceback
            return {
                "success": False,
                "output": None,
                "error": result.stderr.strip(),
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": None,
            "error": f"Execution timed out after {SANDBOX_TIMEOUT} seconds. "
                     f"Check for infinite loops.",
        }

    except Exception as e:
        return {"success": False, "output": None, "error": str(e)}

    finally:
        # Always clean up the temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)