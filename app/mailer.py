"""Outgoing email over SMTP, configured from the environment.

Without SMTP settings in development, messages (and the links in them) are printed to the
log instead, so sign-up works locally with no mail server. In production without SMTP the
message is dropped with a warning: links carry secrets and never go to production logs.

MAIL_OUTBOX_DIR (development and tests only) also writes each message to a JSON file, which
the end-to-end tests read to follow a real verification link.
"""

import json
import logging
import os
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

from app import config

logger = logging.getLogger("self_improving_agent.mail")


def is_configured() -> bool:
    return bool(config.SMTP_HOST and config.MAIL_FROM)


def _build(to: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = config.MAIL_FROM or "CODE_AGENT <no-reply@localhost>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def _send_smtp(msg: EmailMessage) -> None:
    context = ssl.create_default_context()
    if config.SMTP_PORT == 465:
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context, timeout=20) as smtp:
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(msg)
        return
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as smtp:
        if config.SMTP_STARTTLS:
            smtp.starttls(context=context)
        if config.SMTP_USER:
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
        smtp.send_message(msg)


def _write_outbox(to: str, subject: str, body: str) -> None:
    if not (config.MAIL_OUTBOX_DIR and config.IS_DEV):
        return
    os.makedirs(config.MAIL_OUTBOX_DIR, exist_ok=True)
    name = f"{time.time_ns()}.json"
    with open(os.path.join(config.MAIL_OUTBOX_DIR, name), "w", encoding="utf-8") as f:
        json.dump({"to": to, "subject": subject, "body": body}, f)


def _deliver(to: str, subject: str, body: str) -> None:
    try:
        _write_outbox(to, subject, body)
        if is_configured():
            _send_smtp(_build(to, subject, body))
        elif config.IS_DEV:
            logger.info("Email (not sent, no SMTP configured) to %s: %s\n%s", to, subject, body)
        else:
            logger.warning("SMTP is not configured; an email titled %r was not sent", subject)
    except Exception as exc:  # a mail outage must never break sign-up for everyone
        logger.error("Sending email %r failed: %s", subject, type(exc).__name__)


def send(to: str, subject: str, body: str, background: bool = True) -> None:
    """Send in the background by default, so responses take the same time either way."""
    if background:
        threading.Thread(target=_deliver, args=(to, subject, body), daemon=True).start()
    else:
        _deliver(to, subject, body)


def link(path: str) -> str:
    return config.PUBLIC_BASE_URL.rstrip("/") + path
