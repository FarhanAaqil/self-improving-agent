"""Operator command line for accounts and plans. Safe to run while the server is up.

    python -m app.admin set-plan someone@example.com pro --days 31
    python -m app.admin set-plan someone@example.com pro --until 2027-01-31
    python -m app.admin set-plan someone@example.com free
    python -m app.admin show someone@example.com
    python -m app.admin expire          # move lapsed paid accounts back to free now
"""

import argparse
import sys
from datetime import datetime, timezone

from app import accounts, billing, db


def _user_or_exit(email: str) -> dict:
    user = accounts.get_user_by_email(email)
    if user is None:
        sys.exit(f"No account with the email {email!r}")
    return user


def _show(user: dict) -> None:
    for key in ("user_id", "email", "plan", "paid_until", "active", "email_verified_at", "created_at"):
        print(f"{key:>18}: {user.get(key)}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.admin", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    set_plan = sub.add_parser("set-plan", help="put an account on a plan")
    set_plan.add_argument("email")
    set_plan.add_argument("plan")
    when = set_plan.add_mutually_exclusive_group()
    when.add_argument("--days", type=int, help="paid for this many days (added after any time left)")
    when.add_argument("--until", help="paid until this date, YYYY-MM-DD (UTC end of day)")

    show = sub.add_parser("show", help="show an account")
    show.add_argument("email")

    sub.add_parser("expire", help="move lapsed paid accounts back to free")

    args = parser.parse_args(argv)
    db.init_db()

    if args.command == "set-plan":
        user = _user_or_exit(args.email)
        until = None
        if args.until:
            until = datetime.fromisoformat(args.until).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        try:
            updated = billing.grant_plan(user["user_id"], args.plan, days=args.days, until=until)
        except ValueError as exc:
            sys.exit(str(exc))
        _show(updated)
    elif args.command == "show":
        _show(_user_or_exit(args.email))
    elif args.command == "expire":
        print(f"{billing.expire_lapsed_plans()} account(s) moved back to free")


if __name__ == "__main__":
    main()
