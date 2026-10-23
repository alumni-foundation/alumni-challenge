"""
Error reporting to Sentry, switched on by SENTRY_DSN and nothing else.

What is sent is deliberately thin. This API handles passwords, login tokens, email addresses
and profile details, and an error report is the easiest place for them to leak. So before
anything leaves the process it is scrubbed: no request bodies, cookies or auth headers, no query
strings, no addresses of visitors, and anything in the text that looks like a login token or an
email address is blanked, wherever it turns up (messages, stack variables, breadcrumbs).
"""

import re
from typing import Any

import sentry_sdk
from sentry_sdk.transport import Transport

from app.core.config import Settings

_TOKEN_IN_URL = re.compile(r"(token=)[^&\s\"']+", re.IGNORECASE)
_JWT = re.compile(r"eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]*")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_BEARER = re.compile(r"(bearer\s+)[\w.\-]+", re.IGNORECASE)

_DROPPED_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-forwarded-for",
    "cf-connecting-ip",
    "x-real-ip",
    "idempotency-key",
}
_DROPPED_REQUEST_KEYS = ("data", "cookies", "query_string", "env")


def _clean_text(text: str) -> str:
    text = _TOKEN_IN_URL.sub(r"\1[Filtered]", text)
    text = _BEARER.sub(r"\1[Filtered]", text)
    text = _JWT.sub("[Filtered token]", text)
    return _EMAIL.sub("[Filtered email]", text)


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_clean(v) for v in value)
    return value


def scrub_event(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    request = event.get("request")
    if isinstance(request, dict):
        for key in _DROPPED_REQUEST_KEYS:
            request.pop(key, None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                k: v for k, v in headers.items() if k.lower() not in _DROPPED_HEADERS
            }
        url = request.get("url")
        if isinstance(url, str):
            request["url"] = url.split("?", 1)[0]
    user = event.get("user")
    if isinstance(user, dict):
        # Keep only the opaque id, which is enough to find an account's errors.
        event["user"] = {"id": user["id"]} if "id" in user else {}
    event.pop("server_name", None)
    cleaned: dict[str, Any] = _clean(event)
    return cleaned


def _before_send(event: Any, hint: Any) -> Any:
    return scrub_event(event, hint)


def _before_breadcrumb(crumb: Any, hint: Any) -> Any:
    return _clean(crumb)


def init_sentry(
    settings: Settings, *, transport: Transport | type[Transport] | None = None
) -> bool:
    """Starts Sentry if a DSN is configured. Returns whether it did. Safe to call twice."""
    if not settings.sentry_dsn:
        sentry_sdk.init(dsn=None)  # also clears anything left over from an earlier call
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.sentry_release,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        before_send=_before_send,
        before_send_transaction=_before_send,
        before_breadcrumb=_before_breadcrumb,
        transport=transport,
    )
    return True
