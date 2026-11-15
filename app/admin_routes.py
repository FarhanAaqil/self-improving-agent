"""Operator-only endpoints: managing accounts and plans.

Only the server's operator (an API_KEY / API_KEYS key, or local development with no keys)
can call these. Everything here can also be done from the command line: python -m app.admin
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app import accounts, billing
from app.security import require_operator, verify_api_access

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(verify_api_access), Depends(require_operator)])


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
