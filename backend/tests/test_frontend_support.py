"""Endpoints and fields the web app relies on."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.connections.models import Connection, ConnectionStatus
from tests.test_alumni_privacy import Actor, _grant, _make_actor, _make_school

API = "/api/v1"


async def _profile(client: AsyncClient, actor: Actor, name: str, **extra: object) -> str:
    body = {"full_name": name, "profession": "Engineer", "country": "Kenya", **extra}
    r = await client.post(f"{API}/alumni/profile", json=body, headers=actor.headers)
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def test_my_roles_lists_platform_and_school_roles(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    actor = await _make_actor(client)
    other = await _make_actor(client)
    await _grant(db_session, actor.user_id, Role.SCHOOL_ADMIN, school.id)
    await _grant(db_session, actor.user_id, Role.MODERATOR, None)

    r = await client.get(f"{API}/auth/me/roles", headers=actor.headers)
    assert r.status_code == 200
    got = {(row["role"], row["organization_id"]) for row in r.json()}
    assert got == {("school_admin", str(school.id)), ("moderator", None)}

    # Somebody else's roles never show up, and a plain user gets an empty list.
    assert (await client.get(f"{API}/auth/me/roles", headers=other.headers)).json() == []
    assert (await client.get(f"{API}/auth/me/roles")).status_code == 401


async def test_connection_list_names_the_other_person_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a = await _make_actor(client)
    b = await _make_actor(client)
    c = await _make_actor(client)
    a_pid = await _profile(client, a, "Alice Aardvark", company="Secret Corp")
    b_pid = await _profile(client, b, "Bob Baboon", profile_visibility="private")
    await _profile(client, c, "Carol Camel")

    sent = await client.post(
        f"{API}/connections", json={"addressee_id": str(b.user_id)}, headers=a.headers
    )
    assert sent.status_code == 201

    mine = (await client.get(f"{API}/connections", headers=a.headers)).json()
    assert len(mine) == 1
    assert mine[0]["other_user_id"] == str(b.user_id)
    assert mine[0]["other_profile_id"] == b_pid
    assert mine[0]["other_full_name"] == "Bob Baboon"
    # Nothing beyond the name leaks, even for a private profile.
    assert set(mine[0]) == {
        "id",
        "requester_id",
        "addressee_id",
        "status",
        "created_at",
        "other_user_id",
        "other_profile_id",
        "other_full_name",
    }

    theirs = (await client.get(f"{API}/connections", headers=b.headers)).json()
    assert theirs[0]["other_full_name"] == "Alice Aardvark"
    assert theirs[0]["other_profile_id"] == a_pid

    # A third person sees nothing about this pair.
    assert (await client.get(f"{API}/connections", headers=c.headers)).json() == []


async def test_connection_list_hides_blocked_rows(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a = await _make_actor(client)
    b = await _make_actor(client)
    db_session.add(
        Connection(requester_id=a.user_id, addressee_id=b.user_id, status=ConnectionStatus.BLOCKED)
    )
    await db_session.flush()
    assert (await client.get(f"{API}/connections", headers=a.headers)).json() == []
    assert (await client.get(f"{API}/connections", headers=b.headers)).json() == []


async def test_connection_without_profile_still_lists(client: AsyncClient) -> None:
    a = await _make_actor(client)
    b = await _make_actor(client)  # never creates a profile
    await client.post(
        f"{API}/connections", json={"addressee_id": str(b.user_id)}, headers=a.headers
    )
    row = (await client.get(f"{API}/connections", headers=a.headers)).json()[0]
    assert row["other_profile_id"] is None
    assert row["other_full_name"] is None


async def test_directory_cards_carry_profession_and_country_but_not_private_profiles(
    client: AsyncClient,
) -> None:
    viewer = await _make_actor(client)
    owner = await _make_actor(client)
    hidden = await _make_actor(client)
    await _profile(client, owner, "Dana Dikdik", company="Acme")
    await _profile(client, hidden, "Hidden Person", profile_visibility="private")

    rows = (await client.get(f"{API}/alumni/directory", headers=viewer.headers)).json()
    names = {row["full_name"] for row in rows}
    assert "Dana Dikdik" in names
    assert "Hidden Person" not in names
    dana = next(row for row in rows if row["full_name"] == "Dana Dikdik")
    assert dana["profession"] == "Engineer"
    assert dana["country"] == "Kenya"
    assert dana["company"] == "Acme"
    # Directory stays closed to anonymous callers.
    assert (await client.get(f"{API}/alumni/directory")).status_code == 401


async def test_email_domains_are_listed_for_school_admins_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    other_school = await _make_school(db_session)
    admin = await _make_actor(client)
    outsider = await _make_actor(client)
    await _grant(db_session, admin.user_id, Role.SCHOOL_ADMIN, school.id)

    for domain in ("b.school.ac.ke", "a.school.ac.ke"):
        r = await client.post(
            f"{API}/organizations/{school.id}/email-domains",
            json={"domain": domain},
            headers=admin.headers,
        )
        assert r.status_code == 201

    ok = await client.get(f"{API}/organizations/{school.id}/email-domains", headers=admin.headers)
    assert ok.status_code == 200
    assert [row["domain"] for row in ok.json()] == ["a.school.ac.ke", "b.school.ac.ke"]

    # Not for other schools' admins, ordinary users or anonymous callers.
    assert (
        await client.get(
            f"{API}/organizations/{other_school.id}/email-domains", headers=admin.headers
        )
    ).status_code == 403
    assert (
        await client.get(f"{API}/organizations/{school.id}/email-domains", headers=outsider.headers)
    ).status_code == 403
    assert (await client.get(f"{API}/organizations/{school.id}/email-domains")).status_code == 401
