import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import ensure_super_admin
from app.core.permissions.roles import Role
from app.modules.identity.models import User
from app.modules.organizations.models import Organization, OrganizationType
from tests.test_alumni_privacy import (
    PASSWORD,
    Actor,
    _grant,
    _make_actor,
    _make_profile,
    _make_school,
)


async def _make_admin(client: AsyncClient, db: AsyncSession) -> Actor:
    admin = await _make_actor(client)
    await _grant(db, admin.user_id, Role.ADMIN, None)
    return admin


async def _verified_alum(
    client: AsyncClient, db: AsyncSession, admin: Actor, school: Organization
) -> tuple[Actor, str]:
    actor = await _make_actor(client)
    pid = await _make_profile(client, actor, school_id=school.id)
    r = await client.patch(
        f"/api/v1/alumni/{pid}/verify", json={"verified": True}, headers=admin.headers
    )
    assert r.status_code == 200
    return actor, pid


# ---------------------------------------------------------------- skills / interests


async def test_skills_are_normalised_and_replaced(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    await _make_profile(client, owner)
    r = await client.put(
        "/api/v1/alumni/profile/skills",
        json={"names": ["  Python ", "python", "FastAPI  Web"]},
        headers=owner.headers,
    )
    assert r.status_code == 200
    assert r.json()["skills"] == ["fastapi web", "python"]

    r = await client.put(
        "/api/v1/alumni/profile/skills", json={"names": ["go"]}, headers=owner.headers
    )
    assert r.json()["skills"] == ["go"]

    r = await client.put(
        "/api/v1/alumni/profile/interests", json={"names": ["golf", "Chess"]}, headers=owner.headers
    )
    assert r.json()["interests"] == ["chess", "golf"]


async def test_skills_limits_and_auth(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    await _make_profile(client, owner)
    too_many = await client.put(
        "/api/v1/alumni/profile/skills",
        json={"names": [f"skill{i}" for i in range(31)]},
        headers=owner.headers,
    )
    assert too_many.status_code == 422
    blank = await client.put(
        "/api/v1/alumni/profile/skills", json={"names": ["   "]}, headers=owner.headers
    )
    assert blank.status_code == 422
    anon = await client.put("/api/v1/alumni/profile/skills", json={"names": ["x"]})
    assert anon.status_code == 401


async def test_skills_follow_profile_visibility(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    pid = await _make_profile(client, owner, visibility="public")
    await client.put(
        "/api/v1/alumni/profile/skills", json={"names": ["python"]}, headers=owner.headers
    )
    seen = await client.get(f"/api/v1/alumni/{pid}")
    assert seen.json()["skills"] == ["python"]


# ---------------------------------------------------------------- directory


async def test_directory_never_lists_private_or_connections_only(client: AsyncClient) -> None:
    viewer = await _make_actor(client)
    ids = {}
    for vis in ("public", "members_only", "connections_only", "private"):
        actor = await _make_actor(client)
        ids[vis] = await _make_profile(client, actor, visibility=vis)
    r = await client.get("/api/v1/alumni/directory?limit=100", headers=viewer.headers)
    assert r.status_code == 200
    listed = {row["id"] for row in r.json()}
    assert ids["public"] in listed and ids["members_only"] in listed
    assert ids["connections_only"] not in listed
    assert ids["private"] not in listed
    assert (await client.get("/api/v1/alumni/directory")).status_code == 401


# ---------------------------------------------------------------- vouching


async def test_three_verified_schoolmates_verify_a_profile(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    admin = await _make_admin(client, db_session)
    target = await _make_actor(client)
    pid = await _make_profile(client, target, school_id=school.id)

    for expected in (1, 2):
        voucher, _ = await _verified_alum(client, db_session, admin, school)
        r = await client.post(f"/api/v1/alumni/{pid}/vouch", headers=voucher.headers)
        assert r.status_code == 200
        assert r.json()["verification_status"] == "unverified"
        assert r.json()["vouch_count"] == expected

    third, _ = await _verified_alum(client, db_session, admin, school)
    r = await client.post(f"/api/v1/alumni/{pid}/vouch", headers=third.headers)
    assert r.json()["verification_status"] == "verified"
    assert r.json()["vouch_count"] == 3


async def test_vouch_restrictions(client: AsyncClient, db_session: AsyncSession) -> None:
    school = await _make_school(db_session)
    other = await _make_school(db_session)
    admin = await _make_admin(client, db_session)
    target = await _make_actor(client)
    pid = await _make_profile(client, target, school_id=school.id)

    # unverified alum cannot vouch
    rookie = await _make_actor(client)
    await _make_profile(client, rookie, school_id=school.id)
    r = await client.post(f"/api/v1/alumni/{pid}/vouch", headers=rookie.headers)
    assert r.status_code == 403

    # verified alum of a DIFFERENT school cannot vouch
    outsider, _ = await _verified_alum(client, db_session, admin, other)
    r = await client.post(f"/api/v1/alumni/{pid}/vouch", headers=outsider.headers)
    assert r.status_code == 403

    # no profile at all
    nobody = await _make_actor(client)
    assert (
        await client.post(f"/api/v1/alumni/{pid}/vouch", headers=nobody.headers)
    ).status_code == 403

    # cannot vouch for yourself; cannot vouch twice
    me, my_pid = await _verified_alum(client, db_session, admin, school)
    assert (
        await client.post(f"/api/v1/alumni/{my_pid}/vouch", headers=me.headers)
    ).status_code == 422
    assert (await client.post(f"/api/v1/alumni/{pid}/vouch", headers=me.headers)).status_code == 200
    assert (await client.post(f"/api/v1/alumni/{pid}/vouch", headers=me.headers)).status_code == 409


async def test_cannot_vouch_for_a_profile_you_cannot_see(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    admin = await _make_admin(client, db_session)
    hidden = await _make_actor(client)
    pid = await _make_profile(client, hidden, visibility="private", school_id=school.id)
    voucher, _ = await _verified_alum(client, db_session, admin, school)
    r = await client.post(f"/api/v1/alumni/{pid}/vouch", headers=voucher.headers)
    assert r.status_code == 404


async def test_vouch_count_hidden_from_anonymous(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    owner = await _make_actor(client)
    pid = await _make_profile(client, owner, visibility="public", school_id=school.id)
    assert (await client.get(f"/api/v1/alumni/{pid}")).json()["vouch_count"] is None


# ---------------------------------------------------------------- school rules


async def test_school_must_be_an_active_school(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _make_actor(client)
    partner = Organization(
        type=OrganizationType.PARTNER, name="P Co", slug=f"p-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(partner)
    await db_session.flush()
    for bad in (str(partner.id), str(uuid.uuid4())):
        r = await client.post(
            "/api/v1/alumni/profile",
            json={"full_name": "X", "school_id": bad},
            headers=owner.headers,
        )
        assert r.status_code == 422


async def test_changing_school_drops_verification(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a = await _make_school(db_session)
    b = await _make_school(db_session)
    admin = await _make_admin(client, db_session)
    alum, pid = await _verified_alum(client, db_session, admin, a)
    r = await client.patch(
        "/api/v1/alumni/profile", json={"school_id": str(b.id)}, headers=alum.headers
    )
    assert r.status_code == 200
    assert r.json()["verification_status"] == "unverified"


async def test_profile_fields_can_be_cleared(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    await _make_profile(client, owner)
    r = await client.patch("/api/v1/alumni/profile", json={"company": None}, headers=owner.headers)
    assert r.json()["company"] is None
    r = await client.patch(
        "/api/v1/alumni/profile", json={"full_name": None}, headers=owner.headers
    )
    assert r.json()["full_name"] == "Test Alum"  # required field is never blanked


# ---------------------------------------------------------------- email-domain verification


async def test_email_domain_registration_rules(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    school_admin = await _make_actor(client)
    await _grant(db_session, school_admin.user_id, Role.SCHOOL_ADMIN, school.id)
    url = f"/api/v1/organizations/{school.id}/email-domains"

    ok = await client.post(
        url, json={"domain": "  Students.School.AC.KE "}, headers=school_admin.headers
    )
    assert ok.status_code == 201
    assert ok.json()["domain"] == "students.school.ac.ke"
    assert (
        await client.post(
            url, json={"domain": "students.school.ac.ke"}, headers=school_admin.headers
        )
    ).status_code == 409
    assert (
        await client.post(url, json={"domain": "gmail.com"}, headers=school_admin.headers)
    ).status_code == 422
    assert (
        await client.post(url, json={"domain": "not a domain"}, headers=school_admin.headers)
    ).status_code == 422
    stranger = await _make_actor(client)
    assert (
        await client.post(url, json={"domain": "x.ac.ke"}, headers=stranger.headers)
    ).status_code == 403


async def test_email_domain_verifies_only_with_a_verified_mailbox(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    admin = await _make_admin(client, db_session)
    r = await client.post(
        f"/api/v1/organizations/{school.id}/email-domains",
        json={"domain": "example.com"},
        headers=admin.headers,
    )
    assert r.status_code == 201

    # Mailbox not verified: the badge must NOT be granted.
    unproven = await _make_actor(client)
    pid = await _make_profile(client, unproven, school_id=school.id)
    r = await client.get(f"/api/v1/alumni/{pid}", headers=unproven.headers)
    assert r.json()["verification_status"] == "unverified"

    # Mailbox verified: granted on profile creation.
    proven = await _make_actor(client)
    user = await db_session.get(User, proven.user_id)
    assert user is not None
    from datetime import UTC, datetime

    user.email_verified_at = datetime.now(UTC)
    await db_session.flush()
    pid2 = await _make_profile(client, proven, school_id=school.id)
    r = await client.get(f"/api/v1/alumni/{pid2}", headers=proven.headers)
    assert r.json()["verification_status"] == "verified"


# ---------------------------------------------------------------- organizations


async def test_only_platform_admins_create_organizations(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _make_admin(client, db_session)
    user = await _make_actor(client)
    body = {"type": "school", "name": "Alliance High", "slug": f"alliance-{uuid.uuid4().hex[:6]}"}

    assert (await client.post("/api/v1/organizations", json=body)).status_code == 401
    assert (
        await client.post("/api/v1/organizations", json=body, headers=user.headers)
    ).status_code == 403
    ok = await client.post("/api/v1/organizations", json=body, headers=admin.headers)
    assert ok.status_code == 201
    assert (
        await client.post("/api/v1/organizations", json=body, headers=admin.headers)
    ).status_code == 409
    bad = {**body, "slug": "Not A Slug"}
    assert (
        await client.post("/api/v1/organizations", json=bad, headers=admin.headers)
    ).status_code == 422

    org_id = ok.json()["id"]
    assert (await client.get(f"/api/v1/organizations/{org_id}")).status_code == 200
    listed = await client.get("/api/v1/organizations?type=school")
    assert org_id in {o["id"] for o in listed.json()}
    assert (await client.get(f"/api/v1/organizations/{uuid.uuid4()}")).status_code == 404


async def test_school_admin_edits_only_their_own_school(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a = await _make_school(db_session)
    b = await _make_school(db_session)
    admin_a = await _make_actor(client)
    await _grant(db_session, admin_a.user_id, Role.SCHOOL_ADMIN, a.id)

    ok = await client.patch(
        f"/api/v1/organizations/{a.id}", json={"description": "New"}, headers=admin_a.headers
    )
    assert ok.status_code == 200 and ok.json()["description"] == "New"
    denied = await client.patch(
        f"/api/v1/organizations/{b.id}", json={"description": "Hack"}, headers=admin_a.headers
    )
    assert denied.status_code == 403
    stranger = await _make_actor(client)
    assert (
        await client.patch(
            f"/api/v1/organizations/{a.id}", json={"description": "x"}, headers=stranger.headers
        )
    ).status_code == 403


async def test_membership_assignment_rules(client: AsyncClient, db_session: AsyncSession) -> None:
    school = await _make_school(db_session)
    other = await _make_school(db_session)
    partner = Organization(
        type=OrganizationType.PARTNER, name="P", slug=f"p-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(partner)
    await db_session.flush()
    admin = await _make_admin(client, db_session)
    target = await _make_actor(client)
    helper = await _make_actor(client)

    def url(org: Organization) -> str:
        return f"/api/v1/organizations/{org.id}/memberships"

    # Only platform admins appoint school admins.
    r = await client.post(
        url(school),
        json={"user_id": str(target.user_id), "role": "school_admin"},
        headers=admin.headers,
    )
    assert r.status_code == 201
    assert (
        await client.post(
            url(school),
            json={"user_id": str(target.user_id), "role": "school_admin"},
            headers=admin.headers,
        )
    ).status_code == 409
    # ...and only for the matching organization type.
    assert (
        await client.post(
            url(partner),
            json={"user_id": str(target.user_id), "role": "school_admin"},
            headers=admin.headers,
        )
    ).status_code == 422

    # A school admin can appoint managers in their own school only, and cannot appoint admins.
    assert (
        await client.post(
            url(school),
            json={"user_id": str(helper.user_id), "role": "event_manager"},
            headers=target.headers,
        )
    ).status_code == 201
    assert (
        await client.post(
            url(other),
            json={"user_id": str(helper.user_id), "role": "event_manager"},
            headers=target.headers,
        )
    ).status_code == 403
    assert (
        await client.post(
            url(school),
            json={"user_id": str(helper.user_id), "role": "school_admin"},
            headers=target.headers,
        )
    ).status_code == 403

    # Roles that are not organization roles, and unknown users.
    assert (
        await client.post(
            url(school),
            json={"user_id": str(helper.user_id), "role": "admin"},
            headers=admin.headers,
        )
    ).status_code == 422
    assert (
        await client.post(
            url(school),
            json={"user_id": str(uuid.uuid4()), "role": "event_manager"},
            headers=admin.headers,
        )
    ).status_code == 404


# ---------------------------------------------------------------- bootstrap admin


async def test_super_admin_bootstrap(client: AsyncClient, db_session: AsyncSession) -> None:
    email = f"root-{uuid.uuid4().hex[:8]}@example.com"
    user, created = await ensure_super_admin(db_session, email=email, password=PASSWORD)
    assert created
    again, created_again = await ensure_super_admin(db_session, email=email.upper(), password=None)
    assert not created_again and again.id == user.id  # idempotent, no duplicate membership

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    body = {"type": "school", "name": "Root School", "slug": f"root-{uuid.uuid4().hex[:6]}"}
    assert (
        await client.post("/api/v1/organizations", json=body, headers=headers)
    ).status_code == 201

    try:
        await ensure_super_admin(db_session, email="new@example.com", password="short")
    except ValueError:
        pass
    else:
        raise AssertionError("short password must be rejected")
