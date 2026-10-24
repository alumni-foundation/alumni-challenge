"""
The text of the emails we send. Plain text always; a small HTML version for mail clients.
Each function returns (subject, text, html).
"""

import html as html_lib
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailContent:
    subject: str
    text: str
    html: str


def _page(heading: str, intro: str, link: str, button: str, footer: str) -> str:
    safe_link = html_lib.escape(link, quote=True)
    return (
        "<!doctype html><html><body "
        'style="font-family:Arial,Helvetica,sans-serif;background:#f4f4f4;padding:24px">'
        '<div style="max-width:480px;margin:0 auto;background:#fff;border-radius:8px;'
        'padding:24px">'
        f'<h2 style="margin-top:0;color:#0b2b26">{html_lib.escape(heading)}</h2>'
        f"<p>{html_lib.escape(intro)}</p>"
        f'<p><a href="{safe_link}" style="display:inline-block;background:#c9a227;'
        "color:#0b2b26;text-decoration:none;font-weight:bold;padding:12px 20px;"
        f'border-radius:6px">{html_lib.escape(button)}</a></p>'
        '<p style="font-size:12px;color:#555">If the button does not work, copy this address '
        f"into your browser:<br>{safe_link}</p>"
        f'<p style="font-size:12px;color:#555">{html_lib.escape(footer)}</p>'
        "</div></body></html>"
    )


def verification_email(link: str) -> EmailContent:
    intro = "Welcome to Alumni Challenge. Please confirm your email address."
    footer = "This link expires in 24 hours. If you did not sign up, ignore this email."
    return EmailContent(
        subject="Verify your Alumni Challenge email",
        text=f"{intro}\n\nConfirm your email address: {link}\n\n{footer}\n",
        html=_page("Confirm your email", intro, link, "Confirm my email", footer),
    )


def password_reset_email(link: str) -> EmailContent:
    intro = "We received a request to reset your Alumni Challenge password."
    footer = (
        "This link expires in 30 minutes and can only be used once. "
        "If you did not ask for this, you can ignore this email: your password has not changed."
    )
    return EmailContent(
        subject="Reset your Alumni Challenge password",
        text=f"{intro}\n\nReset your password: {link}\n\n{footer}\n",
        html=_page("Reset your password", intro, link, "Reset my password", footer),
    )


def password_changed_email() -> EmailContent:
    text = (
        "The password on your Alumni Challenge account was just changed, and you were signed "
        "out of your other devices.\n\nIf this was not you, reset your password straight away "
        "using the 'Forgot password' link on the sign-in page.\n"
    )
    return EmailContent(
        subject="Your Alumni Challenge password was changed",
        text=text,
        html=(
            '<!doctype html><html><body style="font-family:Arial,sans-serif">'
            f"<p>{html_lib.escape(text).replace(chr(10), '<br>')}</p></body></html>"
        ),
    )


def account_deleted_email() -> EmailContent:
    text = (
        "Your Alumni Challenge account has been deleted and your personal details removed. "
        "You can no longer sign in.\n\nIf you did not ask for this, contact support.\n"
    )
    return EmailContent(
        subject="Your Alumni Challenge account was deleted",
        text=text,
        html=(
            '<!doctype html><html><body style="font-family:Arial,sans-serif">'
            f"<p>{html_lib.escape(text).replace(chr(10), '<br>')}</p></body></html>"
        ),
    )


def _plain_page(text: str) -> str:
    return (
        '<!doctype html><html><body style="font-family:Arial,sans-serif">'
        f"<p>{html_lib.escape(text).replace(chr(10), '<br>')}</p></body></html>"
    )


def booking_confirmed_email(
    *,
    event_title: str,
    when: str,
    reference: str,
    link: str,
    tickets: list[tuple[str, str]],
) -> EmailContent:
    """`tickets` is (holder name, ticket link) for everyone in the booking."""
    lines = "".join(f"  {name}: {ticket_link}\n" for name, ticket_link in tickets)
    text = (
        f"You are booked for {event_title} ({when}).\n\nYour reference is {reference}.\n"
        f"See your booking: {link}\n\nTickets (show the QR code at the door):\n{lines}"
        "\nEach link opens that person's ticket without signing in, so only share it with them.\n"
    )
    return EmailContent(
        subject=f"Booking confirmed: {event_title}", text=text, html=_plain_page(text)
    )


def ticket_email(
    *, event_title: str, when: str, holder_name: str, reference: str, link: str
) -> EmailContent:
    text = (
        f"{holder_name}, you are booked for {event_title} ({when}).\n\n"
        f"Your ticket (show the QR code at the door): {link}\n"
        f"Booking reference: {reference}\n\nThe link opens your ticket without signing in, "
        "so keep it to yourself.\n"
    )
    return EmailContent(subject=f"Your ticket: {event_title}", text=text, html=_plain_page(text))


def event_message_email(*, event_title: str, subject: str, body: str) -> EmailContent:
    text = f"A message from the organizers of {event_title}:\n\n{body}\n"
    return EmailContent(subject=f"{event_title}: {subject}", text=text, html=_plain_page(text))


def booking_cancelled_email(*, event_title: str, reference: str) -> EmailContent:
    text = f"Your booking {reference} for {event_title} was cancelled and your places released.\n"
    return EmailContent(
        subject=f"Booking cancelled: {event_title}", text=text, html=_plain_page(text)
    )


def booking_expired_email(*, event_title: str, reference: str, link: str) -> EmailContent:
    text = (
        f"The places held for your booking {reference} for {event_title} were released because "
        f"payment was not completed in time.\n\nYou can book again while places remain: {link}\n"
    )
    return EmailContent(
        subject=f"Your hold expired: {event_title}", text=text, html=_plain_page(text)
    )


def event_cancelled_email(*, event_title: str, reference: str, reason: str) -> EmailContent:
    text = (
        f"{event_title} has been cancelled by the organizer. Your booking {reference} is "
        f"cancelled.\n\nReason given: {reason}\n\nIf you had paid, the organizer will arrange "
        "your refund.\n"
    )
    return EmailContent(
        subject=f"Event cancelled: {event_title}", text=text, html=_plain_page(text)
    )
