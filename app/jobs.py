"""Background execution of pipeline runs.

A small thread pool is enough for a single-process deployment: the work is dominated by
waiting on Groq and Docker, not CPU. Context variables (like a bring-your-own Groq key)
are copied into the worker so each run keeps the caller's settings.
"""

import contextvars
import logging
import os
from concurrent.futures import Future, ThreadPoolExecutor

from app import db
from app.pipeline import RunSpec, execute_run

logger = logging.getLogger("self_improving_agent.jobs")

_executor = ThreadPoolExecutor(
    max_workers=int(os.getenv("MAX_CONCURRENT_RUNS", "3")),
    thread_name_prefix="agent-run",
)


def submit_run(run_id: str, spec: RunSpec) -> Future:
    ctx = contextvars.copy_context()
    future = _executor.submit(ctx.run, execute_run, run_id, spec)
    future.add_done_callback(_log_crash)
    return future


def _log_crash(future: Future) -> None:
    exc = future.exception()
    if exc:
        logger.error("Background run crashed: %s", exc, exc_info=exc)


def recover_interrupted_runs() -> int:
    """Runs left 'running' by a previous process can never finish; mark them failed."""
    with db.get_connection() as conn:
        cursor = conn.execute(
            "UPDATE runs SET final_status = 'failed' WHERE final_status IN ('running', 'queued')"
        )
        return cursor.rowcount
