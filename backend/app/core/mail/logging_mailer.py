import hashlib

import structlog

logger = structlog.get_logger("mail")


def mask_address(address: str) -> str:
    """j***@example.com: enough to recognise your own address, not to harvest others."""
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}"


def fingerprint(address: str) -> str:
    return hashlib.sha256(address.lower().encode()).hexdigest()[:12]


class LoggingMailer:
    """
    The fake provider, and the default: nothing is sent anywhere.

    In development (`log_content=True`) it logs the whole email, links and tokens included, so
    you can read it from `docker compose logs api` while testing by hand. Anywhere else it logs
    only that an email would have been sent: a masked address, a fingerprint and the subject.
    Never the body, because the body holds links that log in or reset a password.
    """

    def __init__(self, *, log_content: bool) -> None:
        self._log_content = log_content

    async def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        if self._log_content:
            logger.info("email_sent", to=to, subject=subject, body=body)
        else:
            logger.info(
                "email_not_sent_logging_backend",
                to=mask_address(to),
                to_fingerprint=fingerprint(to),
                subject=subject,
            )
