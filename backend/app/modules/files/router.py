import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import NotFoundError, PayloadTooLargeError
from app.core.permissions.dependencies import get_user_roles
from app.core.permissions.roles import Role
from app.core.rate_limit import rate_limit
from app.infrastructure.database.session import get_db_session
from app.infrastructure.storage import Storage, StorageError, get_storage
from app.modules.files import schemas, service, urls
from app.modules.files.models import File as FileRow
from app.modules.files.models import FilePurpose, FileVisibility
from app.modules.files.policies import POLICIES
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/files", tags=["files"])


def _with_url(row: FileRow) -> schemas.FileWithUrl:
    base = schemas.FileResponse.model_validate(row)
    return schemas.FileWithUrl(**base.model_dump(), url=urls.url_for(row))


@router.post(
    "",
    response_model=schemas.FileWithUrl,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("upload_ip", limit=100, window_seconds=3600))],
)
async def upload_file(
    purpose: FilePurpose = Form(),
    organization_id: uuid.UUID | None = Form(default=None),
    file: UploadFile = File(),
    db: AsyncSession = Depends(get_db_session),
    storage: Storage = Depends(get_storage),
    current_user: User = Depends(get_current_user),
) -> schemas.FileWithUrl:
    """
    Upload a picture (JPEG, PNG or WebP). This route, and only this route, accepts a body
    larger than 2 MiB (up to 6 MiB; each purpose has its own smaller limit).

    The file name and Content-Type the client sends are ignored: the type is decided from
    the bytes, and the picture is rebuilt from its pixels, which strips location data and
    anything hidden in or after the image.
    """
    policy = POLICIES[purpose]
    # One byte more than allowed is enough to know it is too big, without reading it all.
    data = await file.read(policy.max_bytes + 1)
    if len(data) > policy.max_bytes:
        raise PayloadTooLargeError(
            f"That file is too large. The limit is {policy.max_bytes // (1024 * 1024)} MB."
        )
    row = await service.upload_image(
        db,
        storage,
        user=current_user,
        purpose=purpose,
        organization_id=organization_id,
        data=data,
    )
    try:
        await db.commit()
    except BaseException:
        await storage.delete(row.storage_key)
        raise
    return _with_url(row)


async def _owned_file(db: AsyncSession, user: User, file_id: uuid.UUID) -> FileRow:
    """The owner's file, or a platform admin's view of anyone's. Everyone else: not found."""
    row = await service.get_file_or_none(db, file_id=file_id)
    if row is None:
        raise NotFoundError("File not found.")
    if row.owner_user_id != user.id:
        roles = await get_user_roles(db, user_id=user.id)
        if not roles & {Role.ADMIN, Role.SUPER_ADMIN}:
            raise NotFoundError("File not found.")
    return row


@router.get("/{file_id}", response_model=schemas.FileWithUrl)
async def get_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> schemas.FileWithUrl:
    """Details of one of your own files, with a fresh link to it."""
    return _with_url(await _owned_file(db, current_user, file_id))


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    storage: Storage = Depends(get_storage),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete one of your own files. Anything that was using it (an avatar, a logo) loses it."""
    row = await _owned_file(db, current_user, file_id)
    key = await service.remove_file_row(db, row=row)
    await db.commit()
    await storage.delete(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{file_id}/content", include_in_schema=True)
async def file_content(
    file_id: uuid.UUID,
    token: str | None = Query(default=None, max_length=2000),
    db: AsyncSession = Depends(get_db_session),
    storage: Storage = Depends(get_storage),
) -> Response:
    """
    The picture itself. No login needed, because an <img> tag cannot send one.

    A public file (logo, poster) is open to anyone and cached for good. A private file needs
    the short-lived `token` from a signed link. Every way of being refused (no such file, no
    token, a bad, expired or someone else's token) gives the same plain 404, so this cannot be
    used to find out which files exist.
    """
    row = await service.get_file_or_none(db, file_id=file_id)
    if row is None:
        raise NotFoundError("File not found.")
    if row.visibility == FileVisibility.PRIVATE and (
        token is None or not urls.token_allows(token, file_id)
    ):
        raise NotFoundError("File not found.")
    try:
        data = await storage.get(row.storage_key)
    except StorageError:
        raise NotFoundError("File not found.") from None

    if row.visibility == FileVisibility.PUBLIC:
        cache = "public, max-age=31536000, immutable"
    else:
        cache = f"private, max-age={urls.FILE_URL_LIFETIME_MINUTES * 60}"
    return Response(
        content=data,
        media_type=row.mime_type,
        headers={
            "Cache-Control": cache,
            # The web app is on another origin and loads these into <img> tags.
            "Cross-Origin-Resource-Policy": "cross-origin",
            "Content-Disposition": "inline",
        },
    )
