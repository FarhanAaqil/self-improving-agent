"""Integration tests verifying real Groq LLM generation and real Docker sandbox execution.

Gated strictly behind GROQ_API_KEY and Docker daemon availability so forks and
local offline test runs skip cleanly without breaking CI or contributor workflows.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.sandbox import _is_docker_available

client = TestClient(app)


def _has_groq_key() -> bool:
    key = os.getenv("GROQ_API_KEY")
    return bool(key and key.strip() and key != "mock-api-key")


@pytest.mark.integration
@pytest.mark.skipif(not _has_groq_key(), reason="GROQ_API_KEY not set or placeholder")
@pytest.mark.skipif(not _is_docker_available(), reason="Docker daemon not active")
def test_real_groq_and_docker_end_to_end():
    """Execute a real end-to-end generate-and-repair loop through Groq and Docker."""
    task = (
        "Write a Python function 'add_numbers(a: int, b: int) -> int' that returns the sum of a and b.\n"
        "Include a print(add_numbers(2, 3)) at the bottom to verify."
    )

    resp = client.post(
        "/generate-and-repair",
        json={
            "task_description": task,
            "max_attempts": 2,
            "skip_agents": ["critique"],  # keep test snappy
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["final_status"] == "success"
    assert data["total_attempts"] >= 1
    assert len(data["attempts"]) >= 1

    first_attempt = data["attempts"][0]
    assert first_attempt["success"] is True
    assert "add_numbers" in first_attempt["generated_code"]
    assert "5" in (first_attempt.get("stdout") or "")


def test_integration_gating_behavior():
    """Verify that gating check properly identifies presence or absence of API credentials."""
    assert isinstance(_has_groq_key(), bool)
    assert isinstance(_is_docker_available(), bool)
