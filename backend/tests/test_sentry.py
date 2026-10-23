import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
import sentry_sdk
from sentry_sdk.transport import Transport

from app.core.config import Settings
from app.core.observability import init_sentry, scrub_event

DSN = "https://publickey@o0.ingest.example.invalid/1"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTYifQ.c2lnbmF0dXJlLXZhbHVl"


class _Capture(Transport):
    """Collects what would have been sent, instead of sending it."""

    sent: list[dict[str, Any]] = []

    def capture_envelope(self, envelope: Any) -> None:
        for item in envelope.items:
            payload = item.payload.json
            if payload is not None:
                _Capture.sent.append(payload)


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "development",
        "secret_key": "k9Zr2vQp7LmX4wTb8NcY1hGfJdS6aUeV0oIxRtMq3Bn",
        "database_url": "postgresql+asyncpg://u:p@localhost:5432/x",
        "redis_url": "redis://localhost:6379/0",
        **overrides,
    }
    return Settings(_env_file=None, **values)


@pytest.fixture(autouse=True)
def _clean_sentry() -> Iterator[None]:
    _Capture.sent = []
    yield
    sentry_sdk.init(dsn=None)


def test_without_a_dsn_nothing_is_started() -> None:
    assert init_sentry(_settings()) is False
    assert not sentry_sdk.get_client().dsn  # nothing can be sent


def test_the_dsn_environment_and_release_come_from_settings() -> None:
    started = init_sentry(
        _settings(
            sentry_dsn=DSN,
            sentry_release="abc1234",
            sentry_traces_sample_rate=0.25,
        ),
        transport=_Capture,
    )

    assert started is True
    options = sentry_sdk.get_client().options
    assert options["environment"] == "development"
    assert options["release"] == "abc1234"
    assert options["traces_sample_rate"] == 0.25
    assert options["send_default_pii"] is False
    assert options["max_request_body_size"] == "never"


def test_an_error_reaches_sentry_with_its_type() -> None:
    init_sentry(_settings(sentry_dsn=DSN), transport=_Capture)

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        sentry_sdk.capture_exception(exc)
    sentry_sdk.flush()

    assert _Capture.sent[0]["exception"]["values"][0]["type"] == "RuntimeError"


def test_tokens_and_addresses_in_an_error_message_never_leave() -> None:
    init_sentry(_settings(sentry_dsn=DSN), transport=_Capture)

    try:
        raise RuntimeError(
            f"bad link https://alumni.example/reset-password?token={TOKEN} "
            f"for person@example.com using Bearer {TOKEN}"
        )
    except RuntimeError as exc:
        sentry_sdk.capture_exception(exc)
    sentry_sdk.flush()

    sent = json.dumps(_Capture.sent)
    assert TOKEN not in sent
    assert "person@example.com" not in sent
    assert "token=[Filtered]" in sent


def test_a_logged_error_is_reported_and_scrubbed_too() -> None:
    init_sentry(_settings(sentry_dsn=DSN), transport=_Capture)

    logging.getLogger("domain_events").error("dead letter for person@example.com")
    sentry_sdk.flush()

    sent = json.dumps(_Capture.sent)
    assert "dead letter" in sent
    assert "person@example.com" not in sent


def test_request_details_are_stripped_from_an_event() -> None:
    event = {
        "request": {
            "url": "https://api.example/api/v1/files/1/content?token=SECRET123",
            "query_string": "token=SECRET123",
            "data": {"password": "hunter2hunter2"},
            "cookies": {"session": "abc"},
            "env": {"REMOTE_ADDR": "203.0.113.9"},
            "headers": {
                "Authorization": f"Bearer {TOKEN}",
                "Cookie": "session=abc",
                "CF-Connecting-IP": "203.0.113.9",
                "X-Forwarded-For": "203.0.113.9",
                "User-Agent": "test-agent",
            },
        },
        "user": {"id": "42", "email": "person@example.com", "ip_address": "203.0.113.9"},
        "server_name": "internal-host",
    }

    clean = scrub_event(event)

    assert clean["request"]["url"] == "https://api.example/api/v1/files/1/content"
    for gone in ("query_string", "data", "cookies", "env"):
        assert gone not in clean["request"]
    assert clean["request"]["headers"] == {"User-Agent": "test-agent"}
    assert clean["user"] == {"id": "42"}
    assert "server_name" not in clean
    text = json.dumps(clean)
    for secret in ("SECRET123", "hunter2", "203.0.113.9", "person@example.com", TOKEN):
        assert secret not in text


def test_breadcrumbs_are_scrubbed_before_they_are_kept() -> None:
    init_sentry(_settings(sentry_dsn=DSN), transport=_Capture)

    sentry_sdk.add_breadcrumb(message=f"GET /x?token={TOKEN} by person@example.com")
    sentry_sdk.capture_message("something happened")
    sentry_sdk.flush()

    sent = json.dumps(_Capture.sent)
    assert TOKEN not in sent and "person@example.com" not in sent


def test_the_dsn_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTRY_DSN", DSN)
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.5")
    monkeypatch.setenv("SENTRY_RELEASE", "v1")

    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        secret_key="k9Zr2vQp7LmX4wTb8NcY1hGfJdS6aUeV0oIxRtMq3Bn",  # type: ignore[arg-type]
        database_url="postgresql+asyncpg://u:p@localhost:5432/x",  # type: ignore[arg-type]
        redis_url="redis://localhost:6379/0",  # type: ignore[arg-type]
    )

    assert (settings.sentry_dsn, settings.sentry_traces_sample_rate, settings.sentry_release) == (
        DSN,
        0.5,
        "v1",
    )


def test_both_processes_start_sentry_from_their_settings() -> None:
    import app.main as main_module
    import app.worker as worker_module

    assert main_module.init_sentry is init_sentry
    assert worker_module.init_sentry is init_sentry
