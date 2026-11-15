"""Request-level guards: who is calling, CSRF on browser writes, and rate limits.

A caller is identified, in order, by:
  1. an API key header (X-API-Key or Authorization: Bearer): a user's own key from the
     database, or one of the API_KEY / API_KEYS env keys (an admin fallback);
  2. the browser session cookie, which must carry a matching X-CSRF-Token on writes;
  3. nothing at all, which only works in local development with OPEN_DEV_ACCESS.
"""

import re
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app import accounts, config

_PLACEHOLDER_KEYS = {
    "",
    "your-secret-key-here",
    "your-api-key-here",
    "your-secret-api-key-here",
    "placeholder",
    "none",
    "false",
    "changeme",
}

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

DEFAULT_WORKSPACE = "default"
_WORKSPACE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass
class Identity:
    workspace: str
    via: str  # "session", "api_key", "env_key" or "open"
    user: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def is_operator(self) -> bool:
        """The server's operator: an env key, or local development with no keys."""
        return self.via in ("env_key", "open")

    @property
    def user_id(self) -> str | None:
        return self.user["user_id"] if self.user else None


def configured_api_key() -> str | None:
    key = (config.API_KEY or "").strip()
    return None if key.lower() in _PLACEHOLDER_KEYS else key


def workspace_keys() -> dict[str, str]:
    """Map of key -> workspace. API_KEY is the 'default' workspace; API_KEYS adds named ones."""
    keys: dict[str, str] = {}
    if configured_api_key():
        keys[configured_api_key()] = DEFAULT_WORKSPACE
    for entry in (config.API_KEYS or "").split(","):
        name, sep, key = entry.strip().partition(":")
        if sep and key.strip() and _WORKSPACE_NAME.match(name.strip()) and key.strip().lower() not in _PLACEHOLDER_KEYS:
            keys[key.strip()] = name.strip()
    return keys


def auth_mode() -> str:
    """'open' in local development without keys, otherwise 'accounts' (log in or use a key)."""
    if config.IS_DEV and config.OPEN_DEV_ACCESS and not workspace_keys():
        return "open"
    return "accounts"


def _env_key_workspace(provided: str) -> str | None:
    # Compare against every key so timing doesn't reveal which ones exist
    match = None
    for key, workspace in workspace_keys().items():
        if secrets.compare_digest(provided.encode(), key.encode()):
            match = workspace
    return match


def session_from(request: Request) -> tuple[dict[str, Any], str] | None:
    return accounts.session_user(request.cookies.get(config.SESSION_COOKIE))


def check_csrf(request: Request, expected: str) -> None:
    if request.method in _UNSAFE_METHODS:
        sent = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(sent.encode(), expected.encode()):
            raise HTTPException(status_code=403, detail="Missing or stale CSRF token. Reload the page and try again.")


def identify(request: Request, provided_key: str | None) -> Identity | None:
    """Who is calling, or None for an anonymous request. Raises 401/403 for bad credentials."""
    if provided_key:
        if provided_key.startswith(accounts.API_KEY_PREFIX):
            user = accounts.user_for_api_key(provided_key)
            if user:
                return Identity(workspace=user["workspace"], via="api_key", user=user)
        else:
            workspace = _env_key_workspace(provided_key)
            if workspace:
                return Identity(workspace=workspace, via="env_key")
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: invalid or revoked API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session = session_from(request)
    if session:
        user, csrf = session
        check_csrf(request, csrf)
        return Identity(workspace=user["workspace"], via="session", user=user)
    return None


def verify_api_access(
    request: Request,
    header_key: str | None = Security(api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> bool:
    """Require a known caller, and record who it is on request.state."""
    provided = (header_key or (bearer.credentials if bearer else None) or "").strip()
    identity = identify(request, provided or None)
    if identity is None:
        if auth_mode() != "open":
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: log in, or send an API key (X-API-Key or Bearer token).",
                headers={"WWW-Authenticate": "Bearer"},
            )
        identity = Identity(workspace=DEFAULT_WORKSPACE, via="open")
    request.state.identity = identity
    request.state.workspace = identity.workspace
    return True


def identity_of(request: Request) -> Identity:
    return getattr(request.state, "identity", None) or Identity(workspace=DEFAULT_WORKSPACE, via="open")


def workspace_of(request: Request) -> str:
    return getattr(request.state, "workspace", DEFAULT_WORKSPACE)


def require_user(request: Request) -> dict[str, Any]:
    """For account pages: the signed-in user (session or their own API key)."""
    identity = identity_of(request)
    if identity.user is None:
        raise HTTPException(status_code=403, detail="This needs a signed-in account.")
    return identity.user


def require_operator(request: Request) -> Identity:
    identity = identity_of(request)
    if not identity.is_operator:
        raise HTTPException(status_code=403, detail="Only the server operator can do this.")
    return identity


def groq_key_of(request: Request) -> str | None:
    """A caller-supplied Groq key, if the server allows bring-your-own keys."""
    if not config.ALLOW_BYO_GROQ_KEY:
        return None
    key = request.headers.get("x-groq-key", "").strip()
    return key if key.startswith("gsk_") and len(key) < 200 else None


class RateLimiter:
    """Sliding window per client. Good enough for a single-process deployment."""

    def __init__(self, limit: int = 0, window_seconds: float = 60.0, per_minute: int | None = None):
        self.limit = per_minute if per_minute is not None else limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @property
    def per_minute(self) -> int:  # kept for older callers and tests
        return self.limit

    @per_minute.setter
    def per_minute(self, value: int) -> None:
        self.limit = value

    def check(self, client_id: str) -> None:
        if self.limit <= 0:
            return
        now = time.monotonic()
        with self._lock:
            hits = self._hits[client_id]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(1, int(self.window - (now - hits[0])))
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Slow down and try again shortly.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter(config.RATE_LIMIT_PER_MINUTE)
# Account endpoints: per client address, and per email address over a longer window
auth_limiter = RateLimiter(config.AUTH_RATE_LIMIT_PER_MINUTE)
email_limiter = RateLimiter(max(1, config.AUTH_RATE_LIMIT_PER_MINUTE // 2) if config.AUTH_RATE_LIMIT_PER_MINUTE else 0, 900)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _client_id(request: Request) -> str:
    identity = getattr(request.state, "identity", None)
    if identity is not None and identity.via != "open":
        return "user:" + (identity.user_id or identity.workspace)
    return "ip:" + client_ip(request)


def rate_limited(request: Request) -> None:
    """Dependency for endpoints that spend LLM tokens or sandbox time (after verify_api_access)."""
    limiter.check(_client_id(request))
