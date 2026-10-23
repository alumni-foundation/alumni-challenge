from typing import Protocol


class MailError(Exception):
    """
    Sending failed. The message is deliberately generic (a status code, never the address, the
    subject or the body): it ends up in the retry queue's error column and in logs, and an
    email body can contain a login-capable link.
    """


class Mailer(Protocol):
    """
    Provider-agnostic. Three implementations: the logging fake (the default), SMTP (Mailpit in
    development) and Resend (production). Callers never know which. `html` is an optional
    richer version of `body`; the plain text is always sent.
    """

    async def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None: ...
