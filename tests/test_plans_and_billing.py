"""Phase 4: plan limits enforced on the server, the payment link, operator upgrades and lapsing."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import accounts, admin, billing, config, db, retention
from app.main import app
from app.plans import PLANS, plan_for
from tests.accounts_helpers import OWN_GROQ_KEY, SignedIn, new_email

TASK = {"task_description": "Write solve() returning 42"}
OPERATOR = {"X-API-Key": "operator-secret-key"}


@pytest.fixture(autouse=True)
def accounts_only(monkeypatch):
    monkeypatch.setattr(config, "OPEN_DEV_ACCESS", False)


@pytest.fixture
def operator():
    with patch("app.config.API_KEY", "operator-secret-key"):
        yield TestClient(app)


def week_old_user() -> SignedIn:
    user = SignedIn(new_email())
    old = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET created_at = ? WHERE user_id = ?", (old, user.user["user_id"]))
    user.user = accounts.get_user(user.user["user_id"])
    return user


def started_runs(user: SignedIn, n: int, days_ago: int = 0) -> None:
    when = datetime.now() - timedelta(days=days_ago)
    for i in range(n):
        run_id = f"run_{user.user['user_id'][-6:]}_{days_ago}_{i}"
        db.insert_run(run_id, "old task", created_at=when, final_status="success")
        db.update_run(run_id, workspace=user.workspace)


# ── Runs per day ─────────────────────────────────────────────


def test_runs_per_day_are_enforced_on_the_server():
    user = week_old_user()
    limit = PLANS["free"].runs_per_day
    started_runs(user, limit - 1)
    with patch("app.main.submit_run"):
        assert user.post("/runs", headers=OWN_GROQ_KEY, json=TASK).status_code == 202
        refused = user.post("/runs", headers=OWN_GROQ_KEY, json=TASK)
    assert refused.status_code == 429
    assert f"limit of {limit} runs" in refused.json()["detail"]


def test_yesterdays_runs_dont_count_today():
    user = week_old_user()
    started_runs(user, PLANS["free"].runs_per_day, days_ago=1)
    with patch("app.main.submit_run"):
        assert user.post("/runs", headers=OWN_GROQ_KEY, json=TASK).status_code == 202


def test_a_comparison_counts_every_model_it_races():
    user = week_old_user()
    started_runs(user, PLANS["free"].runs_per_day - 1)
    race = {**TASK, "models": ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]}
    with patch("app.main.submit_run") as submit:
        assert user.post("/compare", headers=OWN_GROQ_KEY, json=race).status_code == 429
    submit.assert_not_called()


def test_accounts_younger_than_a_day_have_a_tighter_limit():
    user = SignedIn(new_email())  # created just now
    usage = user.get("/account/usage").json()
    assert usage["new_account"] is True
    assert usage["limits"]["runs_per_day"] < PLANS["free"].runs_per_day
    started_runs(user, usage["limits"]["runs_per_day"])
    with patch("app.main.submit_run"):
        assert user.post("/runs", headers=OWN_GROQ_KEY, json=TASK).status_code == 429


def test_pro_gets_more_runs():
    user = week_old_user()
    billing.grant_plan(user.user["user_id"], "pro", days=30)
    started_runs(user, PLANS["free"].runs_per_day + 5)
    with patch("app.main.submit_run"):
        assert user.post("/runs", json=TASK).status_code == 202


# ── History kept ─────────────────────────────────────────────


def test_runs_past_the_plans_history_are_hidden_at_once():
    user = week_old_user()
    keep = PLANS["free"].history_days
    started_runs(user, 1, days_ago=keep + 2)
    started_runs(user, 1, days_ago=1)
    old_id = f"run_{user.user['user_id'][-6:]}_{keep + 2}_0"
    listed = user.get("/runs", params={"page_size": 100}).json()
    assert listed["total"] == 1 and old_id not in [r["run_id"] for r in listed["items"]]
    assert user.get(f"/runs/{old_id}").status_code == 404
    assert user.get(f"/runs/{old_id}/events").status_code == 404


def test_upgrading_brings_back_history_that_wasnt_purged_yet():
    user = week_old_user()
    started_runs(user, 1, days_ago=PLANS["free"].history_days + 2)
    assert user.get("/runs").json()["total"] == 0
    billing.grant_plan(user.user["user_id"], "pro", days=30)
    assert user.get("/runs").json()["total"] == 1


def test_maintenance_purges_expired_history_and_its_events():
    user = week_old_user()
    keep = PLANS["free"].history_days
    started_runs(user, 2, days_ago=keep + 3)
    started_runs(user, 1, days_ago=2)
    old_id = f"run_{user.user['user_id'][-6:]}_{keep + 3}_0"
    db.add_event(old_id, "run_started", {})
    deleted = retention.purge_expired_history()
    assert deleted >= 2
    assert db.get_run(old_id) is None
    assert db.get_events(old_id) == []
    assert user.get("/runs").json()["total"] == 1


def test_operator_history_is_never_purged():
    db.insert_run("run_operator_ancient", "x", created_at=datetime.now() - timedelta(days=4000), final_status="success")
    retention.purge_expired_history()
    assert db.get_run("run_operator_ancient") is not None


# ── Usage in Settings ────────────────────────────────────────


def test_account_usage_shows_plan_limits_and_todays_usage():
    user = week_old_user()
    started_runs(user, 3)
    db.update_run(f"run_{user.user['user_id'][-6:]}_0_0", key_source="server", prompt_tokens=1234)
    usage = user.get("/account/usage").json()
    assert usage["plan"]["name"] == "free"
    assert usage["limits"] == {
        "runs_per_day": PLANS["free"].runs_per_day,
        "concurrent_runs": PLANS["free"].concurrent_runs,
        "history_days": PLANS["free"].history_days,
        "server_token_budget": PLANS["free"].server_token_budget,
    }
    assert usage["usage"]["runs_today"] == 3
    assert usage["usage"]["server_tokens_today"] == 1234
    assert [p["name"] for p in usage["plans"]] == list(PLANS)


def test_plans_are_public_for_the_pricing_page():
    body = TestClient(app).get("/plans").json()
    assert [p["name"] for p in body["items"]] == ["free", "pro"]


# ── Payment link ─────────────────────────────────────────────


def test_upgrade_link_carries_the_account_for_matching(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_URL", "https://pay.example/checkout?ref={user_id}&email={email}")
    user = week_old_user()
    url = user.get("/account/usage").json()["upgrade_url"]
    assert url.startswith("https://pay.example/checkout?ref=" + user.user["user_id"])
    assert "%40example.com" in url  # the email is URL-encoded
    assert TestClient(app).get("/health").json()["payments_enabled"] is True


def test_no_upgrade_link_without_a_payment_url(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_URL", "")
    assert week_old_user().get("/account/usage").json()["upgrade_url"] is None


def test_paid_accounts_get_no_upgrade_link(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_URL", "https://pay.example/x")
    user = week_old_user()
    billing.grant_plan(user.user["user_id"], "pro", days=30)
    usage = user.get("/account/usage").json()
    assert usage["upgrade_url"] is None and usage["paid_until"]


# ── Operator upgrades, and dropping back ─────────────────────


def test_operator_can_upgrade_an_account_and_it_takes_effect(operator):
    user = week_old_user()
    resp = operator.post(f"/admin/users/{user.user['user_id']}/plan", headers=OPERATOR, json={"plan": "pro", "days": 31})
    assert resp.status_code == 200 and resp.json()["plan"] == "pro"
    assert user.get("/auth/me").json()["user"]["plan"]["name"] == "pro"
    with patch("app.main.submit_run"):
        assert user.post("/runs", json=TASK).status_code == 202  # may now use the server key


def test_only_the_operator_can_change_plans():
    user = week_old_user()
    other = week_old_user()
    resp = user.post(f"/admin/users/{other.user['user_id']}/plan", json={"plan": "pro", "days": 31})
    assert resp.status_code == 403
    assert user.post(f"/admin/users/{user.user['user_id']}/plan", json={"plan": "pro", "days": 31}).status_code == 403
    assert accounts.get_user(user.user["user_id"])["plan"] == "free"


def test_admin_api_validates_input(operator):
    user = week_old_user()
    uid = user.user["user_id"]
    assert operator.post(f"/admin/users/{uid}/plan", headers=OPERATOR, json={"plan": "platinum", "days": 3}).status_code == 422
    assert operator.post(f"/admin/users/{uid}/plan", headers=OPERATOR, json={"plan": "pro"}).status_code == 422
    assert operator.post("/admin/users/u_nobody/plan", headers=OPERATOR, json={"plan": "pro", "days": 3}).status_code == 404
    found = operator.get("/admin/users/lookup", headers=OPERATOR, params={"email": user.email}).json()
    assert found["user_id"] == uid


def test_renewing_early_adds_days_instead_of_losing_them():
    user = week_old_user()
    first = billing.grant_plan(user.user["user_id"], "pro", days=10)
    second = billing.grant_plan(user.user["user_id"], "pro", days=10)
    gap = accounts.parse_time(second["paid_until"]) - accounts.parse_time(first["paid_until"])
    assert timedelta(days=9, hours=23) < gap <= timedelta(days=10, seconds=5)


def test_a_lapsed_plan_drops_back_to_free():
    user = week_old_user()
    billing.grant_plan(user.user["user_id"], "pro", until=datetime.now(timezone.utc) + timedelta(seconds=1))
    later = accounts.now() + timedelta(minutes=1)
    # In force right up to paid_until, free right after, even before maintenance runs
    assert user.get("/auth/me").json()["user"]["plan"]["name"] == "pro"
    assert plan_for(accounts.get_user(user.user["user_id"]), now=later).name == "free"
    # Maintenance then records it
    assert billing.expire_lapsed_plans(now=later) >= 1
    assert accounts.get_user(user.user["user_id"])["plan"] == "free"


def test_maintenance_runs_every_chore_and_survives_a_failing_one():
    calls = []
    retention.add_chore(lambda: calls.append("ok"))
    retention.add_chore(lambda: 1 / 0)
    try:
        result = retention.run_maintenance()
    finally:
        retention._extra_chores.clear()
    assert set(result) == {"plans_expired", "runs_purged"} and calls == ["ok"]


def test_admin_command_line(capsys):
    user = week_old_user()
    admin.main(["set-plan", user.email, "pro", "--days", "31"])
    assert accounts.get_user(user.user["user_id"])["plan"] == "pro"
    admin.main(["show", user.email])
    assert user.email in capsys.readouterr().out
    admin.main(["set-plan", user.email, "free"])
    assert accounts.get_user(user.user["user_id"])["paid_until"] is None
    admin.main(["set-plan", user.email, "pro", "--until", "2099-12-31"])
    assert accounts.get_user(user.user["user_id"])["paid_until"].startswith("2099-12-31")
    with pytest.raises(SystemExit):
        admin.main(["show", "nobody@example.com"])
    admin.main(["expire"])
