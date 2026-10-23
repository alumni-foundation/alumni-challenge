import uuid

from httpx import AsyncClient
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.infrastructure.storage import LocalDiskStorage
from app.modules.alumni.models import (
    AlumniInterest,
    AlumniProfile,
    AlumniSkill,
    PeerVouch,
    ProfileVisibility,
    VerificationStatus,
)
from app.modules.audit.models import AuditLogEntry
from app.modules.connections.models import Connection
from app.modules.domain_events.models import DomainEvent
from app.modules.domain_events.service import drain_pending
from app.modules.files.models import File
from app.modules.identity import privacy
from app.modules.identity.models import Session, User, UserStatus
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.moderation.models import Report
from tests._account_data import PASSWORD, Person, build_person
from tests.conftest import Mailbox
from tests.test_alumni_privacy import _grant, _make_actor
from tests.test_file_upload import _encode, _photo, _stored_files

API = "/api/v1"


async def _delete(client: AsyncClient, person: Person, password: str = PASSWORD) -> object:
    return await client.post(
        f"{API}/auth/me/delete", json={"password": password}, headers=person.actor.headers
    )


async def _all_text(db: AsyncSession, table: str) -> str:
    rows = (await db.execute(text(f"SELECT row_to_json(t)::text FROM {table} t"))).scalars().all()
    return "\n".join(rows)


# ------------------------------------------------------------------ signing in again


async def test_a_deleted_person_can_no_longer_sign_in_or_use_any_token(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)
    login = await client.post(
        f"{API}/auth/login", json={"email": person.email, "password": PASSWORD}
    )
    refresh = login.json()["refresh_token"]

    r = await _delete(client, person)

    assert r.status_code == 200, r.text  # type: ignore[attr-defined]
    assert (
        await client.post(f"{API}/auth/login", json={"email": person.email, "password": PASSWORD})
    ).status_code == 401
    assert (await client.get(f"{API}/auth/me", headers=person.actor.headers)).status_code == 401
    assert (
        await client.post(f"{API}/auth/refresh", json={"refresh_token": refresh})
    ).status_code == 401


async def test_the_address_can_be_used_to_register_a_new_account(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)
    await _delete(client, person)

    again = await client.post(
        f"{API}/auth/register",
        json={"email": person.email, "password": PASSWORD, "confirm_18_or_older": True},
    )

    assert again.status_code == 201, again.text
    assert again.json()["id"] != str(person.actor.user_id)


# ----------------------------------------------------------------- what is removed


async def test_the_account_and_profile_no_longer_say_who_the_person_was(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)

    await _delete(client, person)

    user = await db_session.get(User, person.actor.user_id)
    assert user is not None
    assert user.status == UserStatus.DELETED
    assert user.email == f"deleted-{person.actor.user_id}@deleted.invalid"
    assert person.email not in user.email
    assert user.email_verified_at is None and user.age_confirmed_at is None
    profile = await db_session.get(AlumniProfile, person.profile_id)
    assert profile is not None
    assert profile.full_name == "Deleted user"
    assert (profile.bio, profile.graduation_year, profile.school_id) == (None, None, None)
    assert (profile.country, profile.profession, profile.company) == (None, None, None)
    assert profile.avatar_file_id is None
    assert profile.profile_visibility == ProfileVisibility.PRIVATE
    assert profile.verification_status == VerificationStatus.UNVERIFIED


async def test_skills_vouches_connections_and_roles_are_removed(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)
    me = person.actor.user_id

    await _delete(client, person)

    count = lambda q: db_session.scalar(select(func.count()).select_from(q))  # noqa: E731
    assert (
        await count(
            select(AlumniSkill).where(AlumniSkill.alumni_profile_id == person.profile_id).subquery()
        )
        == 0
    )
    assert (
        await count(
            select(AlumniInterest)
            .where(AlumniInterest.alumni_profile_id == person.profile_id)
            .subquery()
        )
        == 0
    )
    assert (
        await count(
            select(PeerVouch)
            .where(or_(PeerVouch.vouched_user_id == me, PeerVouch.voucher_user_id == me))
            .subquery()
        )
        == 0
    )
    assert (
        await count(
            select(Connection)
            .where(or_(Connection.requester_id == me, Connection.addressee_id == me))
            .subquery()
        )
        == 0
    )
    statuses = set(
        await db_session.scalars(select(Membership.status).where(Membership.user_id == me))
    )
    assert statuses == {MembershipStatus.REVOKED}


async def test_sessions_are_revoked_and_forget_their_device_and_address(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)
    await client.post(f"{API}/auth/login", json={"email": person.email, "password": PASSWORD})

    await _delete(client, person)

    sessions = list(
        await db_session.scalars(select(Session).where(Session.user_id == person.actor.user_id))
    )
    assert sessions
    assert all(s.revoked_at is not None for s in sessions)
    assert all(s.ip_address is None and s.device_label is None for s in sessions)


async def test_the_avatar_picture_is_deleted_from_storage_and_the_database(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)
    assert len(_stored_files(storage)) == 1

    await _delete(client, person)

    assert _stored_files(storage) == []
    assert await db_session.get(File, uuid.UUID(person.avatar_file["id"])) is None
    assert (await client.get(person.avatar_file["url"])).status_code == 404


async def test_a_logo_the_person_uploaded_for_their_organization_stays(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    from tests.test_file_upload import _school_admin, _upload

    school, admin = await _school_admin(client, db_session)
    logo = (
        await _upload(
            client,
            admin,
            _encode(_photo(), "PNG"),
            purpose="organization_logo",
            organization_id=school.id,
        )
    ).json()
    r = await client.post(
        f"{API}/auth/me/delete", json={"password": PASSWORD}, headers=admin.headers
    )

    assert r.status_code == 200, r.text
    kept = await db_session.get(File, uuid.UUID(logo["id"]))
    assert kept is not None and kept.owner_user_id is None
    assert (await client.get(logo["url"])).status_code == 200


# ------------------------------------------------------------- what is kept, anonymously


async def test_the_audit_log_is_kept_with_the_identity_taken_out(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)
    me = str(person.actor.user_id)
    before = await db_session.scalar(select(func.count()).select_from(AuditLogEntry))

    await _delete(client, person)

    after = await db_session.scalar(select(func.count()).select_from(AuditLogEntry))
    assert after == (before or 0) + 1  # nothing lost, and the deletion itself is recorded
    audit_text = await _all_text(db_session, "audit_log")
    assert me not in audit_text
    assert person.email not in audit_text
    kept = list(
        await db_session.scalars(
            select(AuditLogEntry).where(
                AuditLogEntry.action.in_(("test.thing_i_did", "test.thing_done_to_me"))
            )
        )
    )
    assert {e.action for e in kept} == {"test.thing_i_did", "test.thing_done_to_me"}
    assert all(e.actor_user_id != person.actor.user_id for e in kept)
    done_to_me = next(e for e in kept if e.action == "test.thing_done_to_me")
    assert done_to_me.actor_user_id == person.admin.user_id  # the admin is still named
    assert done_to_me.context == {"reason": "because", "subject_deleted": True}
    deletion = await db_session.scalar(
        select(AuditLogEntry).where(AuditLogEntry.action == "user.delete")
    )
    assert deletion is not None and deletion.actor_user_id is None and deletion.target_id is None


async def test_a_report_the_person_filed_stays_but_names_nobody(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)

    await _delete(client, person)

    report = await db_session.scalar(
        select(Report).where(Report.target_id == person.friend_profile_id)
    )
    assert report is not None and report.reason == "spam"
    reporter = await db_session.get(User, report.reporter_user_id)
    assert reporter is not None and reporter.status == UserStatus.DELETED


# --------------------------------------------------------------- email and the queue


async def test_the_person_is_told_once_and_the_address_is_not_kept_afterwards(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage, mailbox: Mailbox
) -> None:
    person = await build_person(client, db_session)
    await drain_pending(db_session)  # the signup emails
    mailbox.sent.clear()

    await _delete(client, person)
    assert mailbox.sent == []  # queued, not sent inside the request
    await drain_pending(db_session)

    assert [m["to"] for m in mailbox.sent] == [person.email]
    assert "deleted" in (mailbox.sent[0]["subject"] or "")
    events_text = await _all_text(db_session, "domain_events")
    assert person.email not in events_text
    assert str(person.actor.user_id) not in events_text


async def test_emails_still_waiting_to_be_sent_to_the_person_are_dropped(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage, mailbox: Mailbox
) -> None:
    person = await build_person(client, db_session)
    await client.post(f"{API}/auth/password/forgot", json={"email": person.email})

    await _delete(client, person)
    await drain_pending(db_session)

    assert [m["subject"] for m in mailbox.sent if "Reset" in (m["subject"] or "")] == []
    pending = await db_session.scalar(
        select(func.count()).select_from(DomainEvent).where(DomainEvent.status == "pending")
    )
    assert pending == 0


# -------------------------------------------------------------- others, and being found


async def test_nobody_can_find_the_deleted_profile_and_other_people_are_untouched(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)

    await _delete(client, person)

    viewer = person.friend
    assert (
        await client.get(f"{API}/alumni/{person.profile_id}", headers=viewer.headers)
    ).status_code == 404
    listing = await client.get(f"{API}/alumni/directory", headers=viewer.headers)
    assert "Deleted user" not in listing.text
    friend_profile = await client.get(f"{API}/alumni/profile/me", headers=viewer.headers)
    assert friend_profile.status_code == 200
    assert friend_profile.json()["id"] == str(person.friend_profile_id)


# ------------------------------------------------------------------------- the guard rails


async def test_a_wrong_password_deletes_nothing(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)

    r = await _delete(client, person, password="not-my-password-123")

    assert r.status_code == 422  # type: ignore[attr-defined]
    assert r.json()["error"]["code"] == "invalid_current_password"  # type: ignore[attr-defined]
    user = await db_session.get(User, person.actor.user_id)
    assert user is not None and user.status == UserStatus.ACTIVE and user.email == person.email
    assert len(_stored_files(storage)) == 1
    assert (await client.get(f"{API}/auth/me", headers=person.actor.headers)).status_code == 200


async def test_guessing_the_password_to_delete_is_rate_limited(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)

    for _ in range(privacy.DELETE_LIMIT):
        assert (await _delete(client, person, password="wrong-guess-12345")).status_code == 422  # type: ignore[attr-defined]
    blocked = await _delete(client, person)  # even the right password is refused now

    assert blocked.status_code == 429  # type: ignore[attr-defined]


async def test_deleting_needs_a_login(client: AsyncClient) -> None:
    r = await client.post(f"{API}/auth/me/delete", json={"password": PASSWORD})

    assert r.status_code == 401


async def test_the_only_super_admin_cannot_delete_their_account(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    boss = await _make_actor(client)
    await _grant(db_session, boss.user_id, Role.SUPER_ADMIN, None)

    r = await client.post(
        f"{API}/auth/me/delete", json={"password": PASSWORD}, headers=boss.headers
    )

    assert r.status_code == 409
    assert "only super admin" in r.json()["error"]["message"]
    user = await db_session.get(User, boss.user_id)
    assert user is not None and user.status == UserStatus.ACTIVE


async def test_a_super_admin_can_delete_theirs_when_another_remains(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    first = await _make_actor(client)
    second = await _make_actor(client)
    await _grant(db_session, first.user_id, Role.SUPER_ADMIN, None)
    await _grant(db_session, second.user_id, Role.SUPER_ADMIN, None)

    r = await client.post(
        f"{API}/auth/me/delete", json={"password": PASSWORD}, headers=first.headers
    )

    assert r.status_code == 200, r.text
    still = await db_session.scalar(
        select(func.count())
        .select_from(Membership)
        .where(
            Membership.role == Role.SUPER_ADMIN,
            Membership.status == MembershipStatus.ACTIVE,
            Membership.user_id == second.user_id,
        )
    )
    assert still == 1


async def test_a_second_deletion_attempt_is_refused_because_the_login_is_gone(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)
    await _delete(client, person)

    again = await _delete(client, person)

    assert again.status_code == 401  # type: ignore[attr-defined]
