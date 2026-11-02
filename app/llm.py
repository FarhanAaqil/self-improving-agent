"""One place for every Groq call: client reuse, token accounting and output cleanup."""

import contextvars
import re
import threading
from contextlib import contextmanager
from typing import Any

from groq import Groq

from app.config import GROQ_API_KEY, MODEL

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S | re.I)

_clients: dict[str, Groq] = {}
_clients_lock = threading.Lock()

# Per-run accumulators. Each pipeline run sets its own, so concurrent runs never mix counts.
_usage: contextvars.ContextVar[dict | None] = contextvars.ContextVar("llm_usage", default=None)
# Bring-your-own Groq key for the current request, if the caller supplied one.
_request_key: contextvars.ContextVar[str | None] = contextvars.ContextVar("groq_key", default=None)


def get_client(api_key: str | None = None) -> Groq:
    key = api_key or _request_key.get() or GROQ_API_KEY or ""
    with _clients_lock:
        if key not in _clients:
            _clients[key] = Groq(api_key=key or None)
        return _clients[key]


@contextmanager
def track_usage():
    """Collect token usage for every chat() call made inside the block."""
    bucket = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
    token = _usage.set(bucket)
    try:
        yield bucket
    finally:
        _usage.reset(token)


@contextmanager
def groq_key(api_key: str | None):
    token = _request_key.set(api_key)
    try:
        yield
    finally:
        _request_key.reset(token)


def current_groq_key() -> str | None:
    return _request_key.get()


def usage_snapshot() -> dict:
    bucket = _usage.get()
    return dict(bucket) if bucket else {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}


def _record(response: Any) -> None:
    bucket = _usage.get()
    usage = getattr(response, "usage", None)
    if bucket is None or usage is None:
        return
    for field in ("prompt_tokens", "completion_tokens"):
        value = getattr(usage, field, 0)
        if isinstance(value, int):
            bucket[field] += value
    bucket["calls"] += 1


def chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 1024,
    client: Any = None,
) -> str:
    """Send a chat completion and return the stripped text content."""
    response = (client or get_client()).chat.completions.create(
        model=model or MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    _record(response)
    text = response.choices[0].message.content or ""
    # Reasoning models (Qwen3 and friends) may prepend their chain of thought
    return _THINK_BLOCK.sub("", text).strip()


def clean_code(raw: str) -> str:
    """Strip markdown fences that models add despite being told not to."""
    text = (raw or "").strip()
    if "```" not in text:
        return text
    lines = text.splitlines()
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
