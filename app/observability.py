"""Structured logging, request ids and a dependency-free Prometheus /metrics endpoint."""

import contextvars
import json
import logging
import threading
import time
import uuid
from collections import defaultdict

from app.config import LOG_FORMAT

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id.get(),
        }
        for key in ("run_id", "workspace", "status", "duration_ms", "path", "method", "status_code"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging() -> None:
    root = logging.getLogger()
    if any(getattr(h, "_agent_handler", False) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler._agent_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(
        JsonFormatter() if LOG_FORMAT == "json"
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def new_request_id(incoming: str | None) -> str:
    # Accept a sane upstream id (from a proxy) or mint one
    if incoming and len(incoming) <= 64 and incoming.replace("-", "").isalnum():
        return incoming
    return uuid.uuid4().hex[:16]


class Metrics:
    """Counters and simple latency sums, rendered in the Prometheus text format."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple], float] = defaultdict(float)
        self._help = {
            "agent_http_requests_total": "HTTP requests by method, route and status.",
            "agent_http_request_seconds_sum": "Total seconds spent serving HTTP requests.",
            "agent_runs_total": "Finished pipeline runs by final status.",
            "agent_sandbox_executions_total": "Sandbox executions by outcome.",
            "agent_sandbox_seconds_sum": "Total seconds spent inside the sandbox.",
            "agent_llm_tokens_total": "LLM tokens spent by kind.",
        }

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] += value

    def render(self) -> str:
        with self._lock:
            items = sorted(self._counters.items())
        lines, seen = [], set()
        for (name, labels), value in items:
            if name not in seen:
                seen.add(name)
                lines.append(f"# HELP {name} {self._help.get(name, name)}")
                lines.append(f"# TYPE {name} counter")
            label_text = ",".join(f'{k}="{str(v).replace(chr(34), "")}"' for k, v in labels)
            lines.append(f"{name}{{{label_text}}} {value}" if label_text else f"{name} {value}")
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()


metrics = Metrics()
