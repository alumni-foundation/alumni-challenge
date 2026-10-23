import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.dependencies import require_roles
from app.core.permissions.roles import Role
from app.infrastructure.database.session import get_db_session
from app.modules.identity import account_status
from app.modules.identity.models import User, UserStatus

router = APIRouter(prefix="/users", tags=["accounts"])


class StatusChangeRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A reason is required.")
        return value


class AccountStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: UserStatus


@router.post("/{user_id}/suspend", response_model=AccountStatusResponse)
async def suspend(
    user_id: uuid.UUID,
    body: StatusChangeRequest,
    db: AsyncSession = Depends(get_db_session),
    actor: User = Depends(require_roles(Role.MODERATOR, Role.ADMIN, Role.SUPER_ADMIN)),
) -> User:
    user = await account_status.suspend_user(
        db, actor_id=actor.id, target_user_id=user_id, reason=body.reason
    )
    await db.commit()
    return user


@router.post("/{user_id}/reactivate", response_model=AccountStatusResponse)
async def reactivate(
    user_id: uuid.UUID,
    body: StatusChangeRequest,
    db: AsyncSession = Depends(get_db_session),
    actor: User = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
) -> User:
    user = await account_status.reactivate_user(
        db, actor_id=actor.id, target_user_id=user_id, reason=body.reason
    )
    await db.commit()
    return user
