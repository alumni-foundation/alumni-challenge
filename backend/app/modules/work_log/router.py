import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ForbiddenError
from app.core.permissions.dependencies import get_user_roles
from app.core.permissions.roles import Role
from app.core.rate_limit.limiter import hit
from app.infrastructure.database.session import get_db_session
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.work_log import schemas, service

router = APIRouter(prefix="/work-log", tags=["work-log"])

WRITES_PER_MINUTE = 60


async def require_writer(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)
) -> User:
    """Admins and moderators keep their own log. A super admin only reads, so never gets in here."""
    roles = await get_user_roles(db, user_id=current_user.id)
    if Role.SUPER_ADMIN in roles:
        raise ForbiddenError(
            "Super admins read the team work log but do not keep one of their own."
        )
    if not roles & {Role.ADMIN, Role.MODERATOR}:
        raise ForbiddenError("The work log is for platform admins and moderators.")
    return current_user


async def require_super_admin(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)
) -> User:
    if Role.SUPER_ADMIN not in await get_user_roles(db, user_id=current_user.id):
        raise ForbiddenError("Only a super admin can read the team work log.")
    return current_user


async def _write_limit(user: User) -> None:
    await hit(f"ratelimit:work_log_write:{user.id}", limit=WRITES_PER_MINUTE, window_seconds=60)


@router.get("/me", response_model=list[schemas.EntryResponse])
async def my_entries(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_writer),
) -> list[schemas.EntryResponse]:
    """Newest day first, and within a day in the order added. Without dates: the last 60 days."""
    return await service.list_mine(db, user.id, from_, to)


@router.post("/me", response_model=schemas.EntryResponse, status_code=status.HTTP_201_CREATED)
async def add_entry(
    body: schemas.EntryCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_writer),
) -> schemas.EntryResponse:
    await _write_limit(user)
    result = await service.add(db, user.id, body)
    await db.commit()
    return result


@router.patch("/me/{entry_id}", response_model=schemas.EntryResponse)
async def edit_entry(
    entry_id: uuid.UUID,
    body: schemas.EntryUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_writer),
) -> schemas.EntryResponse:
    await _write_limit(user)
    result = await service.edit(db, user.id, entry_id, body)
    await db.commit()
    return result


@router.post("/me/{entry_id}/complete", response_model=schemas.EntryResponse)
async def complete_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_writer),
) -> schemas.EntryResponse:
    await _write_limit(user)
    result = await service.complete(db, user.id, entry_id)
    await db.commit()
    return result


@router.delete("/me/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_writer),
) -> Response:
    await _write_limit(user)
    await service.remove(db, user.id, entry_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/team", response_model=list[schemas.TeamEntryResponse])
async def team_entries(
    user_id: uuid.UUID | None = None,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_super_admin),
) -> list[schemas.TeamEntryResponse]:
    """Everyone's entries, read-only, newest first. Super admins only."""
    return await service.list_team(
        db, user_id=user_id, start=from_, end=to, limit=limit, offset=offset
    )


@router.get("/team/people", response_model=list[schemas.PersonResponse])
async def team_people(
    db: AsyncSession = Depends(get_db_session), _: User = Depends(require_super_admin)
) -> list[schemas.PersonResponse]:
    """Admins and moderators, for the person filter. Super admins only."""
    return await service.list_people(db)
