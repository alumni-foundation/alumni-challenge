import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db_session
from app.infrastructure.storage import Storage, StorageError, get_storage
from app.modules.identity import privacy, schemas, service
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/auth/me", tags=["account"])
logger = structlog.get_logger("account")


@router.post("/password", response_model=schemas.ChangePasswordResponse)
async def change_password(
    body: schemas.ChangePasswordRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> schemas.ChangePasswordResponse:
    """
    Change your password. Needs your current password. Every other device is signed out; send
    this device's `refresh_token` to keep this one signed in. Ten attempts per 15 minutes.
    """
    revoked = await service.change_password(
        db,
        user=current_user,
        current_password=body.current_password,
        new_password=body.new_password,
        keep_refresh_token=body.refresh_token,
    )
    await db.commit()
    return schemas.ChangePasswordResponse(
        message="Your password has been changed.", sessions_revoked=revoked
    )


@router.get("/export")
async def export_my_data(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """
    A copy of everything we hold about you, as a JSON file to download. It never contains your
    password, tokens or other people's personal details. Three a day is plenty: 3 per hour.
    """
    data = await privacy.export_my_data(db, user=current_user)
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": 'attachment; filename="alumni-challenge-my-data.json"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/delete", response_model=schemas.MessageResponse)
async def delete_my_account(
    body: schemas.DeleteAccountRequest,
    db: AsyncSession = Depends(get_db_session),
    storage: Storage = Depends(get_storage),
    current_user: User = Depends(get_current_user),
) -> schemas.MessageResponse:
    """
    Delete your account. Needs your password. Your profile and personal details are removed,
    every device is signed out, and you can never sign in again; the same email address can
    be used to register a new account. Records that must outlive you (the audit log, reports
    you filed) stay, with your identity taken out. The only super admin cannot delete theirs.
    """
    keys = await privacy.delete_account(db, user=current_user, password=body.password)
    await db.commit()
    for key in keys:
        try:
            await storage.delete(key)
        except StorageError:
            # The account is already gone; a leftover picture is logged for cleanup, not
            # allowed to turn a completed deletion into an error.
            logger.warning("deleted_account_file_not_removed", storage_key=key)
    return schemas.MessageResponse(message="Your account has been deleted.")
