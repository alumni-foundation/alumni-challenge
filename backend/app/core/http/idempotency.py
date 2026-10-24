"""
Idempotency-Key support — built once, reusable by every mutating
endpoint, per the architecture doc (section 45). No route needs to opt
in: if a client sends an `Idempotency-Key` header on a POST/PUT/PATCH/
DELETE, the response for that key+method+path is cached and replayed on
retry instead of re-running the handler. A request with no such header
is untouched — this never forces the header on any caller.

Same-key requests that arrive while the first is still being handled
get 409, not a second execution — the pattern payments (Phase 6) will
depend on for "duplicate callback can't create a duplicate payment".
"""

import base64
import hashlib
import json

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.rate_limit.limiter import client_ip
from app.infrastructure.redis import get_redis_client

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_RESULT_TTL_SECONDS = 24 * 60 * 60
_LOCK_TTL_SECONDS = 30
_MAX_KEY_LENGTH = 255

# A reply that depends on the moment, not on the request: replaying it later would be wrong
# (the caller has since signed in again, or the rate limit has since reset).
_NEVER_CACHED_STATUSES = frozenset({401, 429})


def caller_scope(authorization: str | None, ip: str | None) -> str:
    """
    Who is asking, as an opaque value. A key only ever replays for the caller that made it:
    without this, anyone who knew or guessed another person's key (and the path) would be
    handed that person's saved reply, login tokens included.
    """
    who = authorization if authorization else f"ip:{ip}"
    return hashlib.sha256(who.encode()).hexdigest()[:32]


def cache_key(method: str, path: str, scope: str, idempotency_key: str) -> str:
    return f"idempotency:{method}:{path}:{scope}:{idempotency_key}"


def _cache_key(request: Request, idempotency_key: str) -> str:
    scope = caller_scope(request.headers.get("Authorization"), client_ip(request))
    return cache_key(request.method, request.url.path, scope, idempotency_key)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        key = request.headers.get("Idempotency-Key")
        if not key or request.method not in _MUTATING_METHODS:
            return await call_next(request)

        if len(key) > _MAX_KEY_LENGTH:
            return JSONResponse(
                {
                    "error": {
                        "code": "idempotency_key_invalid",
                        "message": "The Idempotency-Key is too long.",
                    }
                },
                status_code=422,
            )

        redis = get_redis_client()
        result_key = _cache_key(request, key)
        # The same key with a different body is a different request, not a retry.
        request_sha = hashlib.sha256(await request.body()).hexdigest()

        cached = await redis.get(result_key)
        if cached is not None:
            saved = json.loads(cached)
            if saved.get("request_sha") != request_sha:
                return JSONResponse(
                    {
                        "error": {
                            "code": "idempotency_key_reused",
                            "message": "This Idempotency-Key was used for a different request.",
                        }
                    },
                    status_code=422,
                )
            return Response(
                content=base64.b64decode(saved["body_b64"]),
                status_code=saved["status"],
                headers={**saved["headers"], "Idempotency-Replayed": "true"},
                media_type=saved.get("media_type"),
            )

        lock_key = f"{result_key}:lock"
        acquired = await redis.set(lock_key, "1", nx=True, ex=_LOCK_TTL_SECONDS)
        if not acquired:
            return JSONResponse(
                {
                    "error": {
                        "code": "idempotency_in_progress",
                        "message": (
                            "A request with this Idempotency-Key is already being processed."
                        ),
                    }
                },
                status_code=409,
            )

        try:
            response = await call_next(request)
            body = b"".join([chunk async for chunk in response.body_iterator])  # type: ignore[attr-defined]

            # Only successful and deterministic-client-error responses are cached.
            # A 5xx is treated as transient — the client should be able to retry
            # with the same key and have the handler actually run again.
            if response.status_code < 500 and response.status_code not in _NEVER_CACHED_STATUSES:
                headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() not in ("content-length", "idempotency-replayed")
                }
                await redis.set(
                    result_key,
                    json.dumps(
                        {
                            "request_sha": request_sha,
                            "status": response.status_code,
                            "body_b64": base64.b64encode(body).decode("ascii"),
                            "headers": headers,
                            "media_type": response.media_type,
                        }
                    ),
                    ex=_RESULT_TTL_SECONDS,
                )
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        finally:
            await redis.delete(lock_key)
