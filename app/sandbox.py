import os
import subprocess
import sys
import tempfile
import time
import uuid
from app.config import SANDBOX_TIMEOUT

SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "python:3.11-slim")


def _is_docker_available() -> bool:
    try:
        res = subprocess.run(["docker", "info"], capture_output=True, timeout=3)
        return res.returncode == 0
    except Exception:
        return False


def _to_docker_volume_path(path: str) -> str:
    # Windows drive paths (D:\foo\bar) must use forward slashes for Docker mounts
    abs_path = os.path.abspath(path)
    return abs_path.replace("\\", "/")


def run_code(code: str, timeout: int = SANDBOX_TIMEOUT) -> dict:
    """
    Executes Python code inside an isolated Docker container with zero network,
    strict memory/CPU caps, and read-only filesystem.
    Falls back to local subprocess if Docker daemon is not active.
    """
    # Windows note: force utf-8 so unicode symbols in LLM code don't fail with cp1252
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_script = f.name

    try:
        if not _is_docker_available():
            return _run_subprocess_fallback(tmp_script, timeout)
        return _run_docker(tmp_script, timeout)
    finally:
        if os.path.exists(tmp_script):
            os.unlink(tmp_script)


def _run_docker(script_path: str, timeout: int) -> dict:
    container_name = f"sandbox-{uuid.uuid4().hex[:8]}"
    volume_mount = f"{_to_docker_volume_path(script_path)}:/app/script.py:ro"

    cmd = [
        "docker", "run",
        "--name", container_name,
        "--rm",
        "--network", "none",         # no outbound socket or network access
        "--memory", "256m",          # hard cap; triggers OOM kill on abuse
        "--cpus", "0.5",             # throttle CPU consumption
        "--read-only",               # immutable root filesystem
        "--tmpfs", "/tmp:rw,size=64m",  # only /tmp is scratch-writable
        "-v", volume_mount,
        "-w", "/app",
        SANDBOX_IMAGE,
        "python", "/app/script.py",
    ]

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)

        return {
            "success": proc.returncode == 0,
            "output": proc.stdout.strip() if proc.returncode == 0 else None,
            "error": proc.stderr.strip() if proc.returncode != 0 else None,
            "exit_code": proc.returncode,
            "latency_ms": elapsed_ms,
            "sandboxed": True,
        }

    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        # Host-side enforcement: terminate container directly if it refuses to yield
        subprocess.run(["docker", "kill", container_name], capture_output=True)
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        return {
            "success": False,
            "output": None,
            "error": f"Execution timed out after {timeout} seconds.",
            "exit_code": -1,
            "latency_ms": elapsed_ms,
            "sandboxed": True,
        }

    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "output": None,
            "error": str(e),
            "exit_code": -1,
            "latency_ms": elapsed_ms,
            "sandboxed": True,
        }


def _run_subprocess_fallback(script_path: str, timeout: int) -> dict:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": proc.returncode == 0,
            "output": proc.stdout.strip() if proc.returncode == 0 else None,
            "error": proc.stderr.strip() if proc.returncode != 0 else None,
            "exit_code": proc.returncode,
            "latency_ms": elapsed_ms,
            "sandboxed": False,
        }
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "output": None,
            "error": f"Execution timed out after {timeout} seconds.",
            "exit_code": -1,
            "latency_ms": elapsed_ms,
            "sandboxed": False,
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "output": None,
            "error": str(e),
            "exit_code": -1,
            "latency_ms": elapsed_ms,
            "sandboxed": False,
        }
