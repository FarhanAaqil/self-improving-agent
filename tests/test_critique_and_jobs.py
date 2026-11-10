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


def test_llm_calls_wait_out_rate_limits_instead_of_failing(monkeypatch):
    from types import SimpleNamespace

    from app import llm

    class RateLimitError(Exception):
        response = SimpleNamespace(headers={"retry-after": "7"})

    calls, sleeps = [], []
    reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="done"))], usage=None)

    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) < 3:
            raise RateLimitError("slow down")
        return reply

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    assert llm.chat([{"role": "user", "content": "hi"}], client=client) == "done"
    assert len(calls) == 3
    assert all(7 <= s <= 8 for s in sleeps)  # the server's retry-after, plus a little jitter


def test_llm_errors_that_are_not_transient_fail_immediately(monkeypatch):
    from types import SimpleNamespace

    import pytest

    from app import llm

    class AuthenticationError(Exception):
        pass

    def create(**kwargs):
        raise AuthenticationError("bad key")

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm.time, "sleep", lambda s: pytest.fail("must not sleep"))
    with pytest.raises(AuthenticationError):
        llm.chat([{"role": "user", "content": "hi"}], client=client)


def test_a_second_process_on_the_same_data_refuses_to_start(tmp_path):
    import pytest

    from app.single_instance import AlreadyRunning, InstanceLock

    path = str(tmp_path / "agent.db.lock")
    first, second = InstanceLock(path), InstanceLock(path)
    first.acquire()
    with pytest.raises(AlreadyRunning, match="single worker"):
        second.acquire()
    first.release()
    second.acquire()   # free again once the first process lets go
    second.release()


def test_app_startup_takes_and_releases_the_instance_lock():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.single_instance import InstanceLock

    with TestClient(app) as running:
        assert running.get("/health").status_code == 200
        import pytest

        from app.single_instance import AlreadyRunning

        with pytest.raises(AlreadyRunning):
            InstanceLock().acquire()
    probe = InstanceLock()
    probe.acquire()
    probe.release()
