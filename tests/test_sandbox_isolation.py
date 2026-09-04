import os
import pytest
from app.sandbox import run_code

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "adversarial")


def _read_fixture(filename: str) -> str:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.mark.sandbox
def test_outbound_network_blocked():
    code = _read_fixture("outbound_network.py")
    result = run_code(code, timeout=4)
    assert not result["success"], "Outbound network should be blocked"
    assert "VULNERABILITY" not in (result.get("output") or "")


@pytest.mark.sandbox
def test_read_host_files_blocked():
    code = _read_fixture("read_host_file.py")
    result = run_code(code, timeout=4)
    assert not result["success"], "Reading sensitive system files should be blocked"
    assert "VULNERABILITY" not in (result.get("output") or "")


@pytest.mark.sandbox
def test_fork_bomb_bounded():
    code = _read_fixture("fork_bomb.py")
    result = run_code(code, timeout=4)
    assert not result["success"], "Memory exhaustion should be blocked or killed"


@pytest.mark.sandbox
def test_write_outside_tmp_blocked():
    code = _read_fixture("write_outside_tmp.py")
    result = run_code(code, timeout=4)
    assert not result["success"], "Writes outside /tmp must fail"
    assert "VULNERABILITY" not in (result.get("output") or "")


@pytest.mark.sandbox
def test_outlive_timeout_killed():
    code = _read_fixture("outlive_timeout.py")
    # Small 1-second timeout to assert host kill
    result = run_code(code, timeout=1)
    assert not result["success"], "Long-running process should be terminated"
    assert "timed out" in (result.get("error") or "").lower()
