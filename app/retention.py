"""History kept per plan, and the background chores that keep the server tidy.

Runs older than a user's plan allows are hidden from that user at once (see
`history_cutoff`) and deleted for good by `purge_expired_history`, which the maintenance
thread runs every few hours together with expiring lapsed plans. Operators' workspaces
(API_KEY / API_KEYS / local development) keep their history.
"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from app import billing, db
from app.plans import plan_for

logger = logging.getLogger("self_improving_agent.maintenance")


def history_cutoff(user: dict[str, Any] | None, now: datetime | None = None) -> str | None:
    """Runs created before this moment are past the user's plan (runs use local time)."""
    if not user:
        return None
    return ((now or datetime.now()) - timedelta(days=plan_for(user).history_days)).isoformat()


DEMO_WORKSPACE = "demo"


def purge_demo_runs(now: datetime | None = None) -> int:
    """Demo runs only need to live long enough to be watched; drop them after a day."""
    cutoff = ((now or datetime.now()) - timedelta(days=1)).isoformat()
    with db.get_connection() as conn:
        return conn.execute("DELETE FROM runs WHERE workspace = ? AND created_at < ?", (DEMO_WORKSPACE, cutoff)).rowcount


def purge_expired_history(now: datetime | None = None) -> int:
    """Delete runs (with their attempts and events) older than each owner's plan allows."""
    with db.get_connection() as conn:
        users = [dict(r) for r in conn.execute("SELECT user_id, plan, paid_until FROM users").fetchall()]
    deleted = 0
    for user in users:
        cutoff = history_cutoff(user, now)
        with db.get_connection() as conn:
            deleted += conn.execute(
                "DELETE FROM runs WHERE workspace = ? AND created_at < ?", (user["user_id"], cutoff)
            ).rowcount
    return deleted


# Extra chores later phases add (backups, for example): each is called on every tick
_extra_chores: list[Callable[[], Any]] = []


def add_chore(chore: Callable[[], Any]) -> None:
    _extra_chores.append(chore)


def run_maintenance(now: datetime | None = None) -> dict[str, int]:
    result = {
        "plans_expired": billing.expire_lapsed_plans(),
        "runs_purged": purge_expired_history(now),
        "demo_runs_purged": purge_demo_runs(now),
    }
    for chore in _extra_chores:
        try:
            chore()
        except Exception:
            logger.error("Maintenance chore %s failed", getattr(chore, "__name__", chore), exc_info=True)
    if any(result.values()):
        logger.info("Maintenance: %s", result)
    return result


class Maintenance:
    """A daemon thread that runs the chores at start-up and then every `interval` seconds."""

    def __init__(self, interval: float):
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None and self.interval > 0:
            self._thread = threading.Thread(target=self._loop, name="maintenance", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                run_maintenance()
            except Exception:
                logger.error("Maintenance tick failed", exc_info=True)
            self._stop.wait(self.interval)
