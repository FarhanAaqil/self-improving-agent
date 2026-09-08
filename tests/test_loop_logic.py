from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_repair_loop_retry_to_success():
    """Test that a failed first attempt triggers critique and retries to success."""
    attempt_codes = [
        "def solve(): return 1 / 0",  # Fails attempt 1
        "def solve(): return 42\nprint(solve())",  # Passes attempt 2
    ]
    gen_mock = MagicMock(side_effect=attempt_codes)

    # Sandbox responses for each attempt
    exec_responses = [
        {"success": False, "error": "ZeroDivisionError: division by zero", "output": "", "exit_code": 1, "latency_ms": 15},
        {"success": True, "error": None, "output": "42\n", "exit_code": 0, "latency_ms": 12},
    ]
    run_mock = MagicMock(side_effect=exec_responses)

    # Critique mock returning confidence >= 0.3 for the retry
    critique_mock = MagicMock(
        return_value={
            "verdict": "REWRITE",
            "confidence": 0.8,
            "reasoning": "Zero division error, needs fallback logic",
            "issues": ["Division by zero"],
            "instructions": "Avoid dividing by zero",
            "raw": "VERDICT: REWRITE\nCONFIDENCE: 0.8",
        }
    )

    with patch("app.main.generate_code", gen_mock), \
         patch("app.main.run_code", run_mock), \
         patch("app.main.critique_code", critique_mock):

        resp = client.post(
            "/generate-and-repair",
            json={
                "task_description": "Write a function returning 42",
                "max_attempts": 3,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["final_status"] == "success"
        assert data["total_attempts"] == 2
        assert len(data["attempts"]) == 2
        assert data["attempts"][0]["success"] is False
        assert data["attempts"][0]["critique_confidence"] == 0.8
        assert data["attempts"][0]["critique_reasoning"] == "Zero division error, needs fallback logic"
        assert data["attempts"][1]["success"] is True


def test_repair_loop_early_stop_on_low_confidence():
    """Test that critique confidence < 0.3 aborts the repair loop immediately."""
    gen_mock = MagicMock(return_value="def solve(): raise RuntimeError('Impossible')")
    run_mock = MagicMock(
        return_value={
            "success": False,
            "error": "RuntimeError: Impossible specification",
            "output": "",
            "exit_code": 1,
            "latency_ms": 20,
        }
    )

    # Critique reports low confidence (< 0.3) indicating intractable problem
    critique_mock = MagicMock(
        return_value={
            "verdict": "REWRITE",
            "confidence": 0.15,
            "reasoning": "Impossible specification, fundamental contradiction",
            "issues": ["Contradictory requirements"],
            "instructions": "Cannot be solved as specified",
            "raw": "VERDICT: REWRITE\nCONFIDENCE: 0.15",
        }
    )

    with patch("app.main.generate_code", gen_mock), \
         patch("app.main.run_code", run_mock), \
         patch("app.main.critique_code", critique_mock):

        resp = client.post(
            "/generate-and-repair",
            json={
                "task_description": "Solve halting problem",
                "max_attempts": 4,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["final_status"] == "early_stopped"
        assert data["total_attempts"] == 1
        assert len(data["attempts"]) == 1
        assert data["attempts"][0]["critique_confidence"] == 0.15
        assert "Impossible specification" in data["attempts"][0]["critique_reasoning"]
        # Ensure it stopped early and did not generate 4 attempts
        assert gen_mock.call_count == 1


def test_repair_loop_max_retries_exceeded():
    """Test that failures with normal confidence run up to max_attempts."""
    gen_mock = MagicMock(return_value="def solve(): pass")
    run_mock = MagicMock(
        return_value={
            "success": False,
            "error": "AssertionError",
            "output": "",
            "exit_code": 1,
            "latency_ms": 10,
        }
    )
    critique_mock = MagicMock(
        return_value={
            "verdict": "REWRITE",
            "confidence": 0.6,
            "reasoning": "Logic can be fixed",
            "issues": ["Incomplete logic"],
            "instructions": "Fill out logic",
            "raw": "VERDICT: REWRITE\nCONFIDENCE: 0.6",
        }
    )

    with patch("app.main.generate_code", gen_mock), \
         patch("app.main.run_code", run_mock), \
         patch("app.main.critique_code", critique_mock):

        resp = client.post(
            "/generate-and-repair",
            json={
                "task_description": "Write complex parser",
                "max_attempts": 3,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["final_status"] == "max_retries_exceeded"
        assert data["total_attempts"] == 3
        assert len(data["attempts"]) == 3
        assert gen_mock.call_count == 3
