"""Two real users, every route that touches user data: B never sees or changes A's things.

Each test signs in two accounts (session cookie + CSRF token, exactly like browsers) with
anonymous access switched off, gives user A some data, and checks user B from every angle.
"""

import hashlib
import json
from unittest.mock import patch

import chromadb
import numpy as np
import pytest
from chromadb.api.types import EmbeddingFunction
from fastapi.testclient import TestClient

from app import config, db, memory
from app.main import app
from tests.accounts_helpers import OWN_GROQ_KEY, SignedIn, new_email

TASK = "Write add(a, b) returning the sum"


class WordHash(EmbeddingFunction):
    """An offline stand-in for the ONNX embedder: same words, similar vectors."""

    def __init__(self):
        pass

    def __call__(self, input):
        out = []
        for text in input:
            vec = np.zeros(64, dtype=np.float32)
            for word in text.lower().split():
                vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % 64] += 1
            out.append(vec / (np.linalg.norm(vec) or 1))
        return out

    @staticmethod
    def name():
        return "word-hash-test"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return WordHash()


@pytest.fixture(autouse=True)
def accounts_only(monkeypatch):
    monkeypatch.setattr(config, "OPEN_DEV_ACCESS", False)


@pytest.fixture
def alice():
    return SignedIn(new_email())


@pytest.fixture
def bob():
    return SignedIn(new_email())


@pytest.fixture
def vector_memory(monkeypatch):
    name = "iso-" + hashlib.md5(new_email().encode()).hexdigest()[:10]
    coll = chromadb.EphemeralClient().get_or_create_collection(
        name, embedding_function=WordHash(), metadata={"hnsw:space": "cosine"}
    )
    monkeypatch.setattr(memory, "_collection", coll)
    monkeypatch.setattr("app.main.MEMORY_ENABLED", True)
    return coll


def owned_run(user: SignedIn, run_id: str, *, verified=True, group_id=None, tokens=0, recalled=None) -> str:
    db.insert_run(run_id, TASK, final_status="success" if verified else "failed", total_attempts=1)
    db.update_run(
        run_id, workspace=user.workspace, model_name="qwen/qwen3.8-27b", group_id=group_id,
        spec_tests="def test_add():\n    assert add(1, 2) == 3\n", final_code="def add(a, b):\n    return a + b\n",
        prompt_tokens=tokens, completion_tokens=0, memories_json=json.dumps(recalled or []),
    )
    db.insert_attempt(
        run_id=run_id, attempt_number=1, generated_code="def add(a, b):\n    return a + b\n",
        success=verified, tests_passed=1 if verified else 0, tests_total=1, coverage=1.0, sandboxed=True,
        stderr=None if verified else "Traceback: secret detail from alice's failure",
    )
    db.add_event(run_id, "run_started", {"task": TASK})
    db.add_event(run_id, "run_finished", {"status": "success" if verified else "failed"})
    return run_id


# ── Runs ─────────────────────────────────────────────────────


def test_run_list_and_search_only_show_your_own(alice, bob):
    owned_run(alice, "run_iso_a1")
    mine = alice.get("/runs", params={"page_size": 100}).json()
    theirs = bob.get("/runs", params={"page_size": 100, "q": "add"}).json()
    assert [r["run_id"] for r in mine["items"]] == ["run_iso_a1"]
    assert theirs["items"] == [] and theirs["total"] == 0
    assert sum(theirs["status_counts"].values()) == 0  # not even counts leak
    assert bob.get("/runs", params={"q": "run_iso_a1"}).json()["total"] == 0


@pytest.mark.parametrize("path", ["/runs/{id}", "/runs/{id}/events", "/runs/{id}/certificate"])
def test_reading_someone_elses_run_looks_like_it_doesnt_exist(alice, bob, path):
    run_id = owned_run(alice, "run_iso_read_" + path.count("/").__str__() + path[-3:].replace("/", ""))
    assert alice.get(path.format(id=run_id)).status_code == 200
    resp = bob.get(path.format(id=run_id))
    assert resp.status_code == 404
    assert "secret" not in resp.text and TASK not in resp.text


def test_events_stream_of_another_user_is_refused(alice, bob):
    run_id = owned_run(alice, "run_iso_sse")
    with alice.client.stream("GET", f"/runs/{run_id}/events") as resp:
        body = "".join(resp.iter_text())
    assert "run_finished" in body
    assert bob.get(f"/runs/{run_id}/events").status_code == 404


def test_cannot_share_or_unshare_someone_elses_run(alice, bob):
    run_id = owned_run(alice, "run_iso_share")
    assert bob.post(f"/runs/{run_id}/share").status_code == 404
    assert db.get_run(run_id)["share_token"] is None
    token = alice.post(f"/runs/{run_id}/share").json()["token"]
    assert bob.delete(f"/runs/{run_id}/share").status_code == 404
    assert db.get_run(run_id)["share_token"] == token


def test_cannot_execute_someone_elses_run(alice, bob):
    run_id = owned_run(alice, "run_iso_exec")
    before = len(db.get_run_with_attempts(run_id)["attempts"])
    with patch("app.main.run_code") as run_code:
        assert bob.post(f"/execute/{run_id}").status_code == 404
    run_code.assert_not_called()
    assert len(db.get_run_with_attempts(run_id)["attempts"]) == before


def test_cannot_open_a_pull_request_from_someone_elses_run(alice, bob):
    run_id = owned_run(alice, "run_iso_pr")
    with patch("app.github_agent.open_pull_request_for_run") as open_pr:
        assert bob.post(f"/runs/{run_id}/pr").status_code == 404
    open_pr.assert_not_called()


def test_new_runs_land_in_the_callers_workspace(alice, bob):
    with patch("app.main.submit_run"):
        run_id = bob.post("/runs", headers=OWN_GROQ_KEY, json={"task_description": TASK}).json()["run_id"]
    assert db.run_workspace(run_id) == bob.workspace
    assert alice.get(f"/runs/{run_id}").status_code == 404


def test_comparisons_are_private(alice, bob):
    owned_run(alice, "run_iso_cmp1", group_id="cmp_iso_1")
    owned_run(alice, "run_iso_cmp2", group_id="cmp_iso_1")
    assert len(alice.get("/compare/cmp_iso_1").json()["runs"]) == 2
    assert bob.get("/compare/cmp_iso_1").status_code == 404


def test_a_user_cannot_join_someone_elses_comparison_group(alice, bob):
    owned_run(alice, "run_iso_grp", group_id="cmp_iso_2")
    with patch("app.main.submit_run"):
        resp = bob.post(
            "/compare", headers=OWN_GROQ_KEY,
            json={"task_description": TASK, "models": ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]},
        )
    assert resp.json()["group_id"] != "cmp_iso_2"
    assert len(alice.get("/compare/cmp_iso_2").json()["runs"]) == 1


# ── Memory ───────────────────────────────────────────────────


def test_memory_list_stats_and_search_are_private(alice, bob, vector_memory):
    memory.store_failure("reverse a linked list in place", "code", "AttributeError: next", workspace=alice.workspace)
    memory.store_lesson("parse roman numerals", "KeyError: Z", "validate characters first", workspace=alice.workspace)

    assert alice.get("/memory").json()["total"] == 2
    assert bob.get("/memory").json() == {"total": 0, "items": []}
    assert bob.get("/memory/stats").json()["total"] == 0
    assert alice.get("/memory/search", params={"q": "reverse a linked list"}).json()["items"]
    assert bob.get("/memory/search", params={"q": "reverse a linked list", "threshold": 0}).json()["items"] == []


def test_memory_cannot_be_deleted_or_pinned_by_someone_else(alice, bob, vector_memory):
    memory_id = memory.store_failure("sort a list of tuples", "code", "TypeError: x", workspace=alice.workspace)
    assert bob.delete(f"/memory/{memory_id}").status_code == 404
    assert bob.post(f"/memory/{memory_id}/pin").status_code == 404
    item = alice.get("/memory").json()["items"][0]
    assert item["id"] == memory_id and item["pinned"] is False
    assert alice.post(f"/memory/{memory_id}/pin").status_code == 200
    assert alice.delete(f"/memory/{memory_id}").status_code == 200


def test_runs_only_recall_their_own_workspaces_memories(alice, bob, vector_memory):
    memory.store_failure("write add returning the sum", "return a - b", "AssertionError", workspace=alice.workspace)
    found_for_bob = memory.retrieve_similar_failures(TASK, workspace=bob.workspace, similarity_threshold=0.0)
    found_for_alice = memory.retrieve_similar_failures(TASK, workspace=alice.workspace, similarity_threshold=0.0)
    assert found_for_bob == [] and found_for_alice


# ── Usage, stats, eval, metrics ──────────────────────────────


def test_usage_and_improvement_stats_count_only_your_runs(alice, bob):
    owned_run(alice, "run_iso_tokens", tokens=5000)
    assert alice.get("/usage").json()["tokens_today"] == 5000
    assert bob.get("/usage").json()["tokens_today"] == 0
    assert bob.get("/usage").json()["workspace"] == bob.workspace
    alice_days = alice.get("/stats/improvement").json()["daily"]
    bob_days = bob.get("/stats/improvement").json()["daily"]
    assert sum(d["runs"] for d in alice_days) >= 1
    assert sum(d["runs"] for d in bob_days) == 0


def test_only_the_operator_can_start_benchmarks_or_read_metrics(alice):
    assert alice.post("/eval/run", json={"benchmark": "humaneval", "subset_size": 5}).status_code == 403
    assert alice.get("/metrics").status_code == 403
    with patch("app.config.API_KEY", "operator-secret-key"):
        operator = TestClient(app)
        assert operator.get("/metrics", headers={"X-API-Key": "operator-secret-key"}).status_code == 200


def test_published_benchmark_results_stay_public():
    assert TestClient(app).get("/eval/latest").status_code == 200
    assert TestClient(app).get("/eval/agent").status_code == 200


# ── Account data ─────────────────────────────────────────────


def test_api_keys_are_private(alice, bob):
    key_id = alice.post("/account/keys", json={"name": "alice-ci"}).json()["record"]["key_id"]
    assert bob.get("/account/keys").json()["items"] == []
    assert bob.delete(f"/account/keys/{key_id}").status_code == 404
    assert alice.get("/account/keys").json()["items"][0]["revoked_at"] is None


def test_an_api_key_only_reaches_its_owners_workspace(alice, bob):
    owned_run(alice, "run_iso_key")
    bob_key = bob.post("/account/keys", json={"name": "bob-ci"}).json()["key"]
    script = TestClient(app)
    assert script.get("/runs/run_iso_key", headers={"X-API-Key": bob_key}).status_code == 404
    assert script.get("/runs", headers={"X-API-Key": bob_key}).json()["total"] == 0


def test_a_session_cookie_cannot_be_combined_with_someone_elses_csrf_token(alice, bob):
    with patch("app.main.submit_run"):
        resp = bob.client.post("/runs", headers={"X-CSRF-Token": alice.csrf}, json={"task_description": TASK})
    assert resp.status_code == 403


# ── Public share links ───────────────────────────────────────


def test_share_link_shows_only_that_run_and_no_recalled_memories(alice):
    recalled = [{"id": "m1", "task": "alice's private earlier task", "similarity": 0.9}]
    run_id = owned_run(alice, "run_iso_public", recalled=recalled, tokens=777)
    owned_run(alice, "run_iso_other_private")
    token = alice.post(f"/runs/{run_id}/share").json()["token"]

    stranger = TestClient(app)
    shared = stranger.get(f"/shared/{token}")
    assert shared.status_code == 200
    body = shared.json()
    assert body["run_id"] == run_id
    assert body["memories"] == []
    assert body["prompt_tokens"] is None and body["group_id"] is None
    assert len(body["attempts"]) == 1 and body["attempts"][0]["success"]
    text = shared.text
    assert "alice's private earlier task" not in text
    assert "run_iso_other_private" not in text
    assert alice.workspace not in text and alice.email not in text
    assert stranger.get(f"/shared/{token}/badge.svg").status_code == 200


def test_share_links_only_work_by_their_token(alice):
    run_id = owned_run(alice, "run_iso_token")
    token = alice.post(f"/runs/{run_id}/share").json()["token"]
    stranger = TestClient(app)
    assert stranger.get(f"/shared/{run_id}").status_code == 404
    assert stranger.get(f"/shared/{token[:-1]}").status_code == 404
    assert stranger.get(f"/runs/{run_id}").status_code == 401
    alice.delete(f"/runs/{run_id}/share")
    assert stranger.get(f"/shared/{token}").status_code == 404
    assert "unverified" in stranger.get(f"/shared/{token}/badge.svg").text
