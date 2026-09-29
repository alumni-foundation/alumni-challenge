from app.core.mail.base import Mailer
from app.core.mail.logging_mailer import LoggingMailer


def get_mailer() -> Mailer:
    """
    The one place that picks the mail provider. Point this at a real
    Resend-backed Mailer once SPF/DKIM/DMARC and the Resend account exist
    (HANDOFF.md, Phase 3 leftovers) — every caller goes through this
    function, so nothing else changes.
    """
    return LoggingMailer()
