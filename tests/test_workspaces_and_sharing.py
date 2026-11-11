"""Workspaces, budgets, model comparison, certificates, share links, insight and metrics."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)

KEYS = "alice:key-alice-123,bob:key-bob-456"
ALICE = {"X-API-Key": "key-alice-123"}
BOB = {"X-API-Key": "key-bob-456"}


def make_verified_run(run_id: str, workspace: str = "default", share_token: str | None = None) -> None:
    db.insert_run(run_id, "Write add(a, b)", final_status="success", total_attempts=2)
    db.update_run(
        run_id, workspace=workspace, model_name="qwen/qwen3.8-27b", spec_tests="def test_x(): pass",
        final_code="def add(a, b):\n    return a + b\n", docs_applied=True, share_token=share_token,
        memories_json="[]",
    )
    db.insert_attempt(run_id=run_id, attempt_number=1, generated_code="def add(a, b): return a - b", success=False)
    db.insert_attempt(
        run_id=run_id, attempt_number=2, generated_code="def add(a, b): return a + b", success=True,
        tests_passed=4, tests_total=4, coverage=1.0, sandboxed=True, quality_overall_score=0.93,
        quality_report_json=json.dumps({"bandit_issues": []}),
    )


@pytest.fixture
def workspaces():
    with patch("app.config.API_KEYS", KEYS), patch("app.config.API_KEY", None):
        yield


def test_each_key_only_sees_its_own_workspace(workspaces):
    make_verified_run("run_alice1", workspace="alice")
    make_verified_run("run_bob1", workspace="bob")

    assert client.get("/runs/run_alice1", headers=ALICE).status_code == 200
    assert client.get("/runs/run_alice1", headers=BOB).status_code == 404
    assert client.get("/runs/run_alice1/events", headers=BOB).status_code == 404
    assert client.get("/runs/run_alice1/certificate", headers=BOB).status_code == 404

    ids = {r["run_id"] for r in client.get("/runs", headers=ALICE, params={"page_size": 100}).json()["items"]}
    assert "run_alice1" in ids and "run_bob1" not in ids
    assert client.get("/runs", headers={"X-API-Key": "nope"}).status_code == 401


def test_new_runs_are_stamped_with_the_callers_workspace(workspaces):
    with patch("app.main.submit_run") as submit:
        resp = client.post("/runs", headers=BOB, json={"task_description": "Write solve() returning 42"})
    run_id = resp.json()["run_id"]
    assert db.run_workspace(run_id) == "bob"
    assert submit.call_args.args[1].workspace == "bob"


def test_byo_groq_key_reaches_the_run_but_is_never_stored(workspaces):
    with patch("app.main.submit_run") as submit:
        resp = client.post(
            "/runs",
            headers={**ALICE, "X-Groq-Key": "gsk_test_secret_value"},
            json={"task_description": "Write solve() returning 42"},
        )
    spec = submit.call_args.args[1]
    assert spec.groq_key == "gsk_test_secret_value"
    assert "gsk_test_secret_value" not in repr(spec)
    stored = db.get_run_with_attempts(resp.json()["run_id"])
    assert "gsk_test_secret_value" not in json.dumps(stored, default=str)


def test_daily_budget_blocks_new_runs_once_spent():
    make_verified_run("run_spender")
    db.update_run("run_spender", prompt_tokens=900, completion_tokens=200)
    with patch("app.main.DAILY_TOKEN_BUDGET", 1000), patch("app.main.submit_run"):
        resp = client.post("/runs", json={"task_description": "Write solve() returning 42"})
        assert resp.status_code == 429
        assert "budget" in resp.json()["detail"].lower()
        usage = client.get("/usage").json()
    assert usage["tokens_today"] >= 1100 and usage["remaining"] == 0


def test_compare_starts_one_run_per_model_in_a_group():
    with patch("app.main.submit_run") as submit, \
         patch("app.schemas.AVAILABLE_MODELS", ["m-a", "m-b", "m-c"]):
        resp = client.post("/compare", json={"task_description": "Write solve() returning 42", "models": ["m-a", "m-b"]})
    assert resp.status_code == 202
    body = resp.json()
    assert submit.call_count == 2
    assert {r["model"] for r in body["runs"]} == {"m-a", "m-b"}

    group = client.get(f"/compare/{body['group_id']}").json()
    assert len(group["runs"]) == 2
    assert client.get("/compare/cmp_missing").status_code == 404
    assert client.post("/compare", json={"task_description": "Write solve() returning 42", "models": ["m-a"]}).status_code == 422


def test_certificate_hashes_the_code_and_signs_when_configured():
    import hashlib

    from app.certificate import verify_signature

    make_verified_run("run_cert")
    with patch("app.certificate.CERT_SIGNING_KEY", "test-signing-key"):
        cert = client.get("/runs/run_cert/certificate").json()
        assert cert["signed"] is True
        assert verify_signature(cert)
        tampered = {**cert, "code_sha256": "0" * 64}
        assert not verify_signature(tampered)
    assert cert["code_sha256"] == hashlib.sha256(b"def add(a, b):\n    return a + b\n").hexdigest()
    assert cert["tests"] == {"passed": 4, "total": 4}
    assert "--network" in cert["sandbox"]["docker_args"]

    db.insert_run("run_unverified", "x", final_status="max_retries_exceeded")
    assert client.get("/runs/run_unverified/certificate").status_code == 409


def test_share_links_are_public_read_only_and_revocable():
    make_verified_run("run_share")
    share = client.post("/runs/run_share/share").json()
    assert client.post("/runs/run_share/share").json()["token"] == share["token"]  # stable

    with patch("app.config.API_KEY", "server-key"):
        # No key needed for a shared link, but private routes still lock
        public = client.get(f"/shared/{share['token']}")
        assert public.status_code == 200
        assert public.json()["certificate"]["verified_on_attempt"] == 2
        assert client.get("/runs/run_share").status_code == 401
        badge = client.get(f"/shared/{share['token']}/badge.svg")
        assert badge.headers["content-type"].startswith("image/svg+xml")
        assert "verified" in badge.text and "4/4 tests" in badge.text

    client.delete("/runs/run_share/share")
    assert client.get(f"/shared/{share['token']}").status_code == 404


def test_improvement_stats_compare_runs_with_and_without_memory():
    make_verified_run("run_mem_yes")
    db.update_run("run_mem_yes", memories_json='[{"id": "m1"}]')
    stats = client.get("/stats/improvement").json()
    assert stats["memory_effect"]["with_memory"]["runs"] >= 1
    assert any(day["runs"] >= 1 for day in stats["daily"])
    assert all(0 <= (d["solve_rate"] or 0) <= 1 for d in stats["daily"])


def test_metrics_and_request_ids():
    from app.observability import metrics

    metrics.reset()
    resp = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert resp.headers["x-request-id"] == "abc123"
    assert len(client.get("/health").headers["x-request-id"]) == 16
    body = client.get("/metrics").text
    assert 'agent_http_requests_total{method="GET",route="/health",status="200"}' in body
    assert "# TYPE agent_http_requests_total counter" in body


def test_json_logs_carry_the_request_id():
    import logging

    from app.observability import JsonFormatter, request_id

    token = request_id.set("req-42")
    try:
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello %s", ("world",), None)
        entry = json.loads(JsonFormatter().format(record))
    finally:
        request_id.reset(token)
    assert entry["msg"] == "hello world" and entry["request_id"] == "req-42"


def test_public_share_shows_the_result_but_not_history_or_memories():
    make_verified_run("run_private_bits")
    db.update_run("run_private_bits", memories_json='[{"id": "m1", "task": "another customer task", "similarity": 0.9}]')
    token = client.post("/runs/run_private_bits/share").json()["token"]

    owner_view = client.get("/runs/run_private_bits").json()
    assert len(owner_view["attempts"]) == 2 and owner_view["memories"]

    public = client.get(f"/shared/{token}").json()
    assert public["memories"] == []
    assert [a["attempt_number"] for a in public["attempts"]] == [2]      # only the passing one
    assert "stderr" not in public["attempts"][0] and "stdout" not in public["attempts"][0]
    assert "another customer task" not in json.dumps(public)
    assert public["final_code"] and public["certificate"]["tests"]["total"] == 4


def test_only_page_routes_get_the_app_shell():
    from app.main import _FRONTEND_DIST

    if not (_FRONTEND_DIST / "index.html").exists():
        pytest.skip("frontend/dist not built")
    html = {"Accept": "text/html"}
    for page in ("/", "/history", "/eval", "/runs/run_abc", "/shared/tok-en_1", "/compare/cmp_1"):
        assert "text/html" in client.get(page, headers=html).headers["content-type"], page
    # API-only paths stay JSON even when a browser asks
    for api in ("/health", "/models", "/sandbox/config", "/eval/latest"):
        assert client.get(api, headers=html).headers["content-type"].startswith("application/json"), api


def test_groq_client_cache_is_bounded():
    from app import llm

    for i in range(llm._MAX_CLIENTS + 10):
        llm.get_client(f"gsk_fake_{i}")
    assert len(llm._clients) <= llm._MAX_CLIENTS
