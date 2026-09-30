"""Security headers, request body size limit, Idempotency-Key, audit log."""

import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.main import app
from tests.test_alumni_privacy import _grant, _make_actor, _make_school

API = "/api/v1"


async def test_responses_carry_security_headers(client: AsyncClient) -> None:
    r = await client.get(f"{API}/health/live" if False else "/health/live")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


async def test_oversized_body_is_rejected_before_reaching_the_handler(
    db_session: AsyncSession,
) -> None:
    from app.infrastructure.database.session import get_db_session

    async def _override():  # type: ignore[no-untyped-def]
        yield db_session

    app.dependency_overrides[get_db_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            huge_email = "a" * (3 * 1024 * 1024)  # 3 MiB, over the 2 MiB cap
            r = await ac.post(
                f"{API}/auth/register",
                json={
                    "email": f"{huge_email}@example.com",
                    "password": "correct-horse-battery",
                    "confirm_18_or_older": True,
                },
            )
            assert r.status_code == 413
    finally:
        app.dependency_overrides.clear()


async def test_ordinary_requests_are_unaffected_by_the_size_limit(client: AsyncClient) -> None:
    actor = await _make_actor(client)
    r = await client.get(f"{API}/auth/me", headers=actor.headers)
    assert r.status_code == 200


async def test_idempotency_key_replays_the_first_response(client: AsyncClient) -> None:
    actor = await _make_actor(client)
    key = str(uuid.uuid4())
    headers = {**actor.headers, "Idempotency-Key": key}

    first = await client.post(
        f"{API}/alumni/profile", json={"full_name": "Idempotent Alice"}, headers=headers
    )
    assert first.status_code == 201
    profile_id = first.json()["id"]

    # Same key, same route: replayed verbatim, not re-executed — a second
    # create would otherwise 409 ("profile already exists").
    second = await client.post(
        f"{API}/alumni/profile", json={"full_name": "Idempotent Alice"}, headers=headers
    )
    assert second.status_code == 201
    assert second.json()["id"] == profile_id
    assert second.headers.get("Idempotency-Replayed") == "true"


async def test_idempotency_key_is_scoped_per_key(client: AsyncClient) -> None:
    actor = await _make_actor(client)
    r1 = await client.post(
        f"{API}/alumni/profile",
        json={"full_name": "First"},
        headers={**actor.headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r1.status_code == 201

    # A second create with a DIFFERENT key for the same actor genuinely
    # re-runs the handler and correctly hits the real "already exists" rule.
    r2 = await client.post(
        f"{API}/alumni/profile",
        json={"full_name": "Second"},
        headers={**actor.headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r2.status_code == 409


async def test_idempotency_key_blocks_a_concurrent_duplicate(client: AsyncClient) -> None:
    from app.infrastructure.redis import get_redis_client

    actor = await _make_actor(client)
    key = str(uuid.uuid4())
    path = f"{API}/alumni/profile"
    # Simulates "first request already in flight" by holding the same lock
    # the middleware itself takes, rather than racing two real requests.
    redis = get_redis_client()
    await redis.set(f"idempotency:POST:{path}:{key}:lock", "1", nx=True, ex=30)

    r = await client.post(
        path, json={"full_name": "Racer"}, headers={**actor.headers, "Idempotency-Key": key}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "idempotency_in_progress"


async def test_requests_without_the_header_are_never_cached(client: AsyncClient) -> None:
    actor = await _make_actor(client)
    r1 = await client.post(
        f"{API}/alumni/profile", json={"full_name": "No Key"}, headers=actor.headers
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"{API}/alumni/profile", json={"full_name": "No Key"}, headers=actor.headers
    )
    assert r2.status_code == 409  # genuinely re-run, correctly rejected


async def test_audit_log_records_membership_grants_and_org_admin_can_read_them(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    platform_admin = await _make_actor(client)
    school_admin = await _make_actor(client)
    target = await _make_actor(client)
    await _grant(db_session, platform_admin.user_id, Role.SUPER_ADMIN, None)
    await _grant(db_session, school_admin.user_id, Role.SCHOOL_ADMIN, school.id)

    grant = await client.post(
        f"{API}/organizations/{school.id}/memberships",
        json={"user_id": str(target.user_id), "role": "event_manager"},
        headers=school_admin.headers,
    )
    assert grant.status_code == 201

    as_school_admin = await client.get(f"{API}/audit-log", headers=school_admin.headers)
    assert as_school_admin.status_code == 200
    actions = {row["action"] for row in as_school_admin.json()}
    assert "membership.assign" in actions
    entry = next(r for r in as_school_admin.json() if r["action"] == "membership.assign")
    assert entry["context"]["organization_id"] == str(school.id)
    assert entry["actor_user_id"] == str(school_admin.user_id)

    as_platform_admin = await client.get(f"{API}/audit-log", headers=platform_admin.headers)
    assert as_platform_admin.status_code == 200
    assert len(as_platform_admin.json()) >= len(as_school_admin.json())


async def test_audit_log_hides_other_schools_entries_from_a_school_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school_a = await _make_school(db_session)
    school_b = await _make_school(db_session)
    admin_a = await _make_actor(client)
    admin_b = await _make_actor(client)
    target = await _make_actor(client)
    await _grant(db_session, admin_a.user_id, Role.SCHOOL_ADMIN, school_a.id)
    await _grant(db_session, admin_b.user_id, Role.SCHOOL_ADMIN, school_b.id)

    await client.post(
        f"{API}/organizations/{school_b.id}/memberships",
        json={"user_id": str(target.user_id), "role": "event_manager"},
        headers=admin_b.headers,
    )

    r = await client.get(f"{API}/audit-log", headers=admin_a.headers)
    for row in r.json():
        assert row.get("context", {}).get("organization_id") != str(school_b.id)


async def test_audit_log_is_forbidden_for_a_plain_alumni(client: AsyncClient) -> None:
    actor = await _make_actor(client)
    r = await client.get(f"{API}/audit-log", headers=actor.headers)
    assert r.status_code == 403


async def test_password_reset_is_audited_and_visible_only_to_platform_admins(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.core.mail.base import Mailer
    from app.core.mail.dependencies import get_mailer

    class _Mailer(Mailer):
        def __init__(self) -> None:
            self.sent: list[dict[str, str]] = []

        async def send(self, *, to: str, subject: str, body: str) -> None:
            self.sent.append({"to": to, "subject": subject, "body": body})

    email = f"reset-{uuid.uuid4().hex[:10]}@example.com"
    await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "correct-horse-battery", "confirm_18_or_older": True},
    )
    platform_admin = await _make_actor(client)
    school = await _make_school(db_session)
    school_admin = await _make_actor(client)
    await _grant(db_session, platform_admin.user_id, Role.ADMIN, None)
    await _grant(db_session, school_admin.user_id, Role.SCHOOL_ADMIN, school.id)

    mailer = _Mailer()
    app.dependency_overrides[get_mailer] = lambda: mailer
    try:
        await client.post(f"{API}/auth/password/forgot", json={"email": email})
        token = mailer.sent[0]["body"].split("token=")[1].split("\n")[0].strip()
        reset = await client.post(
            f"{API}/auth/password/reset",
            json={"token": token, "new_password": "a-new-password-123456"},
        )
        assert reset.status_code == 200
    finally:
        app.dependency_overrides.pop(get_mailer, None)

    as_admin = await client.get(f"{API}/audit-log", headers=platform_admin.headers)
    assert any(row["action"] == "user.password_reset" for row in as_admin.json())

    # No organization context on this entry, so an org-scoped admin never sees it.
    as_school_admin = await client.get(f"{API}/audit-log", headers=school_admin.headers)
    assert not any(row["action"] == "user.password_reset" for row in as_school_admin.json())
