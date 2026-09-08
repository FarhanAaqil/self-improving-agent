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


def test_skip_all_post_success_agents():
    """Verify skip_agents=['test', 'performance', 'security_audit', 'docs'] produces identical behavior to pre-agent runs."""
    original_code = "def solve(): return 42\nprint(solve())"
    gen_mock = MagicMock(return_value=original_code)
    run_mock = MagicMock(
        return_value={
            "success": True,
            "error": None,
            "output": "42\n",
            "exit_code": 0,
            "latency_ms": 8,
        }
    )

    test_agent_mock = MagicMock()
    perf_agent_mock = MagicMock()
    sec_agent_mock = MagicMock()
    docs_agent_mock = MagicMock()
    critique_mock = MagicMock()

    with patch("app.main.generate_code", gen_mock), \
         patch("app.main.run_code", run_mock), \
         patch("app.main.generate_unit_tests", test_agent_mock), \
         patch("app.main.analyze_performance", perf_agent_mock), \
         patch("app.main.CodeSecurityAudit.audit", sec_agent_mock), \
         patch("app.main.document_code", docs_agent_mock), \
         patch("app.main.critique_code", critique_mock):

        resp = client.post(
            "/generate-and-repair",
            json={
                "task_description": "Return 42",
                "max_attempts": 2,
                "skip_agents": ["test", "performance", "security_audit", "docs", "critique"],
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["final_status"] == "success"
        assert data["total_attempts"] == 1
        attempt = data["attempts"][0]
        # Verify review agents were skipped
        assert attempt["generated_tests"] is None
        assert attempt["performance_notes"] is None
        assert attempt["security_audit"] is None
        assert attempt["critique_confidence"] is None
        assert attempt["critique_reasoning"] is None
        # Code untouched by documentation agent
        assert attempt["generated_code"] == original_code

        # None of the review agent mocks were called
        test_agent_mock.assert_not_called()
        perf_agent_mock.assert_not_called()
        sec_agent_mock.assert_not_called()
        docs_agent_mock.assert_not_called()
        critique_mock.assert_not_called()


def test_post_success_pipeline_populates_review_and_metrics():
    """Verify that all review agents and metrics populate the passing attempt."""
    raw_code = "def add(a, b): return a + b"
    doc_code = "def add(a: int, b: int) -> int:\n    '''Return sum of a and b.'''\n    return a + b"

    gen_mock = MagicMock(return_value=raw_code)
    run_mock = MagicMock(
        return_value={
            "success": True,
            "error": None,
            "output": "",
            "exit_code": 0,
            "latency_ms": 12,
        }
    )

    with patch("app.main.generate_code", gen_mock), \
         patch("app.main.run_code", run_mock), \
         patch("app.main.generate_unit_tests", return_value="def test_add(): assert add(1, 2) == 3"), \
         patch("app.main.analyze_performance", return_value="OPTIMIZED"), \
         patch("app.main.CodeSecurityAudit.audit", return_value="SECURE"), \
         patch("app.main.document_code", return_value=doc_code), \
         patch("app.main.critique_code", return_value={"confidence": 0.95, "reasoning": "Clean logic"}):

        resp = client.post(
            "/generate-and-repair",
            json={
                "task_description": "Write add function",
                "max_attempts": 2,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["final_status"] == "success"
        attempt = data["attempts"][0]
        assert attempt["generated_code"] == doc_code
        assert "test_add" in attempt["generated_tests"]
        assert attempt["performance_notes"] == "OPTIMIZED"
        assert attempt["security_audit"] == "SECURE"
        assert attempt["critique_confidence"] == 0.95
        assert attempt["critique_reasoning"] == "Clean logic"
        assert attempt["quality_overall_score"] is not None
        assert attempt["quality_overall_score"] > 0.8
        assert "cyclomatic_complexity" in attempt["quality_report_json"]

