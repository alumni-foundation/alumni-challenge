"""
A limit on every request that changes something, applied to the whole app, so that a new
endpoint cannot be added without one. Routes that need a tighter limit (sign-in, password reset,
uploads) still carry their own, on top of this.

Signed-in callers are counted by account, so one busy office behind one address is not
punished for it; everyone else is counted by address.
"""

import jwt
from fastapi import Request

from app.core.rate_limit.limiter import client_ip, hit

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
SIGNED_IN_WRITES_PER_MINUTE = 120
ANONYMOUS_WRITES_PER_MINUTE = 30


def _caller_key(request: Request) -> tuple[str, int]:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token:
        # Imported here: the limiter is core code and must not depend on the identity module
        # at import time.
        from app.modules.identity.security import decode_access_token

        try:
            return f"user:{decode_access_token(token)}", SIGNED_IN_WRITES_PER_MINUTE
        except (jwt.PyJWTError, ValueError, KeyError):
            pass  # a bad token earns the anonymous limit, not a free pass
    return f"ip:{client_ip(request)}", ANONYMOUS_WRITES_PER_MINUTE


async def limit_writes(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    key, limit = _caller_key(request)
    await hit(f"ratelimit:writes:{key}", limit=limit, window_seconds=60)
