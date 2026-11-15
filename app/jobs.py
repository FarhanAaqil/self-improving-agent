"""Background execution of pipeline runs, shared fairly between users.

A fixed number of workers (MAX_CONCURRENT_RUNS) serve one queue per workspace in
round-robin order, so a user who queues twenty runs can't make everyone else wait behind
them. Each workspace may also have its own cap (its plan's concurrent runs); its extra
runs wait, as "queued", until one of its own finishes. The sandbox has a separate global
cap (MAX_CONCURRENT_SANDBOXES) and a per-user cap of its own in app/sandbox.py.

Context variables (like a bring-your-own Groq key) are copied into the worker so each run
keeps the caller's settings.
"""

import contextvars
import logging
import os
import threading
from collections import deque
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field

from app import db
from app.pipeline import RunSpec, execute_run

logger = logging.getLogger("self_improving_agent.jobs")


@dataclass
class _Job:
    run_id: str
    spec: RunSpec
    limit: int
    ctx: contextvars.Context
    future: Future = field(default_factory=Future)


class FairScheduler:
    """Round-robin across workspaces, with an optional per-workspace concurrency cap."""

    def __init__(self, workers: int, execute: Callable[[str, RunSpec], object] = execute_run):
        self.workers = max(1, workers)
        self.execute = execute
        self._queues: dict[str, deque[_Job]] = {}
        self._turns: deque[str] = deque()  # workspaces with waiting jobs, in serving order
        self._running: dict[str, int] = {}
        self._cond = threading.Condition()
        self._threads: list[threading.Thread] = []

    def submit(self, run_id: str, spec: RunSpec, limit: int = 0) -> Future:
        job = _Job(run_id, spec, limit, contextvars.copy_context())
        with self._cond:
            self._start_workers()
            queue = self._queues.setdefault(spec.workspace, deque())
            queue.append(job)
            if spec.workspace not in self._turns:
                self._turns.append(spec.workspace)
            self._cond.notify()
        return job.future

    def queued(self, workspace: str) -> int:
        with self._cond:
            return len(self._queues.get(workspace, ()))

    def running(self, workspace: str) -> int:
        with self._cond:
            return self._running.get(workspace, 0)

    def _start_workers(self) -> None:
        while len(self._threads) < self.workers:
            thread = threading.Thread(target=self._work, name=f"agent-run-{len(self._threads)}", daemon=True)
            self._threads.append(thread)
            thread.start()

    def _next_job(self) -> _Job | None:
        """The next job from the first workspace in line that is under its own cap."""
        for _ in range(len(self._turns)):
            workspace = self._turns.popleft()
            queue = self._queues.get(workspace)
            if not queue:
                continue
            job = queue[0]
            if job.limit and self._running.get(workspace, 0) >= job.limit:
                self._turns.append(workspace)  # still waiting; keep its place in the rotation
                continue
            queue.popleft()
            if queue:
                self._turns.append(workspace)  # back of the line for its next job
            else:
                self._queues.pop(workspace, None)
            self._running[workspace] = self._running.get(workspace, 0) + 1
            return job
        return None

    def _work(self) -> None:
        while True:
            with self._cond:
                job = self._next_job()
                while job is None:
                    self._cond.wait()
                    job = self._next_job()
            try:
                result = job.ctx.run(self.execute, job.run_id, job.spec)
                job.future.set_result(result)
            except BaseException as exc:  # noqa: BLE001 - recorded on the future and logged
                logger.error("Background run %s crashed: %s", job.run_id, exc, exc_info=exc)
                job.future.set_exception(exc)
            finally:
                with self._cond:
                    workspace = job.spec.workspace
                    self._running[workspace] -= 1
                    if not self._running[workspace]:
                        del self._running[workspace]
                    self._cond.notify_all()


scheduler = FairScheduler(int(os.getenv("MAX_CONCURRENT_RUNS", "3")))


def submit_run(run_id: str, spec: RunSpec) -> Future:
    return scheduler.submit(run_id, spec, limit=spec.concurrency_limit)


def recover_interrupted_runs() -> int:
    """Runs left 'running' by a previous process can never finish; mark them failed."""
    with db.get_connection() as conn:
        cursor = conn.execute(
            "UPDATE runs SET final_status = 'failed' WHERE final_status IN ('running', 'queued')"
        )
        return cursor.rowcount
