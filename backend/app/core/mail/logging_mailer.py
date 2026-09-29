import structlog

logger = structlog.get_logger("mail")


class LoggingMailer:
    """
    The fake provider for local dev and CI: no Resend account exists yet
    (see HANDOFF.md). Logs the full email — including any link/token in
    the body — so Vance can read it straight out of
    `docker compose logs -f api` while testing by hand. Never used in
    production; get_mailer() is the one place that decision is made.
    """

    async def send(self, *, to: str, subject: str, body: str) -> None:
        logger.info("email_sent", to=to, subject=subject, body=body)
