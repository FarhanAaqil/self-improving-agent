"""Execution sandbox for untrusted, model-generated Python.

Code is piped to `python -` over stdin instead of being bind-mounted, which keeps
the container free of host paths and works when the API itself runs in a container
talking to a remote or proxied Docker daemon.
"""

import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from app.config import (
    ALLOW_UNSAFE_HOST_SUBPROCESS,
    MAX_CONCURRENT_SANDBOXES,
    MAX_OUTPUT_CHARS,
    SANDBOX_TIMEOUT,
)

SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "python:3.11-slim")
SANDBOX_MEMORY = os.getenv("SANDBOX_MEMORY", "256m")
SANDBOX_CPUS = os.getenv("SANDBOX_CPUS", "0.5")
SANDBOX_PIDS = os.getenv("SANDBOX_PIDS", "64")

_DOCKER_CHECK_TTL = 30.0
_docker_state: dict = {"ok": False, "checked_at": 0.0}
_docker_lock = threading.Lock()
_slots = threading.BoundedSemaphore(max(1, MAX_CONCURRENT_SANDBOXES))


def _is_docker_available() -> bool:
    """Cached `docker info` probe so health checks and runs don't pay ~1s each time."""
    with _docker_lock:
        if time.monotonic() - _docker_state["checked_at"] < _DOCKER_CHECK_TTL:
            return _docker_state["ok"]
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
            ok = res.returncode == 0
        except Exception:
            ok = False
        _docker_state.update(ok=ok, checked_at=time.monotonic())
        return ok


def docker_run_args(container_name: str) -> list[str]:
    """The full hardened `docker run` command. Exposed so /sandbox/config can show it."""
    return [
        "docker", "run",
        "-i",                                   # code arrives on stdin
        "--rm",
        "--name", container_name,
        "--network", "none",                    # no sockets out
        "--memory", SANDBOX_MEMORY,
        "--memory-swap", SANDBOX_MEMORY,        # same as memory: no swap escape hatch
        "--cpus", SANDBOX_CPUS,
        "--pids-limit", SANDBOX_PIDS,           # fork bombs hit a wall
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "65534:65534",                # nobody
        "--ulimit", "nofile=64:64",
        "--ulimit", "fsize=10485760:10485760",  # 10MB max file size
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "HOME=/tmp",
        "-w", "/tmp",
        SANDBOX_IMAGE,
        "python", "-u", "-",
    ]


def _clip(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.strip()
    if len(text) > MAX_OUTPUT_CHARS:
        dropped = len(text) - MAX_OUTPUT_CHARS
        return text[:MAX_OUTPUT_CHARS] + f"\n... [output truncated, {dropped} more characters]"
    return text


def _result(success, output, error, exit_code, latency_ms, sandboxed) -> dict:
    return {
        "success": success,
        "output": _clip(output),
        "error": _clip(error),
        "exit_code": exit_code,
        "latency_ms": latency_ms,
        "sandboxed": sandboxed,
    }


def _record(result: dict) -> dict:
    from app.observability import metrics

    outcome = "timeout" if "timed out" in (result.get("error") or "") else ("ok" if result["success"] else "error")
    metrics.inc("agent_sandbox_executions_total", outcome=outcome, sandboxed=str(result["sandboxed"]).lower())
    metrics.inc("agent_sandbox_seconds_sum", (result.get("latency_ms") or 0) / 1000)
    return result


def run_code(code: str, timeout: int = SANDBOX_TIMEOUT) -> dict:
    """
    Execute Python inside a locked-down Docker container. Refuses to run when Docker
    is unavailable unless ALLOW_UNSAFE_HOST_SUBPROCESS is explicitly enabled.
    Both stdout and stderr are always returned; `success` is exit code 0.
    """
    with _slots:
        if _is_docker_available():
            return _record(_run_docker(code, timeout))
        if ALLOW_UNSAFE_HOST_SUBPROCESS:
            return _record(_run_subprocess_fallback(code, timeout))
        return _result(
            False,
            None,
            "Execution rejected: Docker daemon is unavailable and unprivileged host "
            "execution is disabled (ALLOW_UNSAFE_HOST_SUBPROCESS=false).",
            -1,
            0,
            False,
        )


def _run_docker(code: str, timeout: int) -> dict:
    container_name = f"sandbox-{uuid.uuid4().hex[:12]}"
    start = time.monotonic()
    try:
        proc = subprocess.run(
            docker_run_args(container_name),
            input=code,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        # 125 means the docker client itself failed (bad flag, missing image, daemon gone)
        if proc.returncode == 125:
            return _result(False, None, f"Sandbox failed to start: {proc.stderr}", -1, elapsed_ms, False)
        return _result(proc.returncode == 0, proc.stdout, proc.stderr, proc.returncode, elapsed_ms, True)

    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        # The client is gone but the container may not be; kill it from the host side
        subprocess.run(["docker", "kill", container_name], capture_output=True)
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        return _result(False, None, f"Execution timed out after {timeout} seconds.", -1, elapsed_ms, True)

    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return _result(False, None, f"Sandbox error: {e}", -1, elapsed_ms, False)


def _limit_host_child():  # pragma: no cover - runs in the forked child on POSIX
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
    os.setsid()


def _run_subprocess_fallback(code: str, timeout: int) -> dict:
    """
    UNSAFE local fallback. Still strips the server's environment (API keys, tokens)
    and applies rlimits where the OS supports them, but it is not isolation.
    """
    start = time.monotonic()
    minimal_env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # Windows needs this to start Python
    }
    with tempfile.TemporaryDirectory(prefix="agent-run-") as workdir:
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-"],
                input=code,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=workdir,
                env=minimal_env,
                preexec_fn=_limit_host_child if os.name == "posix" else None,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return _result(proc.returncode == 0, proc.stdout, proc.stderr, proc.returncode, elapsed_ms, False)
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return _result(False, None, f"Execution timed out after {timeout} seconds.", -1, elapsed_ms, False)
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return _result(False, None, str(e), -1, elapsed_ms, False)
