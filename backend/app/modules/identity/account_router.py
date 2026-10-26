import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.dependencies import require_roles
from app.core.permissions.roles import Role
from app.infrastructure.database.session import get_db_session
from app.modules.identity import account_status, user_list
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


class UserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    status: UserStatus
    roles: list[Role]
    created_at: datetime


class AccountStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: UserStatus


@router.get("", response_model=list[UserListItem])
async def list_users(
    response: Response,
    q: str | None = Query(default=None, max_length=100, description="Part of a name or email"),
    status: Literal["active", "suspended"] | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    _admin: User = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
) -> list[user_list.UserRow]:
    """
    Every account except deleted ones, newest first, for platform admins. The total is in the
    X-Total-Count header.
    """
    rows, total = await user_list.list_users(
        db, q=q, status=UserStatus(status) if status else None, limit=limit, offset=offset
    )
    response.headers["X-Total-Count"] = str(total)
    return rows


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
