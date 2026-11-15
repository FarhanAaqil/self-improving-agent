"""Operator-only endpoints: managing accounts and plans.

Only the server's operator (an API_KEY / API_KEYS key, or local development with no keys)
and accounts listed in ADMIN_EMAILS can call these. Plans can also be set from the command
line (python -m app.admin) and backups made with python -m app.backup.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app import accounts, billing, config, db, plans
from app.security import identity_of, require_operator, verify_api_access

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(verify_api_access), Depends(require_operator)])


class ActiveChange(BaseModel):
    active: bool


class PlanChange(BaseModel):
    plan: str = Field(..., max_length=20)
    days: int | None = Field(None, ge=1, le=3660)
    until: datetime | None = None


@router.post("/users/{user_id}/plan")
def set_plan(user_id: str, body: PlanChange, request: Request):
    """Version 1 of payment: after a payment arrives, put the account on a plan until a date."""
    try:
        user = billing.grant_plan(user_id, body.plan, days=body.days, until=body.until)
    except LookupError:
        raise HTTPException(status_code=404, detail="No such account.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"user_id": user["user_id"], "plan": user.get("plan"), "paid_until": user.get("paid_until")}


@router.get("/users/lookup")
def lookup(email: str):
    user = accounts.get_user_by_email(email)
    if user is None:
        raise HTTPException(status_code=404, detail="No such account.")
    return {k: user.get(k) for k in ("user_id", "email", "plan", "paid_until", "active", "created_at")}


@router.get("/users")
def list_users(q: str | None = Query(None, max_length=200), page: int = Query(1, ge=1),
               page_size: int = Query(50, ge=1, le=200)):
    """Every account with its plan, today's usage and whether it's enabled."""
    today = datetime.now().date().isoformat()
    where, params = "", []
    if q:
        where = "WHERE u.email LIKE ? OR u.user_id LIKE ?"
        params = [f"%{q.lower()}%", f"%{q}%"]
    with db.get_connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM users u {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""SELECT u.user_id, u.email, u.plan, u.paid_until, u.active, u.email_verified_at, u.created_at,
                       COUNT(r.run_id) AS runs_total,
                       COALESCE(SUM(CASE WHEN substr(r.created_at, 1, 10) = ? THEN 1 ELSE 0 END), 0) AS runs_today,
                       COALESCE(SUM(CASE WHEN substr(r.created_at, 1, 10) = ? AND r.key_source = 'server'
                                    THEN COALESCE(r.prompt_tokens, 0) + COALESCE(r.completion_tokens, 0) ELSE 0 END), 0)
                           AS server_tokens_today
                FROM users u LEFT JOIN runs r ON r.workspace = u.user_id
                {where}
                GROUP BY u.user_id ORDER BY u.created_at DESC LIMIT ? OFFSET ?""",
            [today, today, *params, page_size, (page - 1) * page_size],
        ).fetchall()
    items = []
    for row in rows:
        user = dict(row)
        items.append({
            **user,
            "active": bool(user["active"]),
            "verified": bool(user.pop("email_verified_at")),
            "effective_plan": plans.effective_plan_name(user),
            "new_account": plans.is_new_account(user),
            "admin": user["email"] in config.ADMIN_EMAILS,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/users/{user_id}/active")
def set_active(user_id: str, body: ActiveChange, request: Request):
    """The disable switch: a disabled account is signed out everywhere and its keys stop working."""
    if identity_of(request).user_id == user_id:
        raise HTTPException(status_code=409, detail="You can't disable your own account.")
    if accounts.get_user(user_id) is None:
        raise HTTPException(status_code=404, detail="No such account.")
    accounts.set_active(user_id, body.active)
    return {"user_id": user_id, "active": body.active}


@router.post("/backup")
def backup_now():
    """Take a backup now (safe while the server runs) into BACKUP_DIR."""
    from app.backup import create_backup, prune

    if not config.BACKUP_DIR:
        raise HTTPException(status_code=409, detail="Set BACKUP_DIR to enable backups.")
    path = create_backup()
    prune()
    return {"archive": path.name}


@router.get("/backups")
def list_backups():
    from app.backup import list_backups as found

    return {"items": [{"name": p.name, "bytes": p.stat().st_size} for p in reversed(found())],
            "dir_configured": bool(config.BACKUP_DIR)}
