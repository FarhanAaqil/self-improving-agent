"""Optional error tracking with Sentry, configured so it never carries secrets or code.

Off unless SENTRY_DSN is set. Settings (from Sentry's Python docs): no default PII, no
request bodies, no local variables (frames here can hold submitted code and keys), and a
before_send hook that strips cookies, auth headers, Groq keys and query strings, keeping
only the user id and the request id.
"""

import logging
from typing import Any

from app import config

logger = logging.getLogger("self_improving_agent.errors")

_SECRET_HEADERS = {"authorization", "x-api-key", "x-groq-key", "x-csrf-token", "cookie", "set-cookie"}


def scrub(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Sentry's before_send: drop everything that could hold a key, a password or code."""
    request = event.get("request")
    if isinstance(request, dict):
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {k: ("[removed]" if k.lower() in _SECRET_HEADERS else v) for k, v in headers.items()}
        for key in ("cookies", "data", "query_string", "env"):
            request.pop(key, None)
    user = event.get("user")
    if isinstance(user, dict):
        event["user"] = {"id": user["id"]} if "id" in user else {}
    for entry in (event.get("exception") or {}).get("values", []) or []:
        for frame in (entry.get("stacktrace") or {}).get("frames", []) or []:
            frame.pop("vars", None)
    event.pop("extra", None)
    return event


def init_error_tracking() -> bool:
    """Start Sentry if SENTRY_DSN is set. Returns whether it is on."""
    if not config.SENTRY_DSN:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk isn't installed; error tracking is off")
        return False
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        environment=config.APP_ENV,
        release=config.RELEASE or None,
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE,
        before_send=scrub,
    )
    logger.info("Error tracking is on (environment %s)", config.APP_ENV)
    return True


def tag_user(user_id: str | None) -> None:
    """Attach only the account id to errors raised while serving this request."""
    if not (config.SENTRY_DSN and user_id):
        return
    try:
        import sentry_sdk

        sentry_sdk.set_user({"id": user_id})
    except Exception:
        pass
