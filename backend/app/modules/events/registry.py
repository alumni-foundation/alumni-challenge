"""
The subscriber side. A handler registers itself against an event TYPE
STRING (not an import of the publisher), so publishing code never needs
to know who — if anyone — is listening. `app/main.py` imports this
module's handlers package once at startup so registration actually runs.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]

_HANDLERS: dict[str, list[Handler]] = {}


def on(event_type: str) -> Callable[[Handler], Handler]:
    def _register(fn: Handler) -> Handler:
        _HANDLERS.setdefault(event_type, []).append(fn)
        return fn

    return _register


def handlers_for(event_type: str) -> list[Handler]:
    return list(_HANDLERS.get(event_type, ()))
