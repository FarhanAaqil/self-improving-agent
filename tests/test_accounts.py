"""Accounts: sign-up, email verification, sessions with CSRF, password reset and API keys."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import accounts, config, db
from app.main import app
from app.security import RateLimiter
from tests.accounts_helpers import SignedIn, install_outbox, new_email

PASSWORD = "correct horse battery"


@pytest.fixture
def outbox(monkeypatch):
    return install_outbox(monkeypatch)


@pytest.fixture
def accounts_mode(monkeypatch):
    """Local development, but with anonymous access switched off (like production)."""
    monkeypatch.setattr(config, "OPEN_DEV_ACCESS", False)


def test_signup_verify_and_reach_a_private_route(outbox, accounts_mode):
    browser = TestClient(app)
    email = new_email()
    resp = browser.post("/auth/signup", json={"email": email.upper(), "password": PASSWORD})
    assert resp.status_code == 202

    user = accounts.get_user_by_email(email)
    assert user["email"] == email  # stored lower-case
    assert user["email_verified_at"] is None
    assert browser.get("/runs").status_code == 401

    token = outbox.last_link(email, "/verify")
    resp = browser.post("/auth/verify", json={"token": token})
    assert resp.status_code == 200
    assert resp.json()["user"]["email_verified"] is True
    me = browser.get("/auth/me").json()
    assert me["user"]["email"] == email and me["csrf_token"]

    # The new workspace is named after the user and starts empty
    assert browser.get("/runs").json()["total"] == 0
    assert accounts.workspace_for(user["user_id"]) == user["user_id"]


def test_verification_links_work_once(outbox):
    email = new_email()
    TestClient(app).post("/auth/signup", json={"email": email, "password": PASSWORD})
    token = outbox.last_link(email, "/verify")
    assert TestClient(app).post("/auth/verify", json={"token": token}).status_code == 200
    assert TestClient(app).post("/auth/verify", json={"token": token}).status_code == 400


def test_expired_tokens_are_refused():
    user = accounts.create_user(new_email(), PASSWORD)
    token = accounts.issue_token(user["user_id"], "verify")
    later = accounts.now() + timedelta(days=3)
    with patch("app.accounts.now", return_value=later):
        assert accounts.consume_token(token, "verify") is None


def test_signup_answer_is_identical_for_new_and_existing_emails(outbox):
    email = new_email()
    first = TestClient(app).post("/auth/signup", json={"email": email, "password": PASSWORD})
    second = TestClient(app).post("/auth/signup", json={"email": email, "password": "another long password"})
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()


def test_forgot_password_answer_never_reveals_accounts(outbox):
    real = SignedIn(new_email())
    known = TestClient(app).post("/auth/forgot", json={"email": real.email})
    unknown = TestClient(app).post("/auth/forgot", json={"email": new_email()})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len([m for m in outbox.messages if "Reset" in m["subject"]]) == 1


def test_weak_passwords_and_bad_emails_are_refused(outbox):
    assert TestClient(app).post("/auth/signup", json={"email": new_email(), "password": "short"}).status_code == 422
    assert TestClient(app).post("/auth/signup", json={"email": "not-an-email", "password": PASSWORD}).status_code == 422


def test_login_requires_a_verified_email(outbox):
    email = new_email()
    accounts.create_user(email, PASSWORD)
    resp = TestClient(app).post("/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 403
    assert outbox.last_link(email, "/verify")  # a fresh link was sent


def test_wrong_password_and_unknown_email_look_the_same():
    user = SignedIn(new_email())
    wrong = TestClient(app).post("/auth/login", json={"email": user.email, "password": "wrong password!!"})
    missing = TestClient(app).post("/auth/login", json={"email": new_email(), "password": PASSWORD})
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()


def test_passwords_are_argon2_hashed():
    email = new_email()
    accounts.create_user(email, PASSWORD)
    with db.get_connection() as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()[0]
    assert stored.startswith("$argon2") and PASSWORD not in stored


def test_session_cookie_is_httponly_and_strict():
    browser = TestClient(app)
    email = new_email()
    accounts.mark_verified(accounts.create_user(email, PASSWORD)["user_id"])
    resp = browser.post("/auth/login", json={"email": email, "password": PASSWORD})
    cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    with db.get_connection() as conn:
        stored = [r[0] for r in conn.execute("SELECT session_hash FROM sessions").fetchall()]
    assert browser.cookies.get(config.SESSION_COOKIE) not in stored  # only the hash is kept


def test_writes_need_the_csrf_token(accounts_mode):
    user = SignedIn(new_email())
    with patch("app.main.submit_run"):
        no_token = user.client.post("/runs", json={"task_description": "Write solve() returning 42"})
        assert no_token.status_code == 403
        ok = user.post("/runs", json={"task_description": "Write solve() returning 42"})
    assert ok.status_code == 202
    assert db.run_workspace(ok.json()["run_id"]) == user.workspace
    assert user.client.get("/runs").status_code == 200  # reads don't need it


def test_logout_ends_the_session(accounts_mode):
    user = SignedIn(new_email())
    assert user.post("/auth/logout").status_code == 200
    assert user.get("/runs").status_code == 401
    assert user.get("/auth/me").json()["user"] is None


def test_password_reset_signs_out_everywhere(outbox, accounts_mode):
    user = SignedIn(new_email())
    TestClient(app).post("/auth/forgot", json={"email": user.email})
    token = outbox.last_link(user.email, "/reset")
    resp = TestClient(app).post("/auth/reset", json={"token": token, "password": "a brand new password"})
    assert resp.status_code == 200
    assert user.get("/runs").status_code == 401  # old session gone
    assert TestClient(app).post("/auth/reset", json={"token": token, "password": "yet another one!!"}).status_code == 400
    assert accounts.authenticate(user.email, "a brand new password")


def test_change_password_keeps_this_browser_signed_in(accounts_mode):
    user = SignedIn(new_email())
    other = TestClient(app)
    other.post("/auth/login", json={"email": user.email, "password": user.password})
    resp = user.post("/account/password", json={"current_password": user.password, "new_password": "fresh password here"})
    assert resp.status_code == 200
    user.csrf = resp.json()["csrf_token"]
    assert user.get("/runs").status_code == 200
    assert other.get("/runs").status_code == 401


def test_api_keys_are_shown_once_stored_hashed_and_revocable(accounts_mode):
    user = SignedIn(new_email())
    resp = user.post("/account/keys", json={"name": "laptop script"})
    assert resp.status_code == 201
    secret, record = resp.json()["key"], resp.json()["record"]
    assert secret.startswith("sia_")

    listed = user.get("/account/keys").json()["items"]
    assert listed[0]["name"] == "laptop script" and "key" not in listed[0] and "key_hash" not in listed[0]
    with db.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM api_keys WHERE key_hash = ?", (secret,)).fetchone()[0] == 0

    script = TestClient(app)
    assert script.get("/runs", headers={"X-API-Key": secret}).status_code == 200
    assert script.get("/runs", headers={"Authorization": f"Bearer {secret}"}).status_code == 200
    # A key works without CSRF (it isn't a browser cookie) and lands in the owner's workspace
    with patch("app.main.submit_run"):
        run = script.post("/runs", headers={"X-API-Key": secret}, json={"task_description": "Write solve() returning 42"})
    assert db.run_workspace(run.json()["run_id"]) == user.workspace

    assert user.delete(f"/account/keys/{record['key_id']}").status_code == 200
    assert script.get("/runs", headers={"X-API-Key": secret}).status_code == 401


def test_keys_cannot_mint_more_keys():
    user = SignedIn(new_email())
    secret = user.post("/account/keys", json={"name": "ci"}).json()["key"]
    resp = TestClient(app).post("/account/keys", headers={"X-API-Key": secret}, json={"name": "sneaky"})
    assert resp.status_code == 403


def test_env_keys_still_work_as_an_admin_fallback(accounts_mode):
    with patch("app.config.API_KEY", "operator-secret-key"):
        assert TestClient(app).get("/runs", headers={"X-API-Key": "operator-secret-key"}).status_code == 200
        assert TestClient(app).get("/runs", headers={"X-API-Key": "sia_not_a_real_key"}).status_code == 401


def test_disabled_accounts_lose_access(accounts_mode):
    user = SignedIn(new_email())
    accounts.set_active(user.user["user_id"], False)
    assert user.get("/runs").status_code == 401
    assert TestClient(app).post("/auth/login", json={"email": user.email, "password": user.password}).status_code == 403


def test_account_endpoints_are_rate_limited(monkeypatch, outbox):
    monkeypatch.setattr("app.auth_routes.auth_limiter", RateLimiter(3))
    browser = TestClient(app)
    codes = [browser.post("/auth/forgot", json={"email": new_email()}).status_code for _ in range(5)]
    assert codes[:3] == [202, 202, 202] and codes[-1] == 429


def test_same_email_is_limited_across_addresses(monkeypatch, outbox):
    monkeypatch.setattr("app.auth_routes.email_limiter", RateLimiter(2, 900))
    email = new_email()
    codes = [TestClient(app).post("/auth/forgot", json={"email": email}).status_code for _ in range(3)]
    assert codes == [202, 202, 429]


def test_open_development_mode_still_works_without_an_account():
    assert config.OPEN_DEV_ACCESS
    assert TestClient(app).get("/runs").status_code == 200
    assert TestClient(app).get("/health").json()["auth"] == "open"
