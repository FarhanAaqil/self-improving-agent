"""Request-level guards: API key auth and a small in-process rate limiter."""

import re
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app import config

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
    """'key' when a real key is set, 'open' in local dev without one, 'locked' otherwise."""
    if workspace_keys():
        return "key"
    return "open" if config.IS_DEV else "locked"


def verify_api_access(
    request: Request,
    header_key: str | None = Security(api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> bool:
    """
    Require a configured API key via X-API-Key or Authorization: Bearer, and record which
    workspace it belongs to on request.state.workspace.
    Local development (APP_ENV=development) without keys stays open for convenience;
    any other environment without a key refuses every protected request.
    """
    mode = auth_mode()
    request.state.workspace = DEFAULT_WORKSPACE
    if mode == "open":
        return True
    if mode == "locked":
        raise HTTPException(
            status_code=503,
            detail="Server has no API_KEY configured. Set API_KEY (or APP_ENV=development locally).",
        )

    provided = (header_key or (bearer.credentials if bearer else None) or "").encode()
    # Compare against every key so timing doesn't reveal which ones exist
    match = None
    for key, workspace in workspace_keys().items():
        if secrets.compare_digest(provided, key.encode()):
            match = workspace
    if match is None:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or missing API key (X-API-Key or Bearer token).",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.workspace = match
    return True


def workspace_of(request: Request) -> str:
    return getattr(request.state, "workspace", DEFAULT_WORKSPACE)


def groq_key_of(request: Request) -> str | None:
    """A caller-supplied Groq key, if the server allows bring-your-own keys."""
    if not config.ALLOW_BYO_GROQ_KEY:
        return None
    key = request.headers.get("x-groq-key", "").strip()
    return key if key.startswith("gsk_") and len(key) < 200 else None


class RateLimiter:
    """Sliding one-minute window per client. Good enough for a single-process deployment."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client_id: str) -> None:
        if self.per_minute <= 0:
            return
        now = time.monotonic()
        with self._lock:
            hits = self._hits[client_id]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                retry_after = max(1, int(60 - (now - hits[0])))
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit reached. Slow down and try again shortly.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter(config.RATE_LIMIT_PER_MINUTE)


def _client_id(request: Request) -> str:
    key = request.headers.get("x-api-key") or request.headers.get("authorization")
    if key:
        return "key:" + key[-12:]
    return "ip:" + (request.client.host if request.client else "unknown")


def rate_limited(request: Request) -> None:
    """Dependency for endpoints that spend LLM tokens or sandbox time."""
    limiter.check(_client_id(request))
