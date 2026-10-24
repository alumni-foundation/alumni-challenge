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

from sqlalchemy import select
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


# ------------------------------------------------------------------------------ bookings


async def _booking_context(
    db: AsyncSession, payload: dict[str, Any]
) -> tuple[Any, Any, User] | None:
    """(booking, event, booker) for a booking event, or None if the booker is not active."""
    from app.modules.bookings.models import Booking
    from app.modules.events.models import Event

    booking = await db.get(Booking, uuid.UUID(payload["booking_id"]))
    if booking is None:
        return None
    user = await db.get(User, booking.booker_user_id)
    event = await db.get(Event, booking.event_id)
    if user is None or event is None or user.status != UserStatus.ACTIVE:
        return None
    return booking, event, user


def _booking_link(booking_id: uuid.UUID) -> str:
    return f"{get_settings().frontend_url}/bookings/{booking_id}"


def _ticket_link(code: str) -> str:
    return f"{get_settings().frontend_url}/tickets/{code}"


@on("booking.confirmed")
async def send_booking_confirmed(db: AsyncSession, payload: dict[str, Any]) -> None:
    """The booker gets the booking and every ticket link. Codes are made now from the signing
    key, never stored. (Named players are emailed by their own event, see send_player_ticket.)"""
    from app.modules.bookings.models import BookingParticipant, Ticket
    from app.modules.bookings.tickets import make_code

    ctx = await _booking_context(db, payload)
    if ctx is None:
        return
    booking, event, user = ctx
    when = event.starts_at.strftime("%A %d %B %Y, %H:%M UTC")
    rows = (
        await db.execute(
            select(BookingParticipant, Ticket)
            .join(Ticket, Ticket.participant_id == BookingParticipant.id)
            .where(BookingParticipant.booking_id == booking.id)
            .order_by(BookingParticipant.position)
        )
    ).all()
    links = [(p.full_name, _ticket_link(make_code(t))) for p, t in rows]
    content = templates.booking_confirmed_email(
        event_title=event.title,
        when=when,
        reference=booking.reference,
        link=_booking_link(booking.id),
        tickets=links,
    )
    await get_mailer().send(
        to=user.email, subject=content.subject, body=content.text, html=content.html
    )


@on("booking.ticket_issued")
async def send_player_ticket(db: AsyncSession, payload: dict[str, Any]) -> None:
    """A named player whose email the booker gave gets their own ticket link. One queued event
    per player, so a failure here is retried alone and never re-sends anyone else's email."""
    from app.modules.bookings.models import BookingParticipant, Ticket
    from app.modules.bookings.tickets import make_code

    ctx = await _booking_context(db, payload)
    person = await db.get(BookingParticipant, uuid.UUID(payload["participant_id"]))
    if ctx is None or person is None or not person.email or person.booking_id != ctx[0].id:
        return
    booking, event, booker = ctx
    if person.email == booker.email:
        return
    ticket = await db.scalar(select(Ticket).where(Ticket.participant_id == person.id))
    if ticket is None:
        return
    content = templates.ticket_email(
        event_title=event.title,
        when=event.starts_at.strftime("%A %d %B %Y, %H:%M UTC"),
        holder_name=person.full_name,
        reference=booking.reference,
        link=_ticket_link(make_code(ticket)),
    )
    await get_mailer().send(
        to=person.email, subject=content.subject, body=content.text, html=content.html
    )


@on("event.message")
async def send_event_message(db: AsyncSession, payload: dict[str, Any]) -> None:
    from app.modules.bookings.models import EventMessage

    ctx = await _booking_context(db, payload)
    message = await db.get(EventMessage, uuid.UUID(payload["message_id"]))
    if ctx is None or message is None:
        return
    _booking, event, user = ctx
    content = templates.event_message_email(
        event_title=event.title, subject=message.subject, body=message.body
    )
    await get_mailer().send(
        to=user.email, subject=content.subject, body=content.text, html=content.html
    )


@on("booking.cancelled")
async def send_booking_cancelled(db: AsyncSession, payload: dict[str, Any]) -> None:
    ctx = await _booking_context(db, payload)
    if ctx is None:
        return
    booking, event, user = ctx
    content = templates.booking_cancelled_email(
        event_title=event.title, reference=booking.reference
    )
    await get_mailer().send(
        to=user.email, subject=content.subject, body=content.text, html=content.html
    )


@on("booking.expired")
async def send_booking_expired(db: AsyncSession, payload: dict[str, Any]) -> None:
    ctx = await _booking_context(db, payload)
    if ctx is None:
        return
    booking, event, user = ctx
    content = templates.booking_expired_email(
        event_title=event.title,
        reference=booking.reference,
        link=f"{get_settings().frontend_url}/events/{event.id}",
    )
    await get_mailer().send(
        to=user.email, subject=content.subject, body=content.text, html=content.html
    )


@on("booking.event_cancelled")
async def send_booking_event_cancelled(db: AsyncSession, payload: dict[str, Any]) -> None:
    ctx = await _booking_context(db, payload)
    if ctx is None:
        return
    booking, event, user = ctx
    content = templates.event_cancelled_email(
        event_title=event.title,
        reference=booking.reference,
        reason=(booking.cancel_reason or "").removeprefix("Event cancelled: "),
    )
    await get_mailer().send(
        to=user.email, subject=content.subject, body=content.text, html=content.html
    )
