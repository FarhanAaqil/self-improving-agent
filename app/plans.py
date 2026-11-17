"""Plans: the one place that says what each kind of account may do.

The server enforces every limit here; the UI only displays them. Change a number here
and it changes everywhere. Accounts drop back to `free` the moment `paid_until` passes.

Operators (API_KEY / API_KEYS, or local development with no keys) are not on a plan:
they run the server, so only DAILY_TOKEN_BUDGET and the global caps apply to them.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Plan:
    name: str
    label: str
    price: str
    # Runs (including each model in a comparison) a user may start per day (server time)
    runs_per_day: int
    # Runs of this user that may be working at once; more wait in the fair queue
    concurrent_runs: int
    # Runs older than this are deleted, and hidden right away
    history_days: int
    # May runs use the server's Groq key when the user didn't bring one?
    server_key: bool
    # Tokens per day (server time) that runs on the server's key may spend
    server_token_budget: int
    # Shown under the price, e.g. the yearly option
    price_note: str = ""

    def public(self) -> dict[str, Any]:
        return asdict(self)


PLANS: dict[str, Plan] = {
    "free": Plan(
        name="free",
        label="Free",
        price="$0",
        runs_per_day=25,
        concurrent_runs=1,
        history_days=30,
        server_key=False,
        server_token_budget=0,
    ),
    "pro": Plan(
        name="pro",
        label="Pro",
        price="$12 / month",
        runs_per_day=300,
        concurrent_runs=3,
        history_days=365,
        server_key=True,
        # A typical run is ~4k tokens, so ~25 runs a day on our key. At Groq's price for the
        # dearest default model this keeps even a maxed-out Pro account below its $12
        server_token_budget=100_000,
        price_note="or $120 / year (two months free)",
    ),
}

DEFAULT_PLAN = "free"

# Brand-new accounts get tighter limits for their first day (abuse control)
NEW_ACCOUNT_HOURS = 24
NEW_ACCOUNT_RUNS_PER_DAY = 10


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        moment = datetime.fromisoformat(str(value))
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def effective_plan_name(user: dict[str, Any] | None, now: datetime | None = None) -> str:
    """The plan in force right now. A paid plan without a future paid_until counts as free."""
    if not user:
        return DEFAULT_PLAN
    name = user.get("plan") or DEFAULT_PLAN
    if name == DEFAULT_PLAN or name not in PLANS:
        return DEFAULT_PLAN
    paid_until = _parse(user.get("paid_until"))
    if paid_until is None or paid_until <= (now or datetime.now(timezone.utc)):
        return DEFAULT_PLAN
    return name


def plan_for(user: dict[str, Any] | None, now: datetime | None = None) -> Plan:
    return PLANS[effective_plan_name(user, now)]


def is_new_account(user: dict[str, Any] | None, now: datetime | None = None) -> bool:
    created = _parse((user or {}).get("created_at"))
    if created is None:
        return False
    age = (now or datetime.now(timezone.utc)) - created
    return age.total_seconds() < NEW_ACCOUNT_HOURS * 3600


def runs_per_day(user: dict[str, Any] | None, now: datetime | None = None) -> int:
    limit = plan_for(user, now).runs_per_day
    return min(limit, NEW_ACCOUNT_RUNS_PER_DAY) if is_new_account(user, now) else limit
