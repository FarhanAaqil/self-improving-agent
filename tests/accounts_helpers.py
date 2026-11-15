"""Shared helpers for tests that need real signed-in users."""

import re
import secrets

from fastapi.testclient import TestClient

from app import accounts, mailer
from app.main import app


class Outbox:
    """Captures emails instead of sending them."""

    def __init__(self):
        self.messages: list[dict] = []

    def send(self, to, subject, body, background=True):
        self.messages.append({"to": to, "subject": subject, "body": body})

    def last_link(self, to: str, path: str) -> str:
        for msg in reversed(self.messages):
            if msg["to"] == to:
                match = re.search(re.escape(path) + r"\?token=([\w-]+)", msg["body"])
                if match:
                    return match.group(1)
        raise AssertionError(f"no {path} link was mailed to {to}")


def install_outbox(monkeypatch) -> Outbox:
    box = Outbox()
    monkeypatch.setattr(mailer, "send", box.send)
    return box


def new_email() -> str:
    return f"user-{secrets.token_hex(4)}@example.com"


OWN_GROQ_KEY = {"X-Groq-Key": "gsk_test_users_own_key"}


class SignedIn:
    """A TestClient holding one user's session cookie and CSRF token."""

    def __init__(self, email: str, password: str = "correct horse battery"):
        user = accounts.create_user(email, password)
        accounts.mark_verified(user["user_id"])
        self.user = accounts.get_user(user["user_id"])
        self.email = email
        self.password = password
        self.client = TestClient(app)
        resp = self.client.post("/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, resp.text
        self.csrf = resp.json()["csrf_token"]

    @property
    def workspace(self) -> str:
        return self.user["workspace"]

    def _h(self, headers=None):
        return {"X-CSRF-Token": self.csrf, **(headers or {})}

    def get(self, url, **kw):
        return self.client.get(url, **kw)

    def post(self, url, **kw):
        return self.client.post(url, headers=self._h(kw.pop("headers", None)), **kw)

    def delete(self, url, **kw):
        return self.client.delete(url, headers=self._h(kw.pop("headers", None)), **kw)
