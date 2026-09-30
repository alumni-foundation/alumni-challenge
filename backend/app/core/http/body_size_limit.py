from collections.abc import MutableMapping
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

_DEFAULT_MAX_BYTES = 2 * 1024 * 1024  # 2 MiB — no endpoint accepts file uploads yet (Phase 4)

_413_BODY = b'{"error":{"code":"payload_too_large","message":"Request body is too large."}}'


async def _send_413(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": _413_BODY})


class _PayloadTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """
    Pure ASGI, not BaseHTTPMiddleware, and placed outermost in main.py —
    both matter. Two layers of defence:

    1. If the client declares Content-Length up front, reject immediately
       before calling into the app at all. This is the reliable path: it
       runs before anything downstream (including the BaseHTTPMiddleware
       -based security-headers/request-context middleware) ever touches
       the request. BaseHTTPMiddleware relays the request body to the
       app through its own internal task, and an exception raised from a
       wrapped `receive()` does not propagate cleanly back through that
       relay — so a streaming-only check placed behind one of those
       middlewares can silently fail to trigger. Checking Content-Length
       here, before any of that machinery runs, sidesteps the problem.
    2. A streaming byte-counter as defence in depth, for a client that
       lies about or omits Content-Length (chunked transfer). It won't
       always produce a clean 413 given the caveat above, but it stops
       an unbounded body from ever being fully buffered in memory.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int = _DEFAULT_MAX_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = 0
                if declared > self.max_bytes:
                    await _send_413(send)
                    return
                break

        seen = 0
        too_large = False

        async def guarded_receive() -> MutableMapping[str, Any]:
            nonlocal seen, too_large
            message: MutableMapping[str, Any] = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    too_large = True
            if too_large:
                raise _PayloadTooLarge
            return message

        try:
            await self.app(scope, guarded_receive, send)
        except _PayloadTooLarge:
            await _send_413(send)
