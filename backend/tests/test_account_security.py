"""Rate limiting, login lockout, email verification, password reset."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mail.base import Mailer
from app.main import app

API = "/api/v1/auth"
PASSWORD = "correct-horse-battery-staple"


class _CapturingMailer(Mailer):
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, *, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


def _unique_email() -> str:
    return f"sec-{uuid.uuid4().hex[:12]}@example.com"


async def _register_and_login(client: AsyncClient, email: str) -> dict[str, str]:
    r = await client.post(
        f"{API}/register",
        json={"email": email, "password": PASSWORD, "confirm_18_or_older": True},
    )
    assert r.status_code == 201, r.text
    login = await client.post(f"{API}/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_login_locks_out_after_repeated_failures(client: AsyncClient) -> None:
    email = _unique_email()
    await client.post(
        f"{API}/register",
        json={"email": email, "password": PASSWORD, "confirm_18_or_older": True},
    )

    for _ in range(5):
        wrong = await client.post(
            f"{API}/login", json={"email": email, "password": "nope-nope-nope"}
        )
        assert wrong.status_code == 401

    # The CORRECT password is now rejected too — the account is locked, not the password.
    locked = await client.post(f"{API}/login", json={"email": email, "password": PASSWORD})
    assert locked.status_code == 401
    assert "too many" in locked.json()["error"]["message"].lower()


async def test_login_lockout_is_scoped_to_one_email(client: AsyncClient) -> None:
    victim = _unique_email()
    bystander = _unique_email()
    await client.post(
        f"{API}/register",
        json={"email": bystander, "password": PASSWORD, "confirm_18_or_older": True},
    )
    for _ in range(5):
        await client.post(f"{API}/login", json={"email": victim, "password": "nope-nope-nope"})

    ok = await client.post(f"{API}/login", json={"email": bystander, "password": PASSWORD})
    assert ok.status_code == 200


async def test_successful_login_clears_the_failure_count(client: AsyncClient) -> None:
    email = _unique_email()
    await client.post(
        f"{API}/register",
        json={"email": email, "password": PASSWORD, "confirm_18_or_older": True},
    )
    for _ in range(4):  # one under the threshold
        await client.post(f"{API}/login", json={"email": email, "password": "nope-nope-nope"})

    ok = await client.post(f"{API}/login", json={"email": email, "password": PASSWORD})
    assert ok.status_code == 200

    # Counter reset by the success — four more wrong guesses alone don't lock it.
    for _ in range(4):
        await client.post(f"{API}/login", json={"email": email, "password": "nope-nope-nope"})
    still_ok = await client.post(f"{API}/login", json={"email": email, "password": PASSWORD})
    assert still_ok.status_code == 200


async def test_register_is_rate_limited_by_ip(client: AsyncClient) -> None:
    for _ in range(10):
        await client.post(
            f"{API}/register",
            json={"email": _unique_email(), "password": PASSWORD, "confirm_18_or_older": True},
        )
    blocked = await client.post(
        f"{API}/register",
        json={"email": _unique_email(), "password": PASSWORD, "confirm_18_or_older": True},
    )
    assert blocked.status_code == 429


async def test_email_verification_flow(client: AsyncClient, db_session: AsyncSession) -> None:
    email = _unique_email()
    headers = await _register_and_login(client, email)
    mailer = _CapturingMailer()
    from app.core.mail.dependencies import get_mailer

    app.dependency_overrides[get_mailer] = lambda: mailer
    try:
        r = await client.post(f"{API}/email/verify/request", headers=headers)
        assert r.status_code == 200
        assert len(mailer.sent) == 1
        assert mailer.sent[0]["to"] == email
        token = mailer.sent[0]["body"].split("token=")[1].split("\n")[0].strip()

        confirm = await client.post(f"{API}/email/verify/confirm", json={"token": token})
        assert confirm.status_code == 200
        assert confirm.json()["email_verified_at"] is not None

        # Using the same link twice is harmless, not an error.
        again = await client.post(f"{API}/email/verify/confirm", json={"token": token})
        assert again.status_code == 200
    finally:
        app.dependency_overrides.pop(get_mailer, None)


async def test_email_verify_confirm_rejects_garbage_token(client: AsyncClient) -> None:
    r = await client.post(f"{API}/email/verify/confirm", json={"token": "not-a-real-token"})
    assert r.status_code == 401


async def test_password_reset_flow_and_single_use(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = _unique_email()
    await client.post(
        f"{API}/register",
        json={"email": email, "password": PASSWORD, "confirm_18_or_older": True},
    )
    pre_reset_login = await client.post(f"{API}/login", json={"email": email, "password": PASSWORD})
    pre_reset_refresh = pre_reset_login.json()["refresh_token"]
    mailer = _CapturingMailer()
    from app.core.mail.dependencies import get_mailer

    app.dependency_overrides[get_mailer] = lambda: mailer
    try:
        forgot = await client.post(f"{API}/password/forgot", json={"email": email})
        assert forgot.status_code == 202
        token = mailer.sent[0]["body"].split("token=")[1].split("\n")[0].strip()

        new_password = "a-brand-new-password-123"
        reset = await client.post(
            f"{API}/password/reset", json={"token": token, "new_password": new_password}
        )
        assert reset.status_code == 200

        # Old password no longer works, new one does.
        old_login = await client.post(f"{API}/login", json={"email": email, "password": PASSWORD})
        assert old_login.status_code == 401
        new_login = await client.post(
            f"{API}/login", json={"email": email, "password": new_password}
        )
        assert new_login.status_code == 200

        # The token cannot be replayed.
        replay = await client.post(
            f"{API}/password/reset", json={"token": token, "new_password": "another-one-123456"}
        )
        assert replay.status_code == 401

        # Sessions predating the reset are dead: the refresh token from
        # before the reset can no longer mint a new access token, even
        # though that refresh token was never explicitly logged out.
        dead_refresh = await client.post(
            f"{API}/refresh", json={"refresh_token": pre_reset_refresh}
        )
        assert dead_refresh.status_code == 401
    finally:
        app.dependency_overrides.pop(get_mailer, None)


async def test_forgot_password_does_not_reveal_whether_email_exists(client: AsyncClient) -> None:
    from app.core.mail.dependencies import get_mailer

    mailer = _CapturingMailer()
    app.dependency_overrides[get_mailer] = lambda: mailer
    try:
        r = await client.post(f"{API}/password/forgot", json={"email": "nobody-here@example.com"})
        assert r.status_code == 202
        assert mailer.sent == []  # same 202, but nothing actually sent
    finally:
        app.dependency_overrides.pop(get_mailer, None)
