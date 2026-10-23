import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.dependencies import require_roles
from app.core.permissions.roles import Role
from app.core.rate_limit import rate_limit
from app.infrastructure.database.session import get_db_session
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.moderation import schemas, service
from app.modules.moderation.models import Report, ReportStatus

router = APIRouter(prefix="/reports", tags=["moderation"])

_MODERATION_ROLES = (Role.MODERATOR, Role.ADMIN, Role.SUPER_ADMIN)


@router.post(
    "",
    response_model=schemas.ReportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("report_file", limit=20, window_seconds=3600))],
)
async def file_report(
    body: schemas.ReportCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Report:
    report = await service.file_report(
        db,
        reporter_user_id=current_user.id,
        target_type=body.target_type,
        target_id=body.target_id,
        reason=body.reason,
    )
    await db.commit()
    return report


@router.get("", response_model=list[schemas.ReportResponse])
async def list_reports(
    status_filter: ReportStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles(*_MODERATION_ROLES)),
) -> list[Report]:
    return await service.list_reports(db, status_filter=status_filter, limit=limit, offset=offset)


@router.patch("/{report_id}", response_model=schemas.ReportResponse)
async def review_report(
    report_id: uuid.UUID,
    body: schemas.ReportReview,
    db: AsyncSession = Depends(get_db_session),
    reviewer: User = Depends(require_roles(*_MODERATION_ROLES)),
) -> Report:
    report = await service.review_report(
        db, report_id=report_id, reviewer_user_id=reviewer.id, new_status=body.status
    )
    await db.commit()
    return report
