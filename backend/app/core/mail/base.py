from typing import Protocol


class Mailer(Protocol):
    """
    Provider-agnostic, same pattern as the payments provider interface
    planned for Phase 6. Swap LoggingMailer for a ResendMailer later —
    nothing that calls send() needs to change.
    """

    async def send(self, *, to: str, subject: str, body: str) -> None: ...
