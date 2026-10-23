import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.infrastructure.storage import LocalDiskStorage
from app.modules.files.models import File
from app.modules.organizations.models import Organization
from tests.test_alumni_privacy import Actor, _grant, _make_actor, _make_profile, _make_school
from tests.test_file_upload import (
    API,
    _encode,
    _photo,
    _school_admin,
    _stored_files,
    _upload,
)


async def _upload_avatar(client: AsyncClient, owner: Actor) -> dict[str, Any]:
    r = await _upload(client, owner, _encode(_photo(), "JPEG"))
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


async def _set_avatar(client: AsyncClient, owner: Actor, file_id: str) -> Any:
    return await client.put(
        f"{API}/alumni/profile/avatar", json={"file_id": file_id}, headers=owner.headers
    )


async def _upload_logo(
    client: AsyncClient, admin: Actor, school: Organization, *, purpose: str = "organization_logo"
) -> dict[str, Any]:
    r = await _upload(
        client, admin, _encode(_photo(), "PNG"), purpose=purpose, organization_id=school.id
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


async def _count_files(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(File)) or 0)


# -------------------------------------------------------------------------- avatars


async def test_an_avatar_shows_up_on_the_profile_as_a_working_signed_link(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    await _make_profile(client, owner)
    avatar = await _upload_avatar(client, owner)

    r = await _set_avatar(client, owner, avatar["id"])

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["avatar_file_id"] == avatar["id"]
    assert "?token=" in body["avatar_url"]
    assert (await client.get(body["avatar_url"])).status_code == 200
    # The bare address, without the signature, gives nothing.
    assert (await client.get(f"{API}/files/{avatar['id']}/content")).status_code == 404


async def test_people_who_may_see_a_profile_get_a_link_to_its_avatar(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    viewer = await _make_actor(client)
    public_profile = await _make_profile(client, owner, visibility="public")
    await _set_avatar(client, owner, (await _upload_avatar(client, owner))["id"])

    as_member = await client.get(f"{API}/alumni/{public_profile}", headers=viewer.headers)
    as_anonymous = await client.get(f"{API}/alumni/{public_profile}")

    for response in (as_member, as_anonymous):
        assert response.status_code == 200, response.text
        link = response.json()["avatar_url"]
        assert link is not None
        assert (await client.get(link)).status_code == 200


async def test_nobody_gets_a_link_to_the_avatar_of_a_profile_they_may_not_see(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    stranger = await _make_actor(client)
    members_only = await _make_profile(client, owner, visibility="members_only")
    await _set_avatar(client, owner, (await _upload_avatar(client, owner))["id"])

    hidden_from_anonymous = await client.get(f"{API}/alumni/{members_only}")
    connections_only = await _make_profile(
        client, await _make_actor(client), visibility="connections_only"
    )
    hidden_from_stranger = await client.get(
        f"{API}/alumni/{connections_only}", headers=stranger.headers
    )

    for response in (hidden_from_anonymous, hidden_from_stranger):
        assert response.status_code == 404
        assert "avatar" not in response.text
        assert "token" not in response.text


async def test_a_private_profile_is_never_listed_with_an_avatar_link(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    viewer = await _make_actor(client)
    await _make_profile(client, owner, visibility="private")
    await _set_avatar(client, owner, (await _upload_avatar(client, owner))["id"])

    listing = await client.get(f"{API}/alumni/directory", headers=viewer.headers)

    assert listing.status_code == 200
    assert str(owner.user_id) not in listing.text
    assert "token=" not in listing.text


async def test_nobody_can_use_someone_elses_picture_as_their_avatar(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    thief = await _make_actor(client)
    await _make_profile(client, thief)
    stolen = await _upload_avatar(client, owner)

    taken = await _set_avatar(client, thief, stolen["id"])
    invented = await _set_avatar(client, thief, str(uuid.uuid4()))

    assert taken.status_code == invented.status_code == 404
    assert taken.json() == invented.json()
    profile = await client.get(f"{API}/alumni/profile/me", headers=thief.headers)
    assert profile.json()["avatar_file_id"] is None


async def test_a_logo_cannot_be_used_as_an_avatar(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school, admin = await _school_admin(client, db_session)
    await _make_profile(client, admin)
    logo = await _upload_logo(client, admin, school)

    r = await _set_avatar(client, admin, logo["id"])

    assert r.status_code == 404


async def test_setting_an_avatar_needs_a_profile_and_a_login(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    no_profile = await _make_actor(client)
    avatar = await _upload_avatar(client, no_profile)

    without_profile = await _set_avatar(client, no_profile, avatar["id"])
    anonymous = await client.put(f"{API}/alumni/profile/avatar", json={"file_id": avatar["id"]})

    assert without_profile.status_code == 404
    assert anonymous.status_code == 401


async def test_a_new_avatar_replaces_and_deletes_the_old_one(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    await _make_profile(client, owner)
    first = await _upload_avatar(client, owner)
    await _set_avatar(client, owner, first["id"])
    second = await _upload_avatar(client, owner)

    r = await _set_avatar(client, owner, second["id"])

    assert r.json()["avatar_file_id"] == second["id"]
    assert await db_session.get(File, uuid.UUID(first["id"])) is None
    assert len(_stored_files(storage)) == 1
    assert (await client.get(first["url"])).status_code == 404
    assert (await client.get(r.json()["avatar_url"])).status_code == 200


async def test_choosing_the_same_avatar_again_changes_nothing(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    await _make_profile(client, owner)
    avatar = await _upload_avatar(client, owner)
    await _set_avatar(client, owner, avatar["id"])

    again = await _set_avatar(client, owner, avatar["id"])

    assert again.status_code == 200
    assert again.json()["avatar_file_id"] == avatar["id"]
    assert len(_stored_files(storage)) == 1


async def test_removing_the_avatar_deletes_the_picture(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    await _make_profile(client, owner)
    avatar = await _upload_avatar(client, owner)
    await _set_avatar(client, owner, avatar["id"])

    r = await client.delete(f"{API}/alumni/profile/avatar", headers=owner.headers)

    assert r.status_code == 200
    assert r.json()["avatar_file_id"] is None
    assert r.json()["avatar_url"] is None
    assert await _count_files(db_session) == 0
    assert _stored_files(storage) == []


async def test_deleting_the_file_directly_clears_the_avatar(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    await _make_profile(client, owner)
    avatar = await _upload_avatar(client, owner)
    await _set_avatar(client, owner, avatar["id"])

    assert (
        await client.delete(f"{API}/files/{avatar['id']}", headers=owner.headers)
    ).status_code == 204

    profile = await client.get(f"{API}/alumni/profile/me", headers=owner.headers)
    assert profile.json()["avatar_file_id"] is None
    assert profile.json()["avatar_url"] is None


async def test_the_profile_update_route_cannot_set_the_avatar(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    thief = await _make_actor(client)
    await _make_profile(client, thief)
    stolen = await _upload_avatar(client, await _make_actor(client))

    await client.patch(
        f"{API}/alumni/profile",
        json={"avatar_file_id": stolen["id"]},
        headers=thief.headers,
    )

    profile = await client.get(f"{API}/alumni/profile/me", headers=thief.headers)
    assert profile.json()["avatar_file_id"] is None


# --------------------------------------------------------------------------- logos


async def test_a_school_admin_sets_a_logo_that_anyone_can_load(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school, admin = await _school_admin(client, db_session)
    logo = await _upload_logo(client, admin, school)

    r = await client.put(
        f"{API}/organizations/{school.id}/logo", json={"file_id": logo["id"]}, headers=admin.headers
    )

    assert r.status_code == 200, r.text
    assert r.json()["logo_url"] == f"{API}/files/{logo['id']}/content"
    # Anyone, signed in or not, sees the logo on the organization and can load it.
    public = await client.get(f"{API}/organizations/{school.id}")
    assert public.json()["logo_url"] == r.json()["logo_url"]
    assert "token" not in public.text
    assert (await client.get(public.json()["logo_url"])).status_code == 200


async def test_an_organization_without_a_logo_says_so(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school = await _make_school(db_session)

    r = await client.get(f"{API}/organizations/{school.id}")

    assert r.json()["logo_url"] is None
    assert r.json()["logo_file_id"] is None


async def test_a_school_admin_cannot_change_another_schools_logo(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school_a, admin_a = await _school_admin(client, db_session)
    school_b, admin_b = await _school_admin(client, db_session)
    logo_a = await _upload_logo(client, admin_a, school_a)

    through_b = await client.put(
        f"{API}/organizations/{school_b.id}/logo",
        json={"file_id": logo_a["id"]},
        headers=admin_a.headers,
    )
    fix = await _upload_logo(client, admin_b, school_b)
    removal = await client.delete(
        f"{API}/organizations/{school_b.id}/logo", headers=admin_a.headers
    )

    assert through_b.status_code == 403
    assert removal.status_code == 403
    assert fix["organization_id"] == str(school_b.id)


async def test_a_logo_uploaded_for_one_school_cannot_be_used_by_another(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school_a, admin_a = await _school_admin(client, db_session)
    school_b, admin_b = await _school_admin(client, db_session)
    boss = await _make_actor(client)
    await _grant(db_session, boss.user_id, Role.ADMIN, None)
    logo_for_b = await _upload_logo(client, admin_b, school_b)

    r = await client.put(
        f"{API}/organizations/{school_a.id}/logo",
        json={"file_id": logo_for_b["id"]},
        headers=admin_a.headers,
    )

    assert r.status_code == 404


async def test_an_avatar_or_poster_cannot_be_used_as_a_logo(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school, admin = await _school_admin(client, db_session)
    avatar = await _upload_avatar(client, admin)
    poster = await _upload_logo(client, admin, school, purpose="event_poster")

    for file_id in (avatar["id"], poster["id"]):
        r = await client.put(
            f"{API}/organizations/{school.id}/logo",
            json={"file_id": file_id},
            headers=admin.headers,
        )
        assert r.status_code == 404, r.text


async def test_members_and_managers_cannot_set_a_logo(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school, admin = await _school_admin(client, db_session)
    logo = await _upload_logo(client, admin, school)
    alum = await _make_actor(client)
    manager = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)

    for actor in (alum, manager):
        r = await client.put(
            f"{API}/organizations/{school.id}/logo",
            json={"file_id": logo["id"]},
            headers=actor.headers,
        )
        assert r.status_code == 403, r.text
    assert (
        await client.put(f"{API}/organizations/{school.id}/logo", json={"file_id": logo["id"]})
    ).status_code == 401


async def test_a_new_logo_replaces_and_deletes_the_old_one(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school, admin = await _school_admin(client, db_session)
    first = await _upload_logo(client, admin, school)
    second = await _upload_logo(client, admin, school)
    path = f"{API}/organizations/{school.id}/logo"
    await client.put(path, json={"file_id": first["id"]}, headers=admin.headers)

    r = await client.put(path, json={"file_id": second["id"]}, headers=admin.headers)

    assert r.json()["logo_file_id"] == second["id"]
    assert await db_session.get(File, uuid.UUID(first["id"])) is None
    assert (await client.get(first["url"])).status_code == 404
    assert (await client.get(second["url"])).status_code == 200


async def test_removing_the_logo_deletes_the_picture(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school, admin = await _school_admin(client, db_session)
    logo = await _upload_logo(client, admin, school)
    path = f"{API}/organizations/{school.id}/logo"
    await client.put(path, json={"file_id": logo["id"]}, headers=admin.headers)

    r = await client.delete(path, headers=admin.headers)

    assert r.status_code == 200
    assert r.json()["logo_url"] is None
    assert _stored_files(storage) == []
    assert (await client.get(logo["url"])).status_code == 404
