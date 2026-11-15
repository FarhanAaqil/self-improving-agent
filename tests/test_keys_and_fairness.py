"""Phase 3: who pays for a run, per-user limits, a fair queue and per-user sandbox slots."""

import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import accounts, config, db, llm
from app.jobs import FairScheduler
from app.main import app
from app.pipeline import RunSpec
from app.plans import PLANS, effective_plan_name, plan_for, runs_per_day
from app.security import RateLimiter
from tests.accounts_helpers import OWN_GROQ_KEY, SignedIn, new_email

TASK = {"task_description": "Write solve() returning 42"}


@pytest.fixture(autouse=True)
def accounts_only(monkeypatch):
    monkeypatch.setattr(config, "OPEN_DEV_ACCESS", False)


def make_pro(user: SignedIn, days: int = 30) -> None:
    until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET plan = 'pro', paid_until = ? WHERE user_id = ?", (until, user.user["user_id"]))


# ── Free accounts bring their own key ────────────────────────


def test_free_runs_without_a_key_are_refused_with_a_clear_message():
    user = SignedIn(new_email())
    with patch("app.main.submit_run") as submit:
        resp = user.post("/runs", json=TASK)
    assert resp.status_code == 403
    assert "own Groq key" in resp.json()["detail"] and "Settings" in resp.json()["detail"]
    submit.assert_not_called()
    assert user.get("/runs").json()["total"] == 0  # nothing was even recorded


@pytest.mark.parametrize("path,body", [
    ("/generate", TASK),
    ("/compare", {**TASK, "models": ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]}),
    ("/generate-and-repair", TASK),
])
def test_every_way_to_spend_tokens_needs_a_free_users_own_key(path, body):
    user = SignedIn(new_email())
    with patch("app.main.submit_run"), patch("app.main.execute_run"), patch("app.main.generate_code") as gen:
        assert user.post(path, json=body).status_code == 403
    gen.assert_not_called()


def test_free_runs_with_their_own_key_use_only_that_key():
    user = SignedIn(new_email())
    with patch("app.main.submit_run") as submit:
        resp = user.post("/runs", headers=OWN_GROQ_KEY, json=TASK)
    assert resp.status_code == 202
    spec = submit.call_args.args[1]
    assert spec.groq_key == OWN_GROQ_KEY["X-Groq-Key"]
    assert spec.allow_server_key is False  # never a silent fallback to our key
    assert spec.concurrency_limit == PLANS["free"].concurrent_runs
    assert db.get_run(resp.json()["run_id"])["key_source"] == "own"


def test_the_llm_layer_refuses_the_server_key_when_it_is_not_allowed(monkeypatch):
    monkeypatch.setattr(llm, "GROQ_API_KEY", "gsk_the_operators_key")
    built = MagicMock()
    monkeypatch.setattr(llm, "Groq", built)
    llm._clients.clear()
    with llm.groq_key(None, allow_server_key=False):
        with pytest.raises(llm.ServerKeyNotAllowed):
            llm.get_client()
        with pytest.raises(llm.ServerKeyNotAllowed):
            llm.chat([{"role": "user", "content": "hi"}])
    built.assert_not_called()
    with llm.groq_key("gsk_users_key", allow_server_key=False):
        llm.get_client()
    assert built.call_args.kwargs["api_key"] == "gsk_users_key"


def test_a_free_run_that_somehow_lacks_a_key_fails_without_spending_ours(monkeypatch):
    from app.pipeline import execute_run

    monkeypatch.setattr(llm, "FAKE_LLM", False)
    monkeypatch.setattr(llm, "GROQ_API_KEY", "gsk_the_operators_key")
    built = MagicMock()
    monkeypatch.setattr(llm, "Groq", built)
    llm._clients.clear()
    db.insert_run("run_no_key", "Write solve() returning 42", final_status="queued")
    status = execute_run("run_no_key", RunSpec(task="Write solve() returning 42", allow_server_key=False, groq_key=None))
    assert status == "failed"
    built.assert_not_called()


# ── Paid accounts may use the server key, within a budget ────


def test_pro_runs_may_use_the_server_key_within_the_daily_budget():
    user = SignedIn(new_email())
    make_pro(user)
    with patch("app.main.submit_run") as submit:
        resp = user.post("/runs", json=TASK)
    assert resp.status_code == 202
    spec = submit.call_args.args[1]
    assert spec.groq_key is None and spec.allow_server_key is True
    assert spec.concurrency_limit == PLANS["pro"].concurrent_runs
    assert db.get_run(resp.json()["run_id"])["key_source"] == "server"


def test_pro_budget_counts_only_server_key_tokens():
    user = SignedIn(new_email())
    make_pro(user)
    budget = PLANS["pro"].server_token_budget
    db.insert_run("run_own_spend", "x", final_status="success")
    db.update_run("run_own_spend", workspace=user.workspace, key_source="own", prompt_tokens=budget * 2)
    with patch("app.main.submit_run"):
        assert user.post("/runs", json=TASK).status_code == 202  # own-key tokens don't count

    db.insert_run("run_server_spend", "x", final_status="success")
    db.update_run("run_server_spend", workspace=user.workspace, key_source="server", prompt_tokens=budget)
    with patch("app.main.submit_run"):
        refused = user.post("/runs", json=TASK)
        assert refused.status_code == 429 and "own Groq key" in refused.json()["detail"]
        assert user.post("/runs", headers=OWN_GROQ_KEY, json=TASK).status_code == 202


def test_a_lapsed_pro_account_is_free_again():
    user = SignedIn(new_email())
    make_pro(user, days=-1)
    with patch("app.main.submit_run"):
        assert user.post("/runs", json=TASK).status_code == 403
    assert user.get("/auth/me").json()["user"]["plan"]["name"] == "free"


def test_the_operator_still_uses_the_server_key():
    with patch("app.config.API_KEY", "operator-secret-key"), patch("app.main.submit_run") as submit:
        resp = TestClient(app).post("/runs", headers={"X-API-Key": "operator-secret-key"}, json=TASK)
    assert resp.status_code == 202
    assert submit.call_args.args[1].allow_server_key is True
    assert submit.call_args.args[1].concurrency_limit == 0


def test_me_tells_the_browser_about_the_plan_and_key_rule():
    user = SignedIn(new_email())
    me = user.get("/auth/me").json()["user"]
    assert me["plan"]["name"] == "free" and me["needs_own_groq_key"] is True
    make_pro(user)
    me = user.get("/auth/me").json()["user"]
    assert me["plan"]["name"] == "pro" and me["needs_own_groq_key"] is False and me["paid_until"]


def test_plan_rules():
    now = datetime.now(timezone.utc)
    assert effective_plan_name(None) == "free"
    assert effective_plan_name({"plan": "pro", "paid_until": None}) == "free"
    assert effective_plan_name({"plan": "pro", "paid_until": (now + timedelta(days=1)).isoformat()}) == "pro"
    assert effective_plan_name({"plan": "pro", "paid_until": (now - timedelta(seconds=1)).isoformat()}) == "free"
    assert effective_plan_name({"plan": "made-up", "paid_until": (now + timedelta(days=1)).isoformat()}) == "free"
    assert plan_for(None).server_key is False


def test_brand_new_accounts_get_fewer_runs_on_day_one():
    now = datetime.now(timezone.utc)
    fresh = {"plan": "free", "created_at": now.isoformat()}
    week_old = {"plan": "free", "created_at": (now - timedelta(days=7)).isoformat()}
    assert runs_per_day(fresh) < runs_per_day(week_old) == PLANS["free"].runs_per_day


# ── Fair queue ───────────────────────────────────────────────


def _recording_scheduler(workers: int):
    started: list[str] = []
    release = threading.Event()
    lock = threading.Lock()

    def execute(run_id, spec):
        with lock:
            started.append(run_id)
        release.wait(5)
        return "success"

    return FairScheduler(workers, execute=execute), started, release


def _wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_one_users_burst_does_not_make_others_wait_behind_it():
    sched, started, release = _recording_scheduler(workers=1)
    gate = threading.Event()
    sched.execute = lambda run_id, spec: (started.append(run_id), gate.wait(5))[-1] and "ok"
    first = sched.submit("a0", RunSpec(task="t", workspace="alice"))  # occupies the only worker
    assert _wait_for(lambda: started == ["a0"])
    for i in range(1, 5):
        sched.submit(f"a{i}", RunSpec(task="t", workspace="alice"))
    sched.submit("b1", RunSpec(task="t", workspace="bob"))
    gate.set()
    first.result(5)
    assert _wait_for(lambda: len(started) == 6)
    # Bob's single run goes right after Alice's first, not after all five of hers
    assert started.index("b1") <= 2
    release.set()


def test_a_users_own_cap_holds_back_only_their_runs():
    sched, started, release = _recording_scheduler(workers=3)
    for i in range(3):
        sched.submit(f"a{i}", RunSpec(task="t", workspace="alice"), limit=1)
    sched.submit("b0", RunSpec(task="t", workspace="bob"), limit=1)
    assert _wait_for(lambda: set(started) == {"a0", "b0"})
    time.sleep(0.1)
    assert sorted(started) == ["a0", "b0"]  # alice's other two wait for her own slot
    assert sched.running("alice") == 1 and sched.queued("alice") == 2
    release.set()
    assert _wait_for(lambda: len(started) == 4)


def test_the_global_worker_cap_is_never_exceeded():
    active = 0
    peak = 0
    lock = threading.Lock()

    def execute(run_id, spec):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return "ok"

    sched = FairScheduler(2, execute=execute)
    futures = [sched.submit(f"r{i}", RunSpec(task="t", workspace=f"user{i % 4}")) for i in range(10)]
    for f in futures:
        f.result(5)
    assert peak == 2


def test_a_crashing_run_does_not_stop_the_queue():
    def execute(run_id, spec):
        if run_id == "boom":
            raise RuntimeError("kaboom")
        return "ok"

    sched = FairScheduler(1, execute=execute)
    bad = sched.submit("boom", RunSpec(task="t", workspace="a"))
    good = sched.submit("fine", RunSpec(task="t", workspace="a"))
    assert good.result(5) == "ok"
    assert isinstance(bad.exception(5), RuntimeError)
    assert sched.running("a") == 0


# ── Per-user sandbox slots ───────────────────────────────────


def test_one_user_cannot_fill_every_sandbox_slot(monkeypatch):
    from app import sandbox

    active: dict[str, int] = {}
    peak: dict[str, int] = {}
    lock = threading.Lock()

    def fake_docker(code, timeout):
        owner = code
        with lock:
            active[owner] = active.get(owner, 0) + 1
            peak[owner] = max(peak.get(owner, 0), active[owner])
        time.sleep(0.05)
        with lock:
            active[owner] -= 1
        return {"success": True, "output": "", "error": None, "exit_code": 0, "latency_ms": 1, "sandboxed": True}

    monkeypatch.setattr(sandbox, "_is_docker_available", lambda: True)
    monkeypatch.setattr(sandbox, "_run_docker", fake_docker)

    def run_as(owner, limit):
        with sandbox.sandbox_owner(owner, limit):
            sandbox.run_code(owner)

    threads = [threading.Thread(target=run_as, args=("alice", 1)) for _ in range(4)]
    threads += [threading.Thread(target=run_as, args=("bob", 2)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert peak["alice"] == 1
    assert peak["bob"] <= 2


# ── Per-user rate limits ─────────────────────────────────────


def test_rate_limits_are_per_user_not_per_address(monkeypatch):
    monkeypatch.setattr("app.security.limiter", RateLimiter(2))
    alice, bob = SignedIn(new_email()), SignedIn(new_email())  # same test client address
    with patch("app.main.submit_run"):
        codes_a = [alice.post("/runs", headers=OWN_GROQ_KEY, json=TASK).status_code for _ in range(3)]
        code_b = bob.post("/runs", headers=OWN_GROQ_KEY, json=TASK).status_code
    assert codes_a == [202, 202, 429]
    assert code_b == 202


# ── GitHub pull requests are the operator's ──────────────────


def test_accounts_cannot_open_pull_requests_with_the_operators_token():
    user = SignedIn(new_email())
    db.insert_run("run_pr_user", "x", final_status="success")
    db.update_run("run_pr_user", workspace=user.workspace)
    with patch("app.github_agent.open_pull_request_for_run") as open_pr, \
            patch("app.github_agent.IS_GITHUB_CONFIGURED", True), patch("app.github_agent.GITHUB_TOKEN", "ghp_x"):
        resp = user.post("/runs/run_pr_user/pr")
    assert resp.status_code == 403
    open_pr.assert_not_called()
    assert user.get("/auth/me").json()["can_open_prs"] is False


def test_accounts_keep_their_workspace_after_key_changes():
    user = SignedIn(new_email())
    assert accounts.workspace_for(user.user["user_id"]) == user.workspace
