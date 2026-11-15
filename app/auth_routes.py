"""Sign up, verify email, log in and out, reset a password, and manage API keys."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app import accounts, config, mailer, plans
from app.security import (
    auth_limiter,
    auth_mode,
    check_csrf,
    client_ip,
    email_limiter,
    identity_of,
    require_user,
    session_from,
    verify_api_access,
)

logger = logging.getLogger("self_improving_agent.auth")
router = APIRouter(tags=["Accounts"])

# The same answer whether or not an account exists, so nobody can probe for emails
CHECK_INBOX = "If that address can use this service, an email is on its way. Check your inbox."


class Credentials(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=accounts.PASSWORD_MAX)


class EmailOnly(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)


class TokenOnly(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)


class ResetRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)
    password: str = Field(..., min_length=1, max_length=accounts.PASSWORD_MAX)


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=accounts.PASSWORD_MAX)
    new_password: str = Field(..., min_length=1, max_length=accounts.PASSWORD_MAX)


class KeyRequest(BaseModel):
    name: str = Field("", max_length=60)


def _github_configured() -> bool:
    from app.github_agent import IS_GITHUB_CONFIGURED

    return IS_GITHUB_CONFIGURED


def _throttle(request: Request, email: str | None = None) -> None:
    auth_limiter.check("ip:" + client_ip(request))
    if email:
        email_limiter.check("email:" + accounts.normalize_email(email))


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    """What the browser may know about the signed-in account."""
    plan = plans.plan_for(user)
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "email_verified": bool(user.get("email_verified_at")),
        "created_at": user.get("created_at"),
        "plan": plan.public(),
        "paid_until": user.get("paid_until") if plan.name != plans.DEFAULT_PLAN else None,
        # Free plans can't use the server's Groq key: the UI asks for the user's own first
        "needs_own_groq_key": not plan.server_key,
    }


def _start_session(response: Response, user_id: str) -> str:
    session_id, csrf = accounts.create_session(user_id)
    response.set_cookie(
        config.SESSION_COOKIE,
        session_id,
        max_age=config.SESSION_TTL_DAYS * 86400,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    return csrf


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(config.SESSION_COOKIE, path="/", secure=config.COOKIE_SECURE, httponly=True, samesite="strict")


def _send_verification(user: dict[str, Any]) -> None:
    token = accounts.issue_token(user["user_id"], "verify")
    mailer.send(
        user["email"],
        "Confirm your email for CODE_AGENT",
        "Welcome to CODE_AGENT.\n\n"
        f"Confirm your email address to start using it:\n{mailer.link('/verify?token=' + token)}\n\n"
        "The link works once and expires in 48 hours. If you didn't sign up, ignore this email.",
    )


# ── Session ──────────────────────────────────────────────────


@router.get("/auth/me")
def me(request: Request):
    """The signed-in account (or null), its CSRF token, and how this server authenticates."""
    session = session_from(request)
    return {
        "user": public_user(session[0]) if session else None,
        "csrf_token": session[1] if session else None,
        "auth": auth_mode(),
        # Local development without keys is run by its operator
        "operator": session is None and auth_mode() == "open",
        "can_open_prs": session is None and auth_mode() == "open" and _github_configured(),
        "signups_open": config.SIGNUPS_OPEN,
    }


@router.post("/auth/signup", status_code=202)
def signup(body: Credentials, request: Request):
    _throttle(request, body.email)
    if not config.SIGNUPS_OPEN:
        raise HTTPException(status_code=403, detail="Sign-ups are closed on this server right now.")
    try:
        user = accounts.create_user(body.email, body.password)
    except accounts.AccountError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if user:
        _send_verification(user)
    else:
        accounts.waste_a_hash(body.password)  # same cost as creating an account
        existing = accounts.get_user_by_email(body.email)
        if existing and existing.get("active"):
            if existing.get("email_verified_at"):
                mailer.send(
                    existing["email"],
                    "Someone tried to sign up with your email",
                    "Someone (maybe you) tried to create a CODE_AGENT account with this address, "
                    "but you already have one.\n\n"
                    f"Log in: {mailer.link('/login')}\n"
                    f"Forgot your password? {mailer.link('/forgot')}",
                )
            else:
                _send_verification(existing)
    return {"message": CHECK_INBOX}


@router.post("/auth/resend-verification", status_code=202)
def resend_verification(body: EmailOnly, request: Request):
    _throttle(request, body.email)
    user = accounts.get_user_by_email(body.email)
    if user and user.get("active") and not user.get("email_verified_at"):
        _send_verification(user)
    return {"message": CHECK_INBOX}


@router.post("/auth/verify")
def verify_email(body: TokenOnly, request: Request, response: Response):
    _throttle(request)
    user_id = accounts.consume_token(body.token, "verify")
    user = accounts.get_user(user_id) if user_id else None
    if not user or not user.get("active"):
        raise HTTPException(status_code=400, detail="This link is invalid, expired or already used. Ask for a new one.")
    accounts.mark_verified(user_id)
    csrf = _start_session(response, user_id)
    return {"user": public_user(accounts.get_user(user_id)), "csrf_token": csrf}


@router.post("/auth/login")
def login(body: Credentials, request: Request, response: Response):
    _throttle(request, body.email)
    user = accounts.authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="That email and password don't match an account.")
    if not user.get("active"):
        raise HTTPException(status_code=403, detail="This account is disabled. Contact the operator.")
    if not user.get("email_verified_at"):
        _send_verification(user)
        raise HTTPException(status_code=403, detail="Confirm your email first. We just sent you a fresh link.")
    csrf = _start_session(response, user["user_id"])
    return {"user": public_user(user), "csrf_token": csrf}


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    session = session_from(request)
    if session:
        check_csrf(request, session[1])
        accounts.end_session(request.cookies.get(config.SESSION_COOKIE))
    _clear_session_cookie(response)
    return {"logged_out": True}


@router.post("/auth/forgot", status_code=202)
def forgot_password(body: EmailOnly, request: Request):
    _throttle(request, body.email)
    user = accounts.get_user_by_email(body.email)
    if user and user.get("active"):
        token = accounts.issue_token(user["user_id"], "reset")
        mailer.send(
            user["email"],
            "Reset your CODE_AGENT password",
            f"Choose a new password here:\n{mailer.link('/reset?token=' + token)}\n\n"
            "The link works once and expires in an hour. If you didn't ask for this, ignore this email; "
            "your password stays the same.",
        )
    return {"message": CHECK_INBOX}


@router.post("/auth/reset")
def reset_password(body: ResetRequest, request: Request):
    _throttle(request)
    try:
        accounts.check_password_strength(body.password)
    except accounts.AccountError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    user_id = accounts.consume_token(body.token, "reset")
    if not user_id:
        raise HTTPException(status_code=400, detail="This link is invalid, expired or already used. Ask for a new one.")
    accounts.set_password(user_id, body.password)
    accounts.mark_verified(user_id)  # they proved they read this inbox
    accounts.end_all_sessions(user_id)  # anyone signed in with the old password is signed out
    return {"message": "Password changed. Log in with your new password."}


# ── The signed-in account ────────────────────────────────────


@router.post("/account/password", dependencies=[Depends(verify_api_access)])
def change_password(body: PasswordChange, request: Request, response: Response):
    user = require_user(request)
    _throttle(request)
    if accounts.authenticate(user["email"], body.current_password) is None:
        raise HTTPException(status_code=403, detail="Your current password isn't right.")
    try:
        accounts.set_password(user["user_id"], body.new_password)
    except accounts.AccountError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    accounts.end_all_sessions(user["user_id"])
    csrf = _start_session(response, user["user_id"])  # keep this browser signed in
    return {"changed": True, "csrf_token": csrf}


@router.get("/account/keys", dependencies=[Depends(verify_api_access)])
def list_keys(request: Request):
    return {"items": accounts.list_api_keys(require_user(request)["user_id"])}


@router.post("/account/keys", status_code=201, dependencies=[Depends(verify_api_access)])
def create_key(body: KeyRequest, request: Request):
    user = require_user(request)
    if identity_of(request).via != "session":
        raise HTTPException(status_code=403, detail="Create API keys from a signed-in browser session.")
    active = [k for k in accounts.list_api_keys(user["user_id"]) if not k["revoked_at"]]
    if len(active) >= 10:
        raise HTTPException(status_code=409, detail="You already have 10 active keys. Revoke one first.")
    record, secret = accounts.create_api_key(user["user_id"], body.name)
    return {"key": secret, "record": record, "message": "Copy this key now. It won't be shown again."}


@router.delete("/account/keys/{key_id}", dependencies=[Depends(verify_api_access)])
def revoke_key(key_id: str, request: Request):
    if not accounts.revoke_api_key(require_user(request)["user_id"], key_id):
        raise HTTPException(status_code=404, detail="Key not found.")
    return {"revoked": key_id}
