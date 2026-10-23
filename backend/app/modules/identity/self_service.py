from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db_session
from app.modules.identity import schemas, service
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/auth/me", tags=["account"])


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
