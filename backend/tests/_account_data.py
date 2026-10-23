"""A person with data in every place we keep any, for the export and deletion tests."""

import uuid
from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.alumni.models import AlumniProfile, PeerVouch
from app.modules.audit.service import record as record_audit
from app.modules.connections.models import Connection, ConnectionStatus
from app.modules.identity.models import User
from app.modules.moderation.models import Report, ReportTargetType
from app.modules.organizations.models import Organization
from tests.test_alumni_privacy import (
    PASSWORD,
    Actor,
    _grant,
    _make_actor,
    _make_profile,
    _make_school,
)
from tests.test_file_upload import API, _encode, _photo, _upload

SECRET_BIO = "I keep bees and my phone number is 0700 000 000"


@dataclass
class Person:
    actor: Actor
    email: str
    profile_id: uuid.UUID
    school: Organization
    avatar_file: dict[str, Any]
    friend: Actor
    friend_profile_id: uuid.UUID
    admin: Actor


async def email_of(db: AsyncSession, actor: Actor) -> str:
    email = await db.scalar(select(User.email).where(User.id == actor.user_id))
    assert email is not None
    return email


async def build_person(client: AsyncClient, db: AsyncSession) -> Person:
    school = await _make_school(db)
    me = await _make_actor(client)
    friend = await _make_actor(client)
    admin = await _make_actor(client)
    await _grant(db, admin.user_id, Role.ADMIN, None)

    profile_id = uuid.UUID(
        await _make_profile(client, me, visibility="public", school_id=school.id)
    )
    friend_profile_id = uuid.UUID(await _make_profile(client, friend, visibility="public"))

    profile = await db.get(AlumniProfile, profile_id)
    assert profile is not None
    profile.bio = SECRET_BIO
    profile.graduation_year = 2012
    profile.country = "Kenya"
    await db.flush()
    await client.put(
        f"{API}/alumni/profile/skills", json={"names": ["beekeeping", "python"]}, headers=me.headers
    )
    await client.put(
        f"{API}/alumni/profile/interests", json={"names": ["golf"]}, headers=me.headers
    )

    uploaded = await _upload(client, me, _encode(_photo(), "JPEG"))
    assert uploaded.status_code == 201, uploaded.text
    avatar = uploaded.json()
    attached = await client.put(
        f"{API}/alumni/profile/avatar", json={"file_id": avatar["id"]}, headers=me.headers
    )
    assert attached.status_code == 200, attached.text

    db.add(
        Connection(
            requester_id=me.user_id, addressee_id=friend.user_id, status=ConnectionStatus.ACCEPTED
        )
    )
    db.add(PeerVouch(vouched_user_id=me.user_id, voucher_user_id=friend.user_id))
    db.add(PeerVouch(vouched_user_id=friend.user_id, voucher_user_id=me.user_id))
    db.add(
        Report(
            reporter_user_id=me.user_id,
            target_type=ReportTargetType.PROFILE,
            target_id=friend_profile_id,
            reason="spam",
        )
    )
    await _grant(db, me.user_id, Role.EVENT_MANAGER, school.id)
    await db.flush()

    # Things in the audit log: something I did, and something done to me by an admin.
    await record_audit(
        db,
        actor_user_id=me.user_id,
        action="test.thing_i_did",
        target_type="user",
        target_id=me.user_id,
    )
    await record_audit(
        db,
        actor_user_id=admin.user_id,
        action="test.thing_done_to_me",
        target_type="user",
        target_id=me.user_id,
        context={"target_user_id": str(me.user_id), "reason": "because"},
    )
    return Person(
        actor=me,
        email=await email_of(db, me),
        profile_id=profile_id,
        school=school,
        avatar_file=avatar,
        friend=friend,
        friend_profile_id=friend_profile_id,
        admin=admin,
    )


__all__ = ["PASSWORD", "Person", "build_person", "email_of"]
