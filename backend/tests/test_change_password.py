import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLogEntry
from app.modules.domain_events.service import drain_pending
from app.modules.identity.service import PASSWORD_CHANGE_LIMIT
from tests.conftest import Mailbox

API = "/api/v1"
PASSWORD = "correct-horse-battery"
NEW_PASSWORD = "a-much-better-password-9"


async def _signup(client: AsyncClient) -> str:
    email = f"pw-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": PASSWORD, "confirm_18_or_older": True},
    )
    assert r.status_code == 201, r.text
    return email


async def _login(client: AsyncClient, email: str, password: str = PASSWORD) -> dict[str, Any]:
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _bearer(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _change(
    client: AsyncClient,
    tokens: dict[str, Any],
    *,
    current: str = PASSWORD,
    new: str = NEW_PASSWORD,
    keep: str | None = None,
) -> Any:
    body: dict[str, Any] = {"current_password": current, "new_password": new}
    if keep is not None:
        body["refresh_token"] = keep
    return await client.post(f"{API}/auth/me/password", json=body, headers=_bearer(tokens))


async def _refresh_status(client: AsyncClient, tokens: dict[str, Any]) -> int:
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    return int(r.status_code)


async def test_changing_the_password_signs_out_every_other_device(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = await _signup(client)
    this_device = await _login(client, email)
    phone = await _login(client, email)
    laptop = await _login(client, email)
    bystander = await _login(client, await _signup(client))  # someone else entirely

    r = await _change(client, this_device, keep=this_device["refresh_token"])

    assert r.status_code == 200, r.text
    assert r.json()["sessions_revoked"] == 2
    # Check the kept session first: replaying a revoked refresh token is treated as theft and
    # signs the whole account out (existing behaviour), which would hide the result.
    assert await _refresh_status(client, this_device) == 200  # the one that made the change
    assert await _refresh_status(client, phone) == 401
    assert await _refresh_status(client, laptop) == 401
    assert await _refresh_status(client, bystander) == 200  # other people are untouched


async def test_the_new_password_works_and_the_old_one_does_not(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = await _signup(client)
    tokens = await _login(client, email)

    await _change(client, tokens, keep=tokens["refresh_token"])

    assert (
        await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    ).status_code == 401
    assert (
        await client.post(f"{API}/auth/login", json={"email": email, "password": NEW_PASSWORD})
    ).status_code == 200


async def test_without_a_refresh_token_every_session_is_signed_out(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = await _signup(client)
    here = await _login(client, email)
    elsewhere = await _login(client, email)

    r = await _change(client, here)

    assert r.json()["sessions_revoked"] == 2
    assert await _refresh_status(client, here) == 401
    assert await _refresh_status(client, elsewhere) == 401


async def test_someone_elses_refresh_token_keeps_nothing_and_touches_nobody_else(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    mine = await _login(client, await _signup(client))
    other_email = await _signup(client)
    theirs = await _login(client, other_email)

    r = await _change(client, mine, keep=theirs["refresh_token"])

    assert r.status_code == 200
    assert r.json()["sessions_revoked"] == 1  # my own session, since the token was not mine
    assert await _refresh_status(client, mine) == 401
    assert await _refresh_status(client, theirs) == 200  # untouched


async def test_a_wrong_current_password_changes_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = await _signup(client)
    here = await _login(client, email)
    elsewhere = await _login(client, email)

    r = await _change(client, here, current="not-my-password-123")

    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_current_password"
    assert await _refresh_status(client, elsewhere) == 200
    assert (
        await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    ).status_code == 200


async def test_the_new_password_must_be_different_and_long_enough(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _login(client, await _signup(client))

    same = await _change(client, tokens, new=PASSWORD)
    short = await _change(client, tokens, new="short")

    assert same.status_code == 422
    assert same.json()["error"]["code"] == "password_unchanged"
    assert short.status_code == 422


async def test_changing_a_password_needs_a_login(client: AsyncClient) -> None:
    r = await client.post(
        f"{API}/auth/me/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert r.status_code == 401


async def test_guessing_the_current_password_is_rate_limited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = await _signup(client)
    tokens = await _login(client, email)
    other = await _login(client, await _signup(client))

    for _ in range(PASSWORD_CHANGE_LIMIT):
        assert (await _change(client, tokens, current="wrong-guess-12345")).status_code == 422
    blocked = await _change(client, tokens)  # even the right password is refused now

    assert blocked.status_code == 429
    assert (await _change(client, other)).status_code == 200  # someone else is unaffected


async def test_a_reset_link_sent_before_the_change_stops_working(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    email = await _signup(client)
    tokens = await _login(client, email)
    await client.post(f"{API}/auth/password/forgot", json={"email": email})
    await drain_pending(db_session)
    old_link_token = mailbox.token_from("/reset-password")

    await _change(client, tokens, keep=tokens["refresh_token"])

    replay = await client.post(
        f"{API}/auth/password/reset",
        json={"token": old_link_token, "new_password": "attacker-chosen-password-1"},
    )
    assert replay.status_code == 401


async def test_the_change_is_audited_and_the_owner_is_told_by_email(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    email = await _signup(client)
    tokens = await _login(client, email)
    await drain_pending(db_session)
    mailbox.sent.clear()

    await _change(client, tokens, keep=tokens["refresh_token"])
    assert mailbox.sent == []  # queued, not sent inside the request
    await drain_pending(db_session)

    assert [m["to"] for m in mailbox.sent] == [email]
    assert "password was changed" in (mailbox.sent[0]["subject"] or "")
    assert NEW_PASSWORD not in (mailbox.sent[0]["body"] or "")
    entry = await db_session.scalar(
        select(AuditLogEntry).where(AuditLogEntry.action == "user.password_change")
    )
    assert entry is not None
    assert entry.context == {"sessions_revoked": 0}
    assert NEW_PASSWORD not in str(entry.context)
