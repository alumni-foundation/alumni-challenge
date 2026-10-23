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
