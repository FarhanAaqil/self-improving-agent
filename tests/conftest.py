"""Shared test fixtures for the self-improving code agent test suite.

Provides isolated SQLite in-memory/temp database setups, mocked LLM clients,
reusable sandbox execution responses, and FastAPI TestClient fixtures.
"""

import os
import tempfile
from typing import Any, Generator
from unittest.mock import MagicMock

# Isolate the whole suite from real state BEFORE any app module reads its config:
# no writes to the developer's agent.db, results/, or ChromaDB, and no surprise auth.
_SANDBOX_DIR = tempfile.mkdtemp(prefix="agent-tests-")
os.environ["APP_ENV"] = "test"
os.environ["DB_PATH"] = os.path.join(_SANDBOX_DIR, "agent.db")
os.environ["RESULTS_DIR"] = os.path.join(_SANDBOX_DIR, "results")
os.environ["MEMORY_DIR"] = os.path.join(_SANDBOX_DIR, "memory_db")
os.environ["MEMORY_ENABLED"] = "false"
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"
os.environ.pop("API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402


def pytest_sessionstart(session):
    """In CI the sandbox tests must run. Fail loudly instead of quietly skipping them."""
    if os.getenv("CI"):
        from app.sandbox import _is_docker_available

        if not _is_docker_available():
            raise pytest.UsageError("CI requires a reachable Docker daemon for the sandbox tests.")


@pytest.fixture(autouse=True)
def _no_real_eval_jobs(monkeypatch):
    """Background eval jobs would call Groq and write result files; never in unit tests."""
    monkeypatch.setattr("app.main._run_eval_job", lambda *args, **kwargs: None)


@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Provide a clean, isolated SQLite database file per test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


@pytest.fixture
def test_client() -> TestClient:
    """Provide a FastAPI TestClient instance."""
    return TestClient(app)


@pytest.fixture
def mock_sandbox_success() -> dict[str, Any]:
    """Standard passing sandbox execution output."""
    return {
        "success": True,
        "output": "42\n",
        "error": None,
        "exit_code": 0,
        "latency_ms": 12,
    }


@pytest.fixture
def mock_sandbox_failure() -> dict[str, Any]:
    """Standard failing sandbox execution output."""
    return {
        "success": False,
        "output": "",
        "error": "AssertionError: expected 42, got 0",
        "exit_code": 1,
        "latency_ms": 15,
    }


@pytest.fixture
def mock_groq_completion() -> MagicMock:
    """Factory helper creating a mock Groq chat completion response."""
    def _create_mock(content: str) -> MagicMock:
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = content
        mock_response.choices = [mock_choice]
        return mock_response
    return _create_mock


@pytest.fixture
def sample_task() -> str:
    """Standard prompt for generator/repair testing."""
    return "Write a function solve() that returns 42"
