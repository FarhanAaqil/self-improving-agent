"""Adversarial sandbox tests. Each fixture is a real attack run inside the live sandbox.

A test only passes when the attack is visibly stopped: the script reports BLOCKED
(or is killed by the kernel), and never prints VULNERABILITY.
"""

import os

import pytest

from app.sandbox import _is_docker_available, run_code

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "adversarial")

OOM_KILLED = 137


@pytest.fixture(autouse=True)
def require_docker():
    if not _is_docker_available():
        pytest.skip("Docker daemon not running — isolation tests require active Docker engine")


def _attack(filename: str, timeout: int = 8) -> dict:
    with open(os.path.join(FIXTURES_DIR, filename), encoding="utf-8") as f:
        result = run_code(f.read(), timeout=timeout)
    assert result["sandboxed"] is True, f"{filename} did not run inside Docker: {result['error']}"
    assert "VULNERABILITY" not in (result.get("output") or ""), result["output"]
    assert not result["success"]
    return result


def _blocked(result: dict) -> bool:
    return "BLOCKED" in (result.get("output") or "")


@pytest.mark.sandbox
def test_outbound_network_blocked():
    assert _blocked(_attack("outbound_network.py"))


@pytest.mark.sandbox
def test_host_secrets_not_visible():
    assert _blocked(_attack("host_secrets.py"))


@pytest.mark.sandbox
def test_fork_bomb_hits_pids_limit():
    assert _blocked(_attack("fork_bomb.py"))


@pytest.mark.sandbox
def test_memory_exhaustion_capped():
    result = _attack("memory_exhaustion.py")
    assert _blocked(result) or result["exit_code"] == OOM_KILLED


@pytest.mark.sandbox
def test_write_outside_tmp_blocked():
    assert _blocked(_attack("write_outside_tmp.py"))


@pytest.mark.sandbox
def test_tmp_is_noexec():
    assert _blocked(_attack("tmp_exec.py"))


@pytest.mark.sandbox
def test_runs_unprivileged():
    assert _blocked(_attack("privilege.py"))


@pytest.mark.sandbox
def test_outlive_timeout_killed():
    result = _attack("outlive_timeout.py", timeout=2)
    assert "timed out" in (result.get("error") or "").lower()
