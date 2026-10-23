import asyncio
import smtplib
from email.message import EmailMessage

from app.core.mail.base import MailError


class SmtpMailer:
    """
    Plain SMTP. In development this talks to Mailpit (port 1025, no login), which catches
    every email so you can read it in a browser at http://localhost:8025. It can also talk to
    a real relay with a login and STARTTLS.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        from_address: str,
        username: str | None = None,
        password: str | None = None,
        starttls: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._from = from_address
        self._username = username
        self._password = password
        self._starttls = starttls

    async def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        message = EmailMessage()
        message["From"] = self._from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        if html is not None:
            message.add_alternative(html, subtype="html")
        try:
            await asyncio.to_thread(self._deliver, message)
        except (OSError, smtplib.SMTPException):
            # Say what failed, not to whom or what was in it.
            raise MailError("The SMTP server could not take the email.") from None

    def _deliver(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            if self._starttls:
                smtp.starttls()
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.send_message(message)
