import uuid
from dataclasses import dataclass

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.memberships.models import Membership
from app.modules.organizations.models import Organization, OrganizationType

PASSWORD = "correct-horse-battery"


@dataclass
class Actor:
    user_id: uuid.UUID
    headers: dict[str, str]


async def _make_actor(client: AsyncClient) -> Actor:
    email = f"t-{uuid.uuid4().hex[:12]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "confirm_18_or_older": True},
    )
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    token = login.json()["access_token"]
    return Actor(uuid.UUID(reg.json()["id"]), {"Authorization": f"Bearer {token}"})


async def _make_school(db: AsyncSession) -> Organization:
    slug = f"school-{uuid.uuid4().hex[:8]}"
    org = Organization(type=OrganizationType.SCHOOL, name=slug, slug=slug)
    db.add(org)
    await db.flush()
    return org


async def _grant(
    db: AsyncSession, user_id: uuid.UUID, role: Role, org_id: uuid.UUID | None
) -> None:
    db.add(Membership(user_id=user_id, organization_id=org_id, role=role))
    await db.flush()


async def _make_profile(
    client: AsyncClient,
    actor: Actor,
    *,
    visibility: str = "members_only",
    school_id: uuid.UUID | None = None,
) -> str:
    body: dict[str, object] = {
        "full_name": "Test Alum",
        "company": "Secret Corp",
        "profession": "Engineer",
        "profile_visibility": visibility,
    }
    if school_id:
        body["school_id"] = str(school_id)
    r = await client.post("/api/v1/alumni/profile", json=body, headers=actor.headers)
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def test_default_visibility_is_members_only(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    r = await client.post("/api/v1/alumni/profile", json={"full_name": "X"}, headers=owner.headers)
    assert r.json()["profile_visibility"] == "members_only"


async def test_duplicate_profile_rejected(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    await _make_profile(client, owner)
    r = await client.post("/api/v1/alumni/profile", json={"full_name": "Y"}, headers=owner.headers)
    assert r.status_code == 409


async def test_anonymous_cannot_see_members_only_profile(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    pid = await _make_profile(client, owner, visibility="members_only")
    r = await client.get(f"/api/v1/alumni/{pid}")
    assert r.status_code == 404


async def test_anonymous_sees_public_profile_without_company(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    pid = await _make_profile(client, owner, visibility="public")
    r = await client.get(f"/api/v1/alumni/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["full_name"] == "Test Alum"
    assert body["profession"] == "Engineer"
    assert body["company"] is None  # hidden from anonymous viewers
    assert "email" not in body


async def test_member_sees_company_on_public_profile(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    viewer = await _make_actor(client)
    pid = await _make_profile(client, owner, visibility="public")
    r = await client.get(f"/api/v1/alumni/{pid}", headers=viewer.headers)
    assert r.json()["company"] == "Secret Corp"


async def test_member_sees_members_only_profile(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    viewer = await _make_actor(client)
    pid = await _make_profile(client, owner, visibility="members_only")
    r = await client.get(f"/api/v1/alumni/{pid}", headers=viewer.headers)
    assert r.status_code == 200
    assert r.json()["company"] == "Secret Corp"


async def test_private_profile_hidden_from_members_visible_to_owner(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    viewer = await _make_actor(client)
    pid = await _make_profile(client, owner, visibility="private")
    assert (await client.get(f"/api/v1/alumni/{pid}", headers=viewer.headers)).status_code == 404
    assert (await client.get(f"/api/v1/alumni/{pid}", headers=owner.headers)).status_code == 200


async def test_hidden_and_nonexistent_profiles_look_identical(client: AsyncClient) -> None:
    """A 404 must not reveal whether a private profile exists."""
    owner = await _make_actor(client)
    viewer = await _make_actor(client)
    pid = await _make_profile(client, owner, visibility="private")
    hidden = await client.get(f"/api/v1/alumni/{pid}", headers=viewer.headers)
    missing = await client.get(f"/api/v1/alumni/{uuid.uuid4()}", headers=viewer.headers)
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()


async def test_connections_only_requires_accepted_connection(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    viewer = await _make_actor(client)
    pid = await _make_profile(client, owner, visibility="connections_only")

    assert (await client.get(f"/api/v1/alumni/{pid}", headers=viewer.headers)).status_code == 404

    req = await client.post(
        "/api/v1/connections", json={"addressee_id": str(owner.user_id)}, headers=viewer.headers
    )
    assert req.status_code == 201
    # Pending is not enough.
    assert (await client.get(f"/api/v1/alumni/{pid}", headers=viewer.headers)).status_code == 404

    acc = await client.patch(
        f"/api/v1/connections/{req.json()['id']}/accept", headers=owner.headers
    )
    assert acc.status_code == 200
    assert (await client.get(f"/api/v1/alumni/{pid}", headers=viewer.headers)).status_code == 200


async def test_school_admin_sees_private_profile_of_own_school_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school_a = await _make_school(db_session)
    school_b = await _make_school(db_session)
    owner = await _make_actor(client)
    admin_a = await _make_actor(client)
    admin_b = await _make_actor(client)
    await _grant(db_session, admin_a.user_id, Role.SCHOOL_ADMIN, school_a.id)
    await _grant(db_session, admin_b.user_id, Role.SCHOOL_ADMIN, school_b.id)
    pid = await _make_profile(client, owner, visibility="private", school_id=school_a.id)

    assert (await client.get(f"/api/v1/alumni/{pid}", headers=admin_a.headers)).status_code == 200
    assert (await client.get(f"/api/v1/alumni/{pid}", headers=admin_b.headers)).status_code == 404


async def test_only_own_school_admin_can_verify(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school_a = await _make_school(db_session)
    school_b = await _make_school(db_session)
    owner = await _make_actor(client)
    admin_a = await _make_actor(client)
    admin_b = await _make_actor(client)
    stranger = await _make_actor(client)
    await _grant(db_session, admin_a.user_id, Role.SCHOOL_ADMIN, school_a.id)
    await _grant(db_session, admin_b.user_id, Role.SCHOOL_ADMIN, school_b.id)
    pid = await _make_profile(client, owner, school_id=school_a.id)
    url = f"/api/v1/alumni/{pid}/verify"

    assert (
        await client.patch(url, json={"verified": True}, headers=stranger.headers)
    ).status_code == 403
    assert (
        await client.patch(url, json={"verified": True}, headers=owner.headers)
    ).status_code == 403
    assert (
        await client.patch(url, json={"verified": True}, headers=admin_b.headers)
    ).status_code == 403

    ok = await client.patch(url, json={"verified": True}, headers=admin_a.headers)
    assert ok.status_code == 200
    assert ok.json()["verification_status"] == "verified"


async def test_platform_admin_can_verify_any_school(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    owner = await _make_actor(client)
    admin = await _make_actor(client)
    await _grant(db_session, admin.user_id, Role.ADMIN, None)
    pid = await _make_profile(client, owner, school_id=school.id)
    r = await client.patch(
        f"/api/v1/alumni/{pid}/verify", json={"verified": True}, headers=admin.headers
    )
    assert r.status_code == 200


async def test_connection_rules(client: AsyncClient) -> None:
    a = await _make_actor(client)
    b = await _make_actor(client)

    me = await client.post(
        "/api/v1/connections", json={"addressee_id": str(a.user_id)}, headers=a.headers
    )
    assert me.status_code == 422  # cannot connect to yourself

    first = await client.post(
        "/api/v1/connections", json={"addressee_id": str(b.user_id)}, headers=a.headers
    )
    assert first.status_code == 201
    cid = first.json()["id"]

    dup = await client.post(
        "/api/v1/connections", json={"addressee_id": str(b.user_id)}, headers=a.headers
    )
    assert dup.status_code == 409
    reverse = await client.post(
        "/api/v1/connections", json={"addressee_id": str(a.user_id)}, headers=b.headers
    )
    assert reverse.status_code == 409  # no second row in the opposite direction

    # The requester cannot accept their own request.
    own = await client.patch(f"/api/v1/connections/{cid}/accept", headers=a.headers)
    assert own.status_code == 403

    ok = await client.patch(f"/api/v1/connections/{cid}/accept", headers=b.headers)
    assert ok.status_code == 200
    assert ok.json()["status"] == "accepted"


async def test_stranger_cannot_touch_someone_elses_connection(client: AsyncClient) -> None:
    a = await _make_actor(client)
    b = await _make_actor(client)
    c = await _make_actor(client)
    req = await client.post(
        "/api/v1/connections", json={"addressee_id": str(b.user_id)}, headers=a.headers
    )
    cid = req.json()["id"]
    assert (
        await client.patch(f"/api/v1/connections/{cid}/accept", headers=c.headers)
    ).status_code == 404
    assert (await client.delete(f"/api/v1/connections/{cid}", headers=c.headers)).status_code == 404
