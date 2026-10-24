"""
Pointing something at an uploaded file: a profile's avatar, an organization's logo.

Uploading and attaching are separate steps so a picture can be previewed before it is used.
A file can only be attached by someone entitled to it, and the answer is always a plain
"not found" whether the file does not exist, belongs to someone else, or is the wrong kind of
file, so the ids of other people's files can never be probed.

When a file is replaced or removed, the old row is deleted here and the caller deletes the old
bytes after the commit (the returned storage key).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import NotFoundError
from app.modules.alumni.models import AlumniProfile
from app.modules.alumni.service import get_own_profile
from app.modules.events.models import Event
from app.modules.files.models import File, FilePurpose
from app.modules.files.service import remove_file_row
from app.modules.identity.models import User
from app.modules.organizations.models import Organization


async def _claimable(
    db: AsyncSession,
    *,
    file_id: uuid.UUID,
    purpose: FilePurpose,
    owner_user_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
) -> File:
    row = await db.get(File, file_id)
    if row is None or row.purpose != purpose:
        raise NotFoundError("File not found.")
    if owner_user_id is not None and row.owner_user_id != owner_user_id:
        raise NotFoundError("File not found.")
    if organization_id is not None and row.organization_id != organization_id:
        raise NotFoundError("File not found.")
    return row


async def _drop(db: AsyncSession, file_id: uuid.UUID | None) -> str | None:
    if file_id is None:
        return None
    old = await db.get(File, file_id)
    return await remove_file_row(db, row=old) if old is not None else None


async def set_avatar(
    db: AsyncSession, *, user: User, file_id: uuid.UUID
) -> tuple[AlumniProfile, str | None]:
    profile = await get_own_profile(db, user_id=user.id)
    new = await _claimable(db, file_id=file_id, purpose=FilePurpose.AVATAR, owner_user_id=user.id)
    old_id = profile.avatar_file_id
    if old_id == new.id:
        return profile, None
    profile.avatar_file_id = new.id
    await db.flush()
    return profile, await _drop(db, old_id)


async def clear_avatar(db: AsyncSession, *, user: User) -> tuple[AlumniProfile, str | None]:
    profile = await get_own_profile(db, user_id=user.id)
    old_id = profile.avatar_file_id
    profile.avatar_file_id = None
    await db.flush()
    return profile, await _drop(db, old_id)


async def set_logo(
    db: AsyncSession, *, organization: Organization, file_id: uuid.UUID
) -> str | None:
    new = await _claimable(
        db,
        file_id=file_id,
        purpose=FilePurpose.ORGANIZATION_LOGO,
        organization_id=organization.id,
    )
    old_id = organization.logo_file_id
    if old_id == new.id:
        return None
    organization.logo_file_id = new.id
    await db.flush()
    return await _drop(db, old_id)


async def clear_logo(db: AsyncSession, *, organization: Organization) -> str | None:
    old_id = organization.logo_file_id
    organization.logo_file_id = None
    await db.flush()
    return await _drop(db, old_id)


async def set_event_poster(db: AsyncSession, *, event: Event, file_id: uuid.UUID) -> str | None:
    """The poster must have been uploaded for exactly this event's organizer (or, for a platform
    event, by a platform admin with no organization): a poster made for another school is
    simply not found."""
    row = await db.get(File, file_id)
    if (
        row is None
        or row.purpose != FilePurpose.EVENT_POSTER
        or row.organization_id != event.organization_id
    ):
        raise NotFoundError("File not found.")
    old_id = event.poster_file_id
    if old_id == row.id:
        return None
    event.poster_file_id = row.id
    await db.flush()
    return await _drop(db, old_id)


async def clear_event_poster(db: AsyncSession, *, event: Event) -> str | None:
    old_id = event.poster_file_id
    event.poster_file_id = None
    await db.flush()
    return await _drop(db, old_id)
