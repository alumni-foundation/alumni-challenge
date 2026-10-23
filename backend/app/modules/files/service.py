import asyncio
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.permissions.dependencies import get_user_roles
from app.core.permissions.roles import Role
from app.core.rate_limit import hit
from app.infrastructure.storage import Storage
from app.modules.files.images import process_image
from app.modules.files.models import File, FilePurpose
from app.modules.files.policies import MAX_FILES_PER_USER, POLICIES, UPLOADS_PER_HOUR
from app.modules.identity.models import User
from app.modules.organizations.models import Organization, OrganizationStatus

_PLATFORM_ADMINS = {Role.ADMIN, Role.SUPER_ADMIN}
_ORG_ADMINS = {Role.SCHOOL_ADMIN, Role.PARTNER_ADMIN}

# Who may upload what for an organization. Platform admins may always.
_LOGO_UPLOADERS = _PLATFORM_ADMINS | _ORG_ADMINS
_POSTER_UPLOADERS = _PLATFORM_ADMINS | _ORG_ADMINS | {Role.EVENT_MANAGER, Role.SPORTS_MANAGER}


async def _authorize_upload(
    db: AsyncSession, *, user: User, purpose: FilePurpose, organization_id: uuid.UUID | None
) -> None:
    if purpose == FilePurpose.AVATAR:
        if organization_id is not None:
            raise ValidationError("An avatar does not belong to an organization.")
        return

    if organization_id is None:
        # Only a platform admin can upload for "the platform itself" (a poster for an event
        # the platform organizes). A logo always belongs to an organization.
        if purpose == FilePurpose.ORGANIZATION_LOGO:
            raise ValidationError("A logo needs an organization_id.")
        if not await get_user_roles(db, user_id=user.id) & _PLATFORM_ADMINS:
            raise ValidationError("A poster needs an organization_id.")
        return

    org = await db.get(Organization, organization_id)
    if org is None or org.status != OrganizationStatus.ACTIVE:
        # Same answer as for an organization the caller has no rights in, so the response
        # does not tell an outsider which organizations exist.
        raise ForbiddenError("You do not have permission to upload this.")
    allowed = _LOGO_UPLOADERS if purpose == FilePurpose.ORGANIZATION_LOGO else _POSTER_UPLOADERS
    roles = await get_user_roles(db, user_id=user.id, organization_id=organization_id)
    if not roles & allowed:
        raise ForbiddenError("You do not have permission to upload this.")


async def upload_image(
    db: AsyncSession,
    storage: Storage,
    *,
    user: User,
    purpose: FilePurpose,
    organization_id: uuid.UUID | None,
    data: bytes,
) -> File:
    """
    Checks run cheapest first and before any image work: permission, rate limit, the
    per-user file cap. Only then is the picture decoded and rebuilt.
    """
    policy = POLICIES[purpose]
    await _authorize_upload(db, user=user, purpose=purpose, organization_id=organization_id)
    await hit(f"ratelimit:upload:{user.id}", limit=UPLOADS_PER_HOUR, window_seconds=3600)

    owned = await db.scalar(
        select(func.count()).select_from(File).where(File.owner_user_id == user.id)
    )
    if (owned or 0) >= MAX_FILES_PER_USER:
        raise ValidationError(
            f"You have reached the limit of {MAX_FILES_PER_USER} files. Delete one to add another.",
            code="file_limit_reached",
        )

    # Decoding and re-encoding is CPU work: keep it off the event loop.
    processed = await asyncio.to_thread(process_image, data, policy)

    # The key is made here and nowhere else. Nothing the client sent is part of it.
    key = f"{policy.visibility.value}/{purpose.value}/{uuid.uuid4().hex}.{processed.extension}"
    await storage.put(key, processed.data, content_type=processed.content_type)
    try:
        row = File(
            owner_user_id=user.id,
            purpose=purpose,
            organization_id=organization_id,
            storage_key=key,
            mime_type=processed.content_type,
            size_bytes=len(processed.data),
            width=processed.width,
            height=processed.height,
            visibility=policy.visibility,
        )
        db.add(row)
        await db.flush()
    except BaseException:
        # No row will point at these bytes, so do not leave them behind.
        await storage.delete(key)
        raise
    return row


async def get_file(db: AsyncSession, *, file_id: uuid.UUID) -> File:
    row = await db.get(File, file_id)
    if row is None:
        raise NotFoundError("File not found.")
    return row
