"""Curated sandbox attacks for the "try to break it" panel.

Only these fixed scripts can be run; the caller picks a name, never the code.
They are the same files the adversarial test suite runs in CI.
"""

import os

from app.sandbox import run_code

ATTACK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adversarial")
OOM_KILLED = 137

ATTACKS: dict[str, dict] = {
    "fork_bomb": {
        "title": "Fork bomb",
        "description": "Calls os.fork() in a loop to exhaust the process table.",
        "timeout": 8,
    },
    "memory_exhaustion": {
        "title": "Memory bomb",
        "description": "Allocates 1 GB in 10 MB chunks.",
        "timeout": 8,
    },
    "outbound_network": {
        "title": "Phone home",
        "description": "Makes an HTTPS request to the internet.",
        "timeout": 8,
    },
    "host_secrets": {
        "title": "Steal secrets",
        "description": "Hunts for the Docker socket, API keys in env vars and host home dirs.",
        "timeout": 8,
    },
    "write_outside_tmp": {
        "title": "Tamper with the system",
        "description": "Writes into /etc, /root and the app directory.",
        "timeout": 8,
    },
    "tmp_exec": {
        "title": "Drop a payload",
        "description": "Writes a shell script to /tmp and tries to execute it.",
        "timeout": 8,
    },
    "privilege": {
        "title": "Become root",
        "description": "Checks for root and calls setuid(0).",
        "timeout": 8,
    },
    "outlive_timeout": {
        "title": "Outlive the timeout",
        "description": "Spawns a child process and hangs forever.",
        "timeout": 2,
    },
}


def list_attacks() -> list[dict]:
    return [{"name": name, "title": a["title"], "description": a["description"]} for name, a in ATTACKS.items()]


def run_attack(name: str) -> dict | None:
    spec = ATTACKS.get(name)
    if spec is None:
        return None
    with open(os.path.join(ATTACK_DIR, f"{name}.py"), encoding="utf-8") as f:
        code = f.read()
    result = run_code(code, timeout=spec["timeout"])

    output = result.get("output") or ""
    error = result.get("error") or ""
    leaked = "VULNERABILITY" in output
    timed_out = "timed out" in error.lower()
    blocked = (
        result.get("sandboxed", False)
        and not leaked
        and ("BLOCKED" in output or result.get("exit_code") == OOM_KILLED or timed_out)
    )
    if not result.get("sandboxed"):
        verdict = "Sandbox unavailable, so the attack was not run."
    elif leaked:
        verdict = "The attack got through."
    elif timed_out:
        verdict = "Killed by the host after the timeout."
    elif result.get("exit_code") == OOM_KILLED:
        verdict = "Killed by the kernel for using too much memory."
    else:
        verdict = output.strip().splitlines()[-1] if output.strip() else "Blocked."
    return {
        "name": name,
        "blocked": bool(blocked),
        "sandboxed": bool(result.get("sandboxed")),
        "verdict": verdict,
        "output": result.get("output"),
        "error": result.get("error"),
        "exit_code": result.get("exit_code"),
        "latency_ms": result.get("latency_ms", 0),
    }
