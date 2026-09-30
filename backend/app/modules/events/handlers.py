"""
Handlers register themselves via the `@on(...)` decorator on import — so
this module must actually be imported somewhere for its handlers to take
effect. app/main.py and app/worker.py both import it once at startup.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mail.dependencies import get_mailer
from app.modules.events.registry import on


@on("user.registered")
async def send_welcome_email(db: AsyncSession, payload: dict[str, Any]) -> None:
    """
    The point of routing this through an event instead of calling the
    mailer directly from the register endpoint: the endpoint that
    creates the account doesn't need to know or care that a welcome
    email is one of the things that happens afterward. Add, remove, or
    change what happens on registration here, without touching auth.
    """
    mailer = get_mailer()
    await mailer.send(
        to=payload["email"],
        subject="Welcome to Alumni Challenge",
        body=(
            "Your account is set up. Next, verify your email and finish "
            "your alumni profile so other members can find you."
        ),
    )
