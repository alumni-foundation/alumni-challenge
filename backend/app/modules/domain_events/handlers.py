"""
Handlers register themselves via the `@on(...)` decorator on import, so this module must
actually be imported somewhere for its handlers to take effect. app/main.py and app/worker.py
both import it once at startup.

Every email the app sends is sent from here, by the worker, never from inside a request. A
request writes an event row in the same transaction as the change that caused it; the worker
picks the row up and sends. If the mail provider is down the event is retried with growing
delays (see service.retry_delay) and, if it keeps failing, parked as FAILED where someone can
see it.

Two rules for everything in this file:

* The event row holds as little as possible: a user id, not an email address or a token. The
  handler looks the user up and makes the token at the moment of sending. That keeps links that
  log people in out of the database, and it means a retry sends a fresh link.
* Nothing here logs a token, a link or a body.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.mail import templates
from app.core.mail.dependencies import get_mailer
from app.modules.domain_events.registry import on
from app.modules.identity.models import User, UserStatus
from app.modules.identity.security import create_purpose_token

EMAIL_VERIFY_EXPIRE_MINUTES = 24 * 60
PASSWORD_RESET_EXPIRE_MINUTES = 30


async def _active_user(db: AsyncSession, payload: dict[str, Any]) -> User | None:
    user = await db.get(User, uuid.UUID(payload["user_id"]))
    if user is None or user.status != UserStatus.ACTIVE:
        return None
    return user


async def _send_verification(db: AsyncSession, payload: dict[str, Any]) -> None:
    user = await _active_user(db, payload)
    if user is None or user.email_verified_at is not None:
        return
    token = create_purpose_token(
        user.id, purpose="email_verify", expire_minutes=EMAIL_VERIFY_EXPIRE_MINUTES
    )
    link = f"{get_settings().frontend_url}/verify-email?token={token}"
    content = templates.verification_email(link)
    await get_mailer().send(
        to=user.email, subject=content.subject, body=content.text, html=content.html
    )


@on("user.registered")
async def send_verification_on_signup(db: AsyncSession, payload: dict[str, Any]) -> None:
    """The welcome email is the verification email: one message, one link to click."""
    await _send_verification(db, payload)


@on("email.verification_requested")
async def send_verification_again(db: AsyncSession, payload: dict[str, Any]) -> None:
    await _send_verification(db, payload)


@on("email.password_reset_requested")
async def send_password_reset(db: AsyncSession, payload: dict[str, Any]) -> None:
    user = await _active_user(db, payload)
    if user is None:
        return
    token = create_purpose_token(
        user.id,
        purpose="password_reset",
        expire_minutes=PASSWORD_RESET_EXPIRE_MINUTES,
        extra={"stamp": str(user.security_stamp)},
    )
    link = f"{get_settings().frontend_url}/reset-password?token={token}"
    content = templates.password_reset_email(link)
    await get_mailer().send(
        to=user.email, subject=content.subject, body=content.text, html=content.html
    )


@on("email.password_changed")
async def send_password_changed_notice(db: AsyncSession, payload: dict[str, Any]) -> None:
    user = await _active_user(db, payload)
    if user is None:
        return
    content = templates.password_changed_email()
    await get_mailer().send(
        to=user.email, subject=content.subject, body=content.text, html=content.html
    )


@on("email.account_deleted")
async def send_account_deleted_notice(db: AsyncSession, payload: dict[str, Any]) -> None:
    """
    The account is already anonymized by the time this runs, so the address travels in the
    event itself. The queue clears the payload as soon as the email has been sent
    (domain_events.service.SCRUB_AFTER_DISPATCH).
    """
    content = templates.account_deleted_email()
    await get_mailer().send(
        to=payload["email"], subject=content.subject, body=content.text, html=content.html
    )
