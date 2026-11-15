"""User accounts: users, browser sessions, single-use email tokens and API keys.

Everything secret is stored only as a hash: passwords with argon2, session ids, email
tokens and API keys with SHA-256 (they are long random strings, so a fast hash is fine).
Each user owns exactly one workspace, named by their user id, so every existing
workspace filter keeps working unchanged.
"""

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app import config, db

_hasher = PasswordHasher()
# Verified against when an email doesn't exist, so a login takes as long either way
_DUMMY_HASH = _hasher.hash("not-a-real-password")

API_KEY_PREFIX = "sia_"
PASSWORD_MIN = 10
PASSWORD_MAX = 256


class AccountError(ValueError):
    """A user-facing problem with the request (weak password, bad token...)."""


# ── Helpers ─────────────────────────────────────────────────


def now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def valid_email(email: str) -> bool:
    local, at, domain = email.partition("@")
    return bool(at and local and "." in domain and len(email) <= 254 and " " not in email)


def check_password_strength(password: str) -> None:
    if len(password or "") < PASSWORD_MIN:
        raise AccountError(f"Use at least {PASSWORD_MIN} characters for your password.")
    if len(password) > PASSWORD_MAX:
        raise AccountError(f"Passwords can be at most {PASSWORD_MAX} characters.")


def workspace_for(user_id: str) -> str:
    return user_id


# ── Schema ──────────────────────────────────────────────────


def init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        email_verified_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL,
        active BOOLEAN NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS sessions (
        session_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        csrf_token TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        expires_at TIMESTAMP NOT NULL
    );

    CREATE TABLE IF NOT EXISTS auth_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        purpose TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        used_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS api_keys (
        key_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        key_hash TEXT NOT NULL UNIQUE,
        prefix TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        last_used_at TIMESTAMP,
        revoked_at TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
    CREATE INDEX IF NOT EXISTS idx_tokens_user ON auth_tokens(user_id, purpose);
    CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
    """)
    db._add_missing_columns(conn, "users", USER_COLUMNS)


# Added by later phases; old databases converge on the same shape
USER_COLUMNS: dict[str, str] = {}


# ── Users ───────────────────────────────────────────────────


def _user(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    user = dict(row)
    user.pop("password_hash", None)
    user["workspace"] = workspace_for(user["user_id"])
    return user


def get_user(user_id: str) -> dict[str, Any] | None:
    with db.get_connection() as conn:
        return _user(conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone())


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalize_email(email),)).fetchone()
        return _user(row)


def create_user(email: str, password: str) -> dict[str, Any] | None:
    """Create an unverified user. Returns None when the email is already taken."""
    email = normalize_email(email)
    if not valid_email(email):
        raise AccountError("Enter a valid email address.")
    check_password_strength(password)
    user_id = "u_" + secrets.token_hex(6)
    try:
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO users (user_id, email, password_hash, created_at, active) VALUES (?, ?, ?, ?, 1)",
                (user_id, email, _hasher.hash(password), _iso(now())),
            )
    except sqlite3.IntegrityError:
        return None
    return get_user(user_id)


def waste_a_hash(password: str) -> None:
    """Spend the same time as hashing a new password, so responses don't reveal accounts."""
    _hasher.hash(password or "x")


def authenticate(email: str, password: str) -> dict[str, Any] | None:
    """The user for these credentials, or None. Same work whether or not the email exists."""
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalize_email(email),)).fetchone()
    stored = row["password_hash"] if row else _DUMMY_HASH
    try:
        _hasher.verify(stored, password or "")
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return None
    if row is None:
        return None
    if _hasher.check_needs_rehash(stored):
        set_password(row["user_id"], password)
    return _user(row)


def set_password(user_id: str, password: str) -> None:
    check_password_strength(password)
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (_hasher.hash(password), user_id))


def mark_verified(user_id: str) -> None:
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE users SET email_verified_at = COALESCE(email_verified_at, ?) WHERE user_id = ?",
            (_iso(now()), user_id),
        )


def set_active(user_id: str, active: bool) -> None:
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET active = ? WHERE user_id = ?", (1 if active else 0, user_id))
        if not active:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


# ── Sessions ────────────────────────────────────────────────


def create_session(user_id: str) -> tuple[str, str]:
    """A new browser session. Returns (session id for the cookie, CSRF token)."""
    session_id = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    created = now()
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (session_hash, user_id, csrf_token, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (sha256(session_id), user_id, csrf, _iso(created),
             _iso(created + timedelta(days=config.SESSION_TTL_DAYS))),
        )
    return session_id, csrf


def session_user(session_id: str | None) -> tuple[dict[str, Any], str] | None:
    """(user, csrf token) for a live session on an active account, or None."""
    if not session_id or len(session_id) > 200:
        return None
    with db.get_connection() as conn:
        row = conn.execute(
            """SELECT s.csrf_token, s.expires_at, u.* FROM sessions s
               JOIN users u ON u.user_id = s.user_id WHERE s.session_hash = ?""",
            (sha256(session_id),),
        ).fetchone()
    if row is None or not row["active"] or parse_time(row["expires_at"]) <= now():
        return None
    data = dict(row)
    csrf = data.pop("csrf_token")
    data.pop("expires_at")
    return _user(data), csrf


def end_session(session_id: str | None) -> None:
    if session_id:
        with db.get_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE session_hash = ?", (sha256(session_id),))


def end_all_sessions(user_id: str) -> None:
    with db.get_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


# ── Single-use email tokens ─────────────────────────────────

TOKEN_TTL = {"verify": timedelta(hours=48), "reset": timedelta(hours=1)}


def issue_token(user_id: str, purpose: str) -> str:
    """A new single-use token. Older unused tokens for the same purpose stop working."""
    token = secrets.token_urlsafe(32)
    created = now()
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE auth_tokens SET used_at = ? WHERE user_id = ? AND purpose = ? AND used_at IS NULL",
            (_iso(created), user_id, purpose),
        )
        conn.execute(
            "INSERT INTO auth_tokens (token_hash, user_id, purpose, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (sha256(token), user_id, purpose, _iso(created), _iso(created + TOKEN_TTL[purpose])),
        )
    return token


def consume_token(token: str, purpose: str) -> str | None:
    """The user id for a valid, unused, unexpired token, marking it used. Otherwise None."""
    if not token or len(token) > 200:
        return None
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM auth_tokens WHERE token_hash = ? AND purpose = ?", (sha256(token), purpose)
        ).fetchone()
        if row is None or row["used_at"] or parse_time(row["expires_at"]) <= now():
            return None
        # Conditional update: two requests racing with the same token can't both win
        claimed = conn.execute(
            "UPDATE auth_tokens SET used_at = ? WHERE token_hash = ? AND used_at IS NULL",
            (_iso(now()), row["token_hash"]),
        ).rowcount
    return row["user_id"] if claimed else None


# ── API keys ────────────────────────────────────────────────


def create_api_key(user_id: str, name: str) -> tuple[dict[str, Any], str]:
    """Returns (key record, the key itself). The key is shown once and never stored."""
    name = (name or "").strip()[:60] or "unnamed key"
    secret = API_KEY_PREFIX + secrets.token_urlsafe(30)
    record = {
        "key_id": "key_" + secrets.token_hex(6),
        "user_id": user_id,
        "name": name,
        "prefix": secret[:10],
        "created_at": _iso(now()),
        "last_used_at": None,
        "revoked_at": None,
    }
    with db.get_connection() as conn:
        conn.execute(
            """INSERT INTO api_keys (key_id, user_id, name, key_hash, prefix, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (record["key_id"], user_id, name, sha256(secret), record["prefix"], record["created_at"]),
        )
    return record, secret


def list_api_keys(user_id: str) -> list[dict[str, Any]]:
    with db.get_connection() as conn:
        rows = conn.execute(
            """SELECT key_id, name, prefix, created_at, last_used_at, revoked_at FROM api_keys
               WHERE user_id = ? ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def revoke_api_key(user_id: str, key_id: str) -> bool:
    with db.get_connection() as conn:
        return conn.execute(
            "UPDATE api_keys SET revoked_at = ? WHERE key_id = ? AND user_id = ? AND revoked_at IS NULL",
            (_iso(now()), key_id, user_id),
        ).rowcount > 0


def user_for_api_key(secret: str) -> dict[str, Any] | None:
    """The active user owning this (unrevoked) key, recording when it was last used."""
    if not secret.startswith(API_KEY_PREFIX) or len(secret) > 200:
        return None
    digest = sha256(secret)
    with db.get_connection() as conn:
        row = conn.execute(
            """SELECT k.key_id, u.* FROM api_keys k JOIN users u ON u.user_id = k.user_id
               WHERE k.key_hash = ? AND k.revoked_at IS NULL""",
            (digest,),
        ).fetchone()
        if row is None or not row["active"]:
            return None
        conn.execute("UPDATE api_keys SET last_used_at = ? WHERE key_id = ?", (_iso(now()), row["key_id"]))
    data = dict(row)
    data.pop("key_id")
    return _user(data)
