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
import json

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.infrastructure.redis import get_redis_client

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_RESULT_TTL_SECONDS = 24 * 60 * 60
_LOCK_TTL_SECONDS = 30


def _cache_key(request: Request, idempotency_key: str) -> str:
    return f"idempotency:{request.method}:{request.url.path}:{idempotency_key}"


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        key = request.headers.get("Idempotency-Key")
        if not key or request.method not in _MUTATING_METHODS:
            return await call_next(request)

        redis = get_redis_client()
        cache_key = _cache_key(request, key)

        cached = await redis.get(cache_key)
        if cached is not None:
            saved = json.loads(cached)
            return Response(
                content=base64.b64decode(saved["body_b64"]),
                status_code=saved["status"],
                headers={**saved["headers"], "Idempotency-Replayed": "true"},
                media_type=saved.get("media_type"),
            )

        lock_key = f"{cache_key}:lock"
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
            if response.status_code < 500:
                headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() not in ("content-length", "idempotency-replayed")
                }
                await redis.set(
                    cache_key,
                    json.dumps(
                        {
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
