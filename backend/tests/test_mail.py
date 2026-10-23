import json
import os
import smtplib
import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any

import httpx
import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.mail import dependencies as mail_dependencies
from app.core.mail import logging_mailer, templates
from app.core.mail.base import MailError
from app.core.mail.logging_mailer import LoggingMailer, mask_address
from app.core.mail.resend_mailer import ResendMailer
from app.core.mail.smtp_mailer import SmtpMailer
from app.modules.domain_events import service as events_service
from app.modules.domain_events.models import DomainEvent, DomainEventStatus
from app.modules.domain_events.service import MAX_ATTEMPTS, drain_pending
from tests.conftest import Mailbox

settings = get_settings()
API = "/api/v1"
SECRET_LINK = "https://alumni.example/reset-password?token=SECRET-TOKEN-VALUE"


# --------------------------------------------------------------------- the logging fake


class _FakeLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def info(self, event: str, **kwargs: Any) -> None:
        self.events.append((event, kwargs))


@pytest.fixture
def fake_logger(monkeypatch: pytest.MonkeyPatch) -> _FakeLogger:
    fake = _FakeLogger()
    monkeypatch.setattr(logging_mailer, "logger", fake)
    return fake


async def test_in_development_the_logging_mailer_shows_the_whole_email(
    fake_logger: _FakeLogger,
) -> None:
    await LoggingMailer(log_content=True).send(
        to="person@example.com", subject="Hello", body=f"Click {SECRET_LINK}"
    )

    assert "SECRET-TOKEN-VALUE" in json.dumps(fake_logger.events)


async def test_outside_development_the_logging_mailer_never_logs_the_body_or_the_address(
    fake_logger: _FakeLogger,
) -> None:
    await LoggingMailer(log_content=False).send(
        to="person@example.com",
        subject="Hello",
        body=f"Click {SECRET_LINK}",
        html=f'<a href="{SECRET_LINK}">go</a>',
    )

    logged = json.dumps(fake_logger.events)
    assert "SECRET-TOKEN-VALUE" not in logged
    assert "token=" not in logged
    assert "person@example.com" not in logged
    assert "p***@example.com" in logged
    assert "Hello" in logged  # the subject is fine to log


def test_masking_keeps_only_the_first_letter_and_the_domain() -> None:
    assert mask_address("jane.doe@school.ac.ke") == "j***@school.ac.ke"


# ------------------------------------------------------------------------------ Resend


def _resend(handler: Any) -> ResendMailer:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ResendMailer(
        api_key="re_test_key", from_address="Alumni <hello@alumni.example>", client=client
    )


async def test_resend_gets_the_email_exactly_as_its_api_expects() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "abc"})

    await _resend(handler).send(
        to="person@example.com", subject="Subject", body="plain", html="<b>rich</b>"
    )

    request = seen[0]
    assert str(request.url) == "https://api.resend.com/emails"
    assert request.headers["authorization"] == "Bearer re_test_key"
    assert json.loads(request.content) == {
        "from": "Alumni <hello@alumni.example>",
        "to": ["person@example.com"],
        "subject": "Subject",
        "text": "plain",
        "html": "<b>rich</b>",
    }


async def test_a_refused_email_raises_an_error_that_leaks_nothing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # A provider error body that echoes the message back, as some do.
        return httpx.Response(422, text=f"invalid email body: {SECRET_LINK} to person@example.com")

    with pytest.raises(MailError) as caught:
        await _resend(handler).send(
            to="person@example.com", subject="S", body=f"Click {SECRET_LINK}"
        )

    text = str(caught.value)
    assert "422" in text
    assert "SECRET-TOKEN-VALUE" not in text
    assert "person@example.com" not in text


async def test_an_unreachable_provider_is_a_mail_error_not_a_crash() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot connect while sending {SECRET_LINK}")

    with pytest.raises(MailError) as caught:
        await _resend(handler).send(to="person@example.com", subject="S", body="b")

    assert "SECRET-TOKEN-VALUE" not in str(caught.value)


# ------------------------------------------------------------------------------- SMTP


class _FakeSmtp:
    sent: list[EmailMessage] = []
    fail = False
    logins: list[tuple[str, str]] = []
    tls = 0

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.target = (host, port)

    def __enter__(self) -> "_FakeSmtp":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def starttls(self) -> None:
        _FakeSmtp.tls += 1

    def login(self, user: str, password: str) -> None:
        _FakeSmtp.logins.append((user, password))

    def send_message(self, message: EmailMessage) -> None:
        if _FakeSmtp.fail:
            raise smtplib.SMTPRecipientsRefused({"person@example.com": (550, b"no")})
        _FakeSmtp.sent.append(message)


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[_FakeSmtp]:
    _FakeSmtp.sent, _FakeSmtp.logins, _FakeSmtp.fail, _FakeSmtp.tls = [], [], False, 0
    monkeypatch.setattr(smtplib, "SMTP", _FakeSmtp)
    return _FakeSmtp


async def test_smtp_sends_a_text_and_html_email(fake_smtp: type[_FakeSmtp]) -> None:
    mailer = SmtpMailer(host="mailpit", port=1025, from_address="Alumni <no-reply@alumni.local>")

    await mailer.send(to="person@example.com", subject="Hi", body="plain", html="<b>rich</b>")

    message = fake_smtp.sent[0]
    assert (message["From"], message["To"], message["Subject"]) == (
        "Alumni <no-reply@alumni.local>",
        "person@example.com",
        "Hi",
    )
    assert message.get_body(preferencelist=("plain",)).get_content().strip() == "plain"  # type: ignore[union-attr]
    assert "<b>rich</b>" in message.get_body(preferencelist=("html",)).get_content()  # type: ignore[union-attr]
    assert fake_smtp.logins == [] and fake_smtp.tls == 0


async def test_smtp_logs_in_and_upgrades_the_connection_when_asked(
    fake_smtp: type[_FakeSmtp],
) -> None:
    mailer = SmtpMailer(
        host="smtp.example",
        port=587,
        from_address="a@b.c",
        username="user",
        password="pw",
        starttls=True,
    )

    await mailer.send(to="person@example.com", subject="Hi", body="plain")

    assert fake_smtp.tls == 1
    assert fake_smtp.logins == [("user", "pw")]


async def test_an_smtp_refusal_is_a_mail_error_that_leaks_nothing(
    fake_smtp: type[_FakeSmtp],
) -> None:
    fake_smtp.fail = True
    mailer = SmtpMailer(host="mailpit", port=1025, from_address="a@b.c")

    with pytest.raises(MailError) as caught:
        await mailer.send(to="person@example.com", subject="S", body=f"Click {SECRET_LINK}")

    assert "person@example.com" not in str(caught.value)
    assert "SECRET-TOKEN-VALUE" not in str(caught.value)


async def test_a_real_email_reaches_the_mail_catcher() -> None:
    """End to end over a real SMTP connection, when Mailpit is running (compose, and CI)."""
    host, api = os.environ.get("TEST_SMTP_HOST"), os.environ.get("TEST_MAILPIT_API")
    if not host or not api:
        if os.environ.get("CI"):
            pytest.fail("TEST_SMTP_HOST and TEST_MAILPIT_API must be set in CI")
        pytest.skip("no Mailpit configured (TEST_SMTP_HOST, TEST_MAILPIT_API)")
    recipient = f"catch-{uuid.uuid4().hex[:10]}@example.com"
    mailer = SmtpMailer(host=host, port=1025, from_address="Alumni <no-reply@alumni.local>")

    await mailer.send(
        to=recipient, subject="Catch me", body="plain text body", html="<p>html body</p>"
    )

    async with httpx.AsyncClient() as client:
        found = await client.get(f"{api}/api/v1/search", params={"query": f"to:{recipient}"})
    messages = found.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["Subject"] == "Catch me"


# --------------------------------------------------------------- choosing the provider


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "development",
        "secret_key": "k9Zr2vQp7LmX4wTb8NcY1hGfJdS6aUeV0oIxRtMq3Bn",
        "database_url": "postgresql+asyncpg://u:p@localhost:5432/x",
        "redis_url": "redis://localhost:6379/0",
        **overrides,
    }
    return Settings(_env_file=None, **values)


def _built(monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> object:
    monkeypatch.setattr(mail_dependencies, "get_settings", lambda: _settings(**overrides))
    mail_dependencies._build_mailer.cache_clear()
    try:
        return mail_dependencies.get_mailer()
    finally:
        mail_dependencies._build_mailer.cache_clear()


def test_the_default_provider_is_the_logging_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(_built(monkeypatch), LoggingMailer)
    assert _settings().mail_backend == "logging"


def test_each_setting_picks_its_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(_built(monkeypatch, mail_backend="smtp", smtp_host="mailpit"), SmtpMailer)
    assert isinstance(
        _built(monkeypatch, mail_backend="resend", resend_api_key="re_x"), ResendMailer
    )


def test_the_logging_fake_shows_content_only_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev = _built(monkeypatch)
    staging = _built(
        monkeypatch,
        environment="staging",
        storage_backend="r2",
        storage_endpoint_url="https://x.invalid",
        storage_access_key="a",
        storage_secret_key="s",
        storage_bucket_name="b",
    )

    assert isinstance(dev, LoggingMailer) and dev._log_content is True
    assert isinstance(staging, LoggingMailer) and staging._log_content is False


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"mail_backend": "resend"}, "RESEND_API_KEY"),
        ({"mail_backend": "smtp", "smtp_host": None}, "SMTP_HOST"),
    ],
)
def test_a_provider_needs_its_settings(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _settings(**overrides)


_R2 = {
    "storage_backend": "r2",
    "storage_endpoint_url": "https://x.invalid",
    "storage_access_key": "a",
    "storage_secret_key": "s",
    "storage_bucket_name": "b",
}


def test_production_must_really_send_email() -> None:
    with pytest.raises(ValueError, match="MAIL_BACKEND=resend"):
        _settings(environment="production", frontend_url="https://alumni.example", **_R2)


def test_production_links_must_be_https() -> None:
    with pytest.raises(ValueError, match="https://"):
        _settings(
            environment="production",
            mail_backend="resend",
            resend_api_key="re_x",
            frontend_url="http://alumni.example",
            **_R2,
        )


def test_a_complete_production_mail_setup_is_accepted() -> None:
    ok = _settings(
        environment="production",
        mail_backend="resend",
        resend_api_key="re_x",
        frontend_url="https://alumni.example",
        **_R2,
    )

    assert ok.mail_backend == "resend"


# ------------------------------------------------------------------- the emails themselves


async def test_the_links_in_the_emails_have_exactly_the_agreed_shape(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    email = f"links-{uuid.uuid4().hex[:10]}@example.com"
    registered = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "correct-horse-battery", "confirm_18_or_older": True},
    )
    await client.post(f"{API}/auth/password/forgot", json={"email": email})
    await drain_pending(db_session)

    verify = mailbox.links("/verify-email")[0]
    reset = mailbox.links("/reset-password")[0]

    base = settings.frontend_url
    assert verify.startswith(f"{base}/verify-email?token=")
    assert reset.startswith(f"{base}/reset-password?token=")
    verify_claims = jwt.decode(verify.split("token=")[1], options={"verify_signature": False})
    reset_claims = jwt.decode(reset.split("token=")[1], options={"verify_signature": False})
    assert verify_claims["type"] == "email_verify"
    assert verify_claims["sub"] == registered.json()["id"]
    assert reset_claims["type"] == "password_reset"
    # The verification link is valid for a day, the reset link for half an hour.
    assert verify_claims["exp"] - verify_claims["iat"] == 24 * 3600
    assert reset_claims["exp"] - reset_claims["iat"] == 30 * 60


def test_the_html_version_carries_the_same_link_and_escapes_it() -> None:
    link = 'https://alumni.example/verify-email?token=abc&x="><script>'

    content = templates.verification_email(link)

    assert link in content.text
    assert "<script>" not in content.html
    assert "&amp;x=&quot;&gt;&lt;script&gt;" in content.html


async def test_nobody_is_emailed_for_an_unknown_or_suspended_account(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    from app.modules.identity.models import User, UserStatus

    email = f"gone-{uuid.uuid4().hex[:10]}@example.com"
    registered = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "correct-horse-battery", "confirm_18_or_older": True},
    )
    user = await db_session.get(User, uuid.UUID(registered.json()["id"]))
    assert user is not None
    user.status = UserStatus.SUSPENDED
    await db_session.flush()

    await client.post(f"{API}/auth/password/forgot", json={"email": email})
    await drain_pending(db_session)

    assert mailbox.sent == []


async def test_an_already_verified_person_is_not_sent_another_verification(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    from app.modules.identity.models import User

    registered = await client.post(
        f"{API}/auth/register",
        json={
            "email": f"done-{uuid.uuid4().hex[:10]}@example.com",
            "password": "correct-horse-battery",
            "confirm_18_or_older": True,
        },
    )
    user = await db_session.get(User, uuid.UUID(registered.json()["id"]))
    assert user is not None
    user.email_verified_at = datetime.now(UTC)
    await db_session.flush()

    await drain_pending(db_session)

    assert mailbox.sent == []


# ---------------------------------------------------------------- the queue and retries


class _FlakyMailer:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.delivered: list[str] = []

    async def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        if self.failures > 0:
            self.failures -= 1
            raise MailError("Resend refused the email (HTTP 503).")
        self.delivered.append(to)


async def _register(client: AsyncClient) -> str:
    email = f"queue-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "correct-horse-battery", "confirm_18_or_older": True},
    )
    assert r.status_code == 201
    return email


async def test_an_outage_at_the_provider_is_ridden_out_by_retrying_later(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.modules.domain_events.handlers as handlers_module

    flaky = _FlakyMailer(failures=2)
    monkeypatch.setattr(handlers_module, "get_mailer", lambda: flaky)
    email = await _register(client)
    event = await db_session.scalar(
        select(DomainEvent).where(DomainEvent.event_type == "user.registered")
    )
    assert event is not None

    for _ in range(3):
        await drain_pending(db_session)
        event.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)  # the wait is over
        await db_session.flush()

    assert flaky.delivered == [email]  # delivered once, after two failures
    assert event.status == DomainEventStatus.DISPATCHED
    assert event.attempts == 2


async def test_a_provider_that_never_recovers_parks_the_email_with_a_clean_error(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.modules.domain_events.handlers as handlers_module

    flaky = _FlakyMailer(failures=1000)
    monkeypatch.setattr(handlers_module, "get_mailer", lambda: flaky)
    monkeypatch.setattr(events_service, "retry_delay", lambda attempts: timedelta(0))
    email = await _register(client)

    for _ in range(MAX_ATTEMPTS + 2):
        await drain_pending(db_session)

    event = await db_session.scalar(
        select(DomainEvent).where(DomainEvent.event_type == "user.registered")
    )
    assert event is not None
    assert event.status == DomainEventStatus.FAILED
    assert event.attempts == MAX_ATTEMPTS
    assert event.last_error == "Resend refused the email (HTTP 503)."
    assert email not in (event.last_error or "")
    assert "token=" not in (event.last_error or "")
    assert flaky.delivered == []


async def test_the_queue_row_never_holds_an_address_or_a_link(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    email = await _register(client)
    await client.post(f"{API}/auth/password/forgot", json={"email": email})
    await drain_pending(db_session)

    rows = list(await db_session.scalars(select(DomainEvent)))
    stored = json.dumps([r.payload for r in rows])

    assert rows
    assert email not in stored
    assert "token" not in stored
    assert "http" not in stored


async def test_email_is_not_sent_from_inside_the_request(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    await _register(client)

    assert mailbox.sent == []
