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


def _reply(content, finish_reason="stop"):
    from types import SimpleNamespace

    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)], usage=None
    )


def _client(replies, seen):
    from types import SimpleNamespace

    def create(**kwargs):
        seen.append(kwargs["max_tokens"])
        return replies.pop(0)

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_empty_or_cut_off_answers_are_retried_with_more_room():
    from app import llm

    seen = []
    client = _client([_reply("", "length"), _reply("def f(): pa", "length"), _reply("def f(): pass")], seen)
    assert llm.chat([{"role": "user", "content": "x"}], max_tokens=500, client=client) == "def f(): pass"
    assert seen == [500, 1000, 2000]


def test_a_model_that_never_answers_raises_instead_of_returning_nothing():
    import pytest

    from app import llm

    seen = []
    client = _client([_reply("<think>hmm</think>", "length")] * 10, seen)
    with pytest.raises(llm.EmptyCompletion):
        llm.chat([{"role": "user", "content": "x"}], max_tokens=4096, client=client)
    assert seen[-1] == llm.LLM_MAX_OUTPUT_TOKENS


def test_spec_tests_must_parse_and_can_be_pruned_by_name():
    from app.test_agent import drop_tests, usable_tests

    good = "import math\n\ndef test_a():\n    assert 1\n\ndef test_b():\n    assert math.pi > 3\n"
    assert usable_tests(good)
    assert not usable_tests("def test_a(:\n    pass")       # cut off mid-line
    assert not usable_tests("x = 1")                         # no tests at all
    assert not usable_tests(None)
    pruned = drop_tests(good, ["test_a"])
    assert "test_a" not in pruned and "test_b" in pruned and "import math" in pruned


def test_no_code_never_passes_verification():
    from app.harness import verify

    result = verify("   \n", "def test_x():\n    assert True\n")
    assert result.success is False and "No code" in result.feedback()


def test_diagnosis_lists_the_tests_it_blames():
    blamed = _parse_diagnosis('{"blame": "tests", "wrong_tests": ["test_a", 7, "test_b"], "retry_confidence": 0.8}')
    assert blamed["wrong_tests"] == ["test_a", "test_b"]
    assert _parse_diagnosis('{"blame": "code"}')["wrong_tests"] == []
