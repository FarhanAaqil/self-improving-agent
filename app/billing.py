"""Plans and payment, version 1: a payment link and an operator action.

The Upgrade button opens PAYMENT_LINK_URL (any provider's hosted checkout or payment link).
After the payment arrives, the operator runs one command (or calls the admin API) to set
the account to `pro` until a date; when that date passes the account is free again.

Version 2 (later): a webhook from the payment provider calls `grant_plan` for the paying
user, after verifying the provider's signature and recording the event id so a retried
delivery isn't applied twice. Everything below already works for that caller too.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from app import accounts, config, db
from app.plans import DEFAULT_PLAN, PLANS

logger = logging.getLogger("self_improving_agent.billing")


def payments_enabled() -> bool:
    return bool(config.PAYMENT_LINK_URL)


def payment_link(user: dict[str, Any]) -> str | None:
    """The checkout URL for this user. `{user_id}` and `{email}` in the template are filled in,
    so the payment can be matched to the account (most providers echo them back)."""
    template = config.PAYMENT_LINK_URL
    if not template:
        return None
    return template.replace("{user_id}", quote(user["user_id"], safe="")).replace(
        "{email}", quote(user["email"], safe="")
    )


def grant_plan(user_id: str, plan: str, *, days: int | None = None, until: datetime | None = None) -> dict[str, Any]:
    """Put an account on `plan` until a moment (or for N days from now, or from the current
    paid_until if that is later, so renewing early never loses days)."""
    if plan not in PLANS:
        raise ValueError(f"Unknown plan {plan!r}. Known: {', '.join(PLANS)}")
    user = accounts.get_user(user_id)
    if user is None:
        raise LookupError(f"No account {user_id!r}")
    if plan == DEFAULT_PLAN:
        paid_until = None
    else:
        if until is None:
            if days is None or days <= 0:
                raise ValueError("Give a positive number of days or an end date for a paid plan.")
            current = accounts.parse_time(user.get("paid_until"))
            start = max(current, accounts.now()) if current else accounts.now()
            until = start + timedelta(days=days)
        paid_until = until.astimezone(timezone.utc).isoformat()
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET plan = ?, paid_until = ? WHERE user_id = ?", (plan, paid_until, user_id))
    logger.info("Plan for %s set to %s until %s", user_id, plan, paid_until or "-")
    return accounts.get_user(user_id)


def expire_lapsed_plans(now: datetime | None = None) -> int:
    """Move accounts whose paid_until has passed back to the free plan. Returns how many."""
    moment = (now or accounts.now()).astimezone(timezone.utc).isoformat()
    with db.get_connection() as conn:
        return conn.execute(
            "UPDATE users SET plan = ? WHERE plan != ? AND (paid_until IS NULL OR paid_until <= ?)",
            (DEFAULT_PLAN, DEFAULT_PLAN, moment),
        ).rowcount
