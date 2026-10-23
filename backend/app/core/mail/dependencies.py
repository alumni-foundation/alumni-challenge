from functools import lru_cache

from app.core.config import get_settings
from app.core.mail.base import Mailer
from app.core.mail.logging_mailer import LoggingMailer
from app.core.mail.resend_mailer import ResendMailer
from app.core.mail.smtp_mailer import SmtpMailer


@lru_cache
def _build_mailer() -> Mailer:
    settings = get_settings()
    if settings.mail_backend == "resend":
        # Settings validation has already insisted that these are present.
        assert settings.resend_api_key is not None
        return ResendMailer(
            api_key=settings.resend_api_key.get_secret_value(),
            from_address=settings.mail_from,
        )
    if settings.mail_backend == "smtp":
        assert settings.smtp_host
        return SmtpMailer(
            host=settings.smtp_host,
            port=settings.smtp_port,
            from_address=settings.mail_from,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
            starttls=settings.smtp_starttls,
        )
    # The default. Full content is logged only in development.
    return LoggingMailer(log_content=settings.environment == "development")


def get_mailer() -> Mailer:
    """
    The one place that picks the mail provider (MAIL_BACKEND=logging|smtp|resend).
    Every caller goes through this function, so nothing else changes.
    """
    return _build_mailer()
