import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import PayloadTooLargeError
from app.core.rate_limit import rate_limit
from app.infrastructure.database.session import get_db_session
from app.infrastructure.storage import Storage, get_storage
from app.modules.files import schemas, service
from app.modules.files.models import File as FileRow
from app.modules.files.models import FilePurpose
from app.modules.files.policies import POLICIES
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/files", tags=["files"])


@router.post(
    "",
    response_model=schemas.FileResponse,
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
) -> FileRow:
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
    return row
