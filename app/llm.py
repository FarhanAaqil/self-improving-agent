"""One place for every Groq call: client reuse, token accounting and output cleanup."""

import contextvars
import logging
import random
import re
import threading
import time
from contextlib import contextmanager
from typing import Any

from groq import Groq

from app.config import (
    FAKE_LLM,
    GROQ_API_KEY,
    LLM_MAX_OUTPUT_TOKENS,
    LLM_MAX_RETRIES,
    LLM_MAX_WAIT_SECONDS,
    MODEL,
)

logger = logging.getLogger("self_improving_agent.llm")

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S | re.I)

_clients: dict[str, Groq] = {}
_MAX_CLIENTS = 32
_clients_lock = threading.Lock()

# Per-run accumulators. Each pipeline run sets its own, so concurrent runs never mix counts.
_usage: contextvars.ContextVar[dict | None] = contextvars.ContextVar("llm_usage", default=None)
# Bring-your-own Groq key for the current request, if the caller supplied one.
_request_key: contextvars.ContextVar[str | None] = contextvars.ContextVar("groq_key", default=None)


def get_client(api_key: str | None = None) -> Groq:
    key = api_key or _request_key.get() or GROQ_API_KEY or ""
    with _clients_lock:
        if key not in _clients:
            # Bring-your-own keys would otherwise pile up forever; keep the most recent few
            while len(_clients) >= _MAX_CLIENTS:
                _clients.pop(next(iter(_clients)))
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


class EmptyCompletion(RuntimeError):
    """The model produced no usable text."""


_TRANSIENT = ("RateLimitError", "APIConnectionError", "APITimeoutError", "InternalServerError")


def is_transient(exc: BaseException) -> bool:
    """Rate limits, timeouts and server errors: the provider's problem, not the task's."""
    return type(exc).__name__ in _TRANSIENT


def _retry_after(exc: Exception) -> float | None:
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    try:
        return float(headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


def _create_with_retry(client: Any, **kwargs: Any) -> Any:
    """
    Rate limits and brief outages are normal on free tiers; a run should wait them out
    rather than fail. Honors the server's retry-after, with capped exponential backoff.
    """
    delay = 2.0
    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            if not is_transient(exc) or attempt == LLM_MAX_RETRIES:
                raise
            wait = min(_retry_after(exc) or delay, LLM_MAX_WAIT_SECONDS)
            logger.info("LLM call hit %s; retrying in %.0fs (%d/%d)",
                        type(exc).__name__, wait, attempt + 1, LLM_MAX_RETRIES)
            time.sleep(wait + random.uniform(0, 1))
            delay = min(delay * 2, LLM_MAX_WAIT_SECONDS)


def chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 1024,
    client: Any = None,
) -> str:
    """Send a chat completion and return the stripped text content."""
    if FAKE_LLM and client is None:
        from app import fake_llm

        reply = fake_llm.respond(messages)
        bucket = _usage.get()
        if bucket is not None:
            bucket["prompt_tokens"] += sum(len(m["content"]) for m in messages) // 4
            bucket["completion_tokens"] += len(reply) // 4
            bucket["calls"] += 1
        return reply

    # Reasoning models can spend the whole budget thinking and return nothing, or stop
    # mid-answer. Either way, ask again with more room before giving up.
    budget = max_tokens
    text = ""
    while True:
        response = _create_with_retry(
            client or get_client(),
            model=model or MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=budget,
        )
        _record(response)
        choice = response.choices[0]
        # Reasoning models (Qwen3 and friends) may prepend their chain of thought
        text = _THINK_BLOCK.sub("", choice.message.content or "").strip()
        cut_off = getattr(choice, "finish_reason", None) == "length"
        if (text and not cut_off) or budget >= LLM_MAX_OUTPUT_TOKENS:
            break
        budget = min(budget * 2, LLM_MAX_OUTPUT_TOKENS)
    if not text:
        raise EmptyCompletion(f"The model returned no text even with {budget} output tokens.")
    return text


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
