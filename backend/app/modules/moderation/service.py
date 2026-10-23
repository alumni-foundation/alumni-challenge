import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession



from app.core.errors.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.alumni.models import AlumniProfile
from app.modules.audit import service as audit_service
from app.modules.moderation.models import (
    ACTIVE_REPORT_STATUSES,
    Report,
    ReportStatus,
    ReportTargetType,
)

_CLOSED_STATUSES = (ReportStatus.RESOLVED, ReportStatus.DISMISSED)


async def file_report(
    db: AsyncSession,
    *,
    reporter_user_id: uuid.UUID,
    target_type: ReportTargetType,
    target_id: uuid.UUID,
    reason: str,
) -> Report:
    reason = reason.strip()
    if not reason:
        raise ValidationError("A reason is required.")

    # Only profiles exist today. Messages and content are not built yet, so those target
    # types pass through unchecked until their modules exist.
    if target_type == ReportTargetType.PROFILE:
        profile = await db.get(AlumniProfile, target_id)
        if profile is None:
            raise ValidationError("The profile you are reporting does not exist.")
        if profile.user_id == reporter_user_id:
            raise ValidationError("You cannot report your own profile.")

    already_open = await db.scalar(
        select(Report.id).where(
            Report.reporter_user_id == reporter_user_id,
            Report.target_type == target_type,
            Report.target_id == target_id,
            Report.status.in_(ACTIVE_REPORT_STATUSES),
        )
    )
    if already_open is not None:
        raise ConflictError("You already have an open report on this.")

    report = Report(
        reporter_user_id=reporter_user_id,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        status=ReportStatus.OPEN,
    )
    db.add(report)
    await db.flush()
    return report


async def list_reports(
    db: AsyncSession, *, status_filter: ReportStatus | None, limit: int, offset: int
) -> list[Report]:
    stmt = select(Report).order_by(Report.created_at.desc(), Report.id)
    if status_filter is not None:
        stmt = stmt.where(Report.status == status_filter)
    stmt = stmt.limit(limit).offset(offset)
    return list((await db.scalars(stmt)).all())


async def review_report(
    db: AsyncSession,
    *,
    report_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    new_status: ReportStatus,
) -> Report:
    report = await db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report not found.")

    previous_status = report.status
    report.status = new_status
    report.reviewed_by = reviewer_user_id
    # Only a closed report has a resolution time. Re-opening one clears it.
    report.resolved_at = datetime.now(UTC) if new_status in _CLOSED_STATUSES else None
    await db.flush()

    await audit_service.record(
        db,
        actor_user_id=reviewer_user_id,
        action="report.review",
        target_type="report",
        target_id=report.id,
        context={
            "from_status": previous_status.value,
            "to_status": new_status.value,
            "reported_target_type": report.target_type.value,
            "reported_target_id": str(report.target_id),
        },
    )
    return report


async def has_active_report(
    db: AsyncSession,
    *,
    target_type: ReportTargetType,
    target_id: uuid.UUID,
    excluding_reporter_id: uuid.UUID | None = None,
) -> bool:
    """
    True only while a report is OPEN or REVIEWING. Re-evaluated on every call, so access
    that depends on it ends the moment the report is resolved or dismissed.

    `excluding_reporter_id` ignores reports filed by that user. A moderator must not be
    able to open a private profile by filing a report on it themselves.
    """
    stmt = select(Report.id).where(
        Report.target_type == target_type,
        Report.target_id == target_id,
        Report.status.in_(ACTIVE_REPORT_STATUSES),
    )
    if excluding_reporter_id is not None:
        stmt = stmt.where(Report.reporter_user_id != excluding_reporter_id)
    return (await db.scalar(stmt.limit(1))) is not None
