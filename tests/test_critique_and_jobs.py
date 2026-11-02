"""Diagnosis parsing is defensive against messy model output; restarts never leave zombie runs."""

from app import db
from app.critique import _parse_diagnosis, _parse_verdict
from app.jobs import recover_interrupted_runs


def test_diagnosis_parses_json_wrapped_in_prose():
    raw = 'Sure! Here it is:\n```json\n{"summary": "I forgot empty input.", "root_cause": "IndexError on []", ' \
          '"fix_plan": "Return early for []", "blame": "code", "retry_confidence": 0.7}\n```'
    d = _parse_diagnosis(raw)
    assert d["summary"] == "I forgot empty input."
    assert d["confidence"] == 0.7 and d["blame"] == "code"
    assert "IndexError" in d["reasoning"]


def test_diagnosis_survives_garbage_and_clamps_confidence():
    assert _parse_diagnosis("no json at all")["confidence"] == 0.6
    assert _parse_diagnosis('{"retry_confidence": 7, "blame": "Tests"}')["confidence"] == 1.0
    assert _parse_diagnosis('{"retry_confidence": "high", "blame": "tests"}')["blame"] == "tests"


def test_review_verdict_parsing():
    v = _parse_verdict("VERDICT: REWRITE\nCONFIDENCE: 65%\nREASONING: slow\nISSUES:\n- O(n^2)\nREWRITE_INSTRUCTIONS:\nUse a set")
    assert v["verdict"] == "REWRITE" and v["confidence"] == 0.65
    assert v["issues"] == ["O(n^2)"] and v["instructions"] == "Use a set"


def test_runs_interrupted_by_a_restart_are_marked_failed():
    db.insert_run("run_zombie", "task", final_status="running")
    db.insert_run("run_waiting", "task", final_status="queued")
    assert recover_interrupted_runs() >= 2
    assert db.get_run("run_zombie")["final_status"] == "failed"
    assert db.get_run("run_waiting")["final_status"] == "failed"
