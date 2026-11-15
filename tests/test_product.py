"""Phase 5: the public live demo, exporting your data and deleting your account."""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import accounts, config, db, llm, memory, retention
from app.main import app
from app.security import RateLimiter
from tests.accounts_helpers import SignedIn, new_email
from tests.test_isolation import owned_run, vector_memory  # noqa: F401 - fixture


@pytest.fixture(autouse=True)
def accounts_only(monkeypatch):
    monkeypatch.setattr(config, "OPEN_DEV_ACCESS", False)


@pytest.fixture
def memory_on(vector_memory, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "MEMORY_ENABLED", True)
    return vector_memory


@pytest.fixture
def docker_up(monkeypatch):
    monkeypatch.setattr("app.main._is_docker_available", lambda: True)


# ── Live demo ────────────────────────────────────────────────


def test_anyone_can_start_a_demo_and_it_never_uses_a_real_model(docker_up):
    visitor = TestClient(app)  # no account, no key
    with patch("app.main.submit_run") as submit:
        resp = visitor.post("/demo/run")
    assert resp.status_code == 202
    spec = submit.call_args.args[1]
    assert spec.fake_llm is True
    assert spec.allow_server_key is False and spec.groq_key is None
    assert spec.workspace == "demo" and spec.use_memory is False
    run = db.get_run(resp.json()["run_id"])
    assert run["workspace"] == "demo" and run["key_source"] == "demo"
    # The result can be opened afterwards through its public share link
    assert visitor.get(resp.json()["share_url"]).status_code == 200


def test_the_scripted_model_can_be_forced_for_one_block(monkeypatch):
    monkeypatch.setattr(llm, "FAKE_LLM", False)
    built = MagicMock()
    monkeypatch.setattr(llm, "Groq", built)
    with llm.fake_mode():
        reply = llm.chat([{"role": "system", "content": "write code"}, {"role": "user", "content": "Write add(a, b)"}])
    assert reply
    built.assert_not_called()


def test_demo_events_are_public_but_only_for_demo_runs(docker_up):
    visitor = TestClient(app)
    with patch("app.main.submit_run"):
        run_id = visitor.post("/demo/run").json()["run_id"]
    db.add_event(run_id, "run_finished", {"status": "success"})
    with visitor.stream("GET", f"/demo/runs/{run_id}/events") as resp:
        assert resp.status_code == 200
        assert "run_finished" in "".join(resp.iter_text())
    assert visitor.get(f"/runs/{run_id}").status_code == 401  # not a back door to the run API

    user = SignedIn(new_email())
    private = owned_run(user, "run_private_not_demo")
    assert visitor.get(f"/demo/runs/{private}/events").status_code == 404


def test_demo_is_rate_limited_per_visitor(docker_up, monkeypatch):
    monkeypatch.setattr("app.main._demo_limiter", RateLimiter(2, 600))
    visitor = TestClient(app)
    with patch("app.main.submit_run"):
        codes = [visitor.post("/demo/run").status_code for _ in range(3)]
    assert codes == [202, 202, 429]


def test_demo_needs_the_sandbox_and_can_be_switched_off(monkeypatch):
    monkeypatch.setattr("app.main._is_docker_available", lambda: False)
    assert TestClient(app).post("/demo/run").status_code == 503
    monkeypatch.setattr(config, "DEMO_ENABLED", False)
    assert TestClient(app).post("/demo/run").status_code == 404


def test_old_demo_runs_are_cleaned_up():
    db.insert_run("run_demo_old", "x", created_at=datetime.now() - timedelta(days=2), final_status="success")
    db.update_run("run_demo_old", workspace="demo")
    db.insert_run("run_demo_new", "x", final_status="success")
    db.update_run("run_demo_new", workspace="demo")
    assert retention.purge_demo_runs() >= 1
    assert db.get_run("run_demo_old") is None and db.get_run("run_demo_new") is not None


# ── Export ───────────────────────────────────────────────────


def test_export_has_everything_of_yours_and_no_secrets(memory_on):
    user = SignedIn(new_email())
    other = SignedIn(new_email())
    owned_run(user, "run_export_mine")
    owned_run(other, "run_export_theirs")
    user.post("/runs/run_export_mine/share")
    user.post("/account/keys", json={"name": "export-key"})
    memory.store_failure("reverse a linked list", "code", "AttributeError: next", workspace=user.workspace)

    resp = user.get("/account/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.json()
    assert body["account"]["email"] == user.email
    assert [r["run_id"] for r in body["runs"]] == ["run_export_mine"]
    assert body["runs"][0]["attempts"] and body["runs"][0]["events"]
    assert body["memories"][0]["task"] == "reverse a linked list"
    assert body["api_keys"][0]["name"] == "export-key"
    text = json.dumps(body)
    assert "run_export_theirs" not in text
    assert "password_hash" not in text and "key_hash" not in text and "share_token" not in text
    assert "$argon2" not in text


# ── Delete my account ────────────────────────────────────────


def test_deleting_an_account_removes_everything_it_owned(memory_on):
    user = SignedIn(new_email())
    bystander = SignedIn(new_email())
    owned_run(user, "run_del_mine")
    owned_run(bystander, "run_del_bystander")
    key = user.post("/account/keys", json={"name": "doomed"}).json()["key"]
    memory.store_failure("parse roman numerals", "code", "KeyError: Z", workspace=user.workspace)
    memory.store_failure("parse roman numerals", "code", "KeyError: Z", workspace=bystander.workspace)
    uid = user.user["user_id"]

    assert user.client.request("DELETE", "/account", headers={"X-CSRF-Token": user.csrf},
                               json={"password": "wrong password!!"}).status_code == 403
    resp = user.client.request("DELETE", "/account", headers={"X-CSRF-Token": user.csrf}, json={"password": user.password})
    assert resp.status_code == 200 and resp.json()["runs"] == 1 and resp.json()["memories"] == 1

    assert accounts.get_user(uid) is None
    assert db.get_run("run_del_mine") is None and db.get_events("run_del_mine") == []
    with db.get_connection() as conn:
        for table in ("sessions", "auth_tokens", "api_keys"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (uid,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM attempts WHERE run_id = 'run_del_mine'").fetchone()[0] == 0
    assert memory.list_memories(workspace=uid)["total"] == 0
    assert TestClient(app).get("/runs", headers={"X-API-Key": key}).status_code == 401
    assert user.get("/runs").status_code == 401
    assert TestClient(app).post("/auth/login", json={"email": user.email, "password": user.password}).status_code == 401

    # Nobody else lost anything
    assert db.get_run("run_del_bystander") is not None
    assert memory.list_memories(workspace=bystander.workspace)["total"] == 1


def test_an_api_key_cannot_delete_the_account():
    user = SignedIn(new_email())
    key = user.post("/account/keys", json={"name": "script"}).json()["key"]
    resp = TestClient(app).request("DELETE", "/account", headers={"X-API-Key": key}, json={"password": user.password})
    assert resp.status_code == 403
    assert accounts.get_user(user.user["user_id"]) is not None


def test_memory_wipe_refuses_an_empty_workspace():
    with pytest.raises(ValueError):
        memory.delete_workspace("")
