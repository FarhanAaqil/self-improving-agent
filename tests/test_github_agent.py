"""Unit tests for GitHub PR automation agent.

Asserts no-op when GITHUB_TOKEN is unset and verifies correct branch, file,
and PR creation with a mocked GitHub HTTP client.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.github_agent import IS_GITHUB_CONFIGURED, open_pull_request_for_run
from app.main import app

client = TestClient(app)


def test_github_agent_inert_when_unconfigured():
    """Assert github_agent is completely no-op when token is missing/placeholder."""
    if not IS_GITHUB_CONFIGURED:
        result = open_pull_request_for_run("run_mock_123")
        assert result["status"] == "skipped"
        assert "not configured" in result["reason"]
        assert result["pr_url"] is None


def test_github_agent_creates_pr_with_mocked_github():
    """Verify branch creation, file commit, and PR generation with mocked HTTP responses."""
    mock_client = MagicMock()

    # 1. GET base ref
    ref_resp = MagicMock()
    ref_resp.status_code = 200
    ref_resp.json.return_value = {"object": {"sha": "abc123456"}}

    # 2. POST create branch
    branch_resp = MagicMock()
    branch_resp.status_code = 201

    # 3. PUT create file
    file_resp = MagicMock()
    file_resp.status_code = 201

    # 4. POST open PR
    pr_resp = MagicMock()
    pr_resp.status_code = 201
    pr_resp.json.return_value = {
        "html_url": "https://github.com/FarhanAaqil/self-improving-agent/pull/42",
        "number": 42,
    }

    mock_client.get.return_value = ref_resp
    mock_client.post.side_effect = [branch_resp, pr_resp]
    mock_client.put.return_value = file_resp

    mock_run_data = {
        "run_id": "run_test42",
        "task_description": "Write Fibonacci function",
        "final_status": "success",
        "total_attempts": 1,
        "attempts": [
            {
                "attempt_number": 1,
                "generated_code": "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)",
                "success": True,
                "quality_overall_score": 0.95,
            }
        ],
    }

    with patch("app.github_agent.IS_GITHUB_CONFIGURED", True), \
         patch("app.github_agent.GITHUB_TOKEN", "mock_valid_token"), \
         patch("app.github_agent.get_run_with_attempts", return_value=mock_run_data):

        result = open_pull_request_for_run("run_test42", repo="FarhanAaqil/self-improving-agent", client=mock_client)

        assert result["status"] == "success"
        assert result["pr_url"] == "https://github.com/FarhanAaqil/self-improving-agent/pull/42"
        assert result["pr_number"] == 42
        assert result["branch"] == "agent/solution-run_test42"

        # Verify calls occurred
        mock_client.get.assert_called_once()
        assert mock_client.post.call_count == 2
        mock_client.put.assert_called_once()


def test_endpoint_post_run_pr():
    """Verify POST /runs/{run_id}/pr endpoint routing."""
    with patch("app.github_agent.IS_GITHUB_CONFIGURED", False):
        resp = client.post("/runs/run_dummy_123/pr")
        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped"
