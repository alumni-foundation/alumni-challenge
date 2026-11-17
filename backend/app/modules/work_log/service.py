"""
The staff work log. The clock lives in `nairobi_now`, the only place the day is decided, so a
test can move it. Every read and write of one person's entry goes through `_own`, which matches
the author as well as the id: somebody else's entry is "not found", exactly like one that does
not exist.
"""

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.permissions.roles import Role
from app.modules.alumni.models import AlumniProfile
from app.modules.identity.models import User, UserStatus
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.work_log import schemas
from app.modules.work_log.models import WorkLogEntry, WorkLogKind

NAIROBI = ZoneInfo("Africa/Nairobi")
DEFAULT_DAYS = 60  # what "my entries" covers when no dates are asked for
MAX_RANGE_DAYS = 366
MY_ENTRIES_CAP = 500
LOCKED = "This entry is from an earlier day, so it can no longer be changed."


def nairobi_now() -> datetime:
    return datetime.now(NAIROBI)


def today() -> date:
    return nairobi_now().date()


def check_range(start: date | None, end: date | None) -> None:
    if start and end and start > end:
        raise ValidationError("The start date must not be after the end date.")


def as_response(entry: WorkLogEntry, today_: date) -> schemas.EntryResponse:
    return schemas.EntryResponse(
        id=entry.id,
        kind=entry.kind,
        text=entry.text,
        entry_date=entry.entry_date,
        created_at=entry.created_at,
        completed_at=entry.completed_at,
        editable=entry.entry_date == today_,
    )


async def list_mine(
    db: AsyncSession, user_id: uuid.UUID, start: date | None, end: date | None
) -> list[schemas.EntryResponse]:
    """Newest day first, and within a day in the order the lines were added."""
    check_range(start, end)
    today_ = today()
    if end is None:
        end = today_
    if start is None:
        start = end - timedelta(days=DEFAULT_DAYS)
    if (end - start).days > MAX_RANGE_DAYS:
        raise ValidationError("Please ask for a year or less at a time.")
    stmt = (
        select(WorkLogEntry)
        .where(
            WorkLogEntry.author_user_id == user_id,
            WorkLogEntry.entry_date >= start,
            WorkLogEntry.entry_date <= end,
        )
        .order_by(WorkLogEntry.entry_date.desc(), WorkLogEntry.created_at, WorkLogEntry.id)
        .limit(MY_ENTRIES_CAP)
    )
    return [as_response(e, today_) for e in (await db.scalars(stmt)).all()]


async def _own(
    db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID, *, lock: bool = False
) -> WorkLogEntry:
    stmt = select(WorkLogEntry).where(
        WorkLogEntry.id == entry_id, WorkLogEntry.author_user_id == user_id
    )
    if lock:
        stmt = stmt.with_for_update()
    entry = await db.scalar(stmt)
    if entry is None:
        raise NotFoundError("Entry not found.")
    return entry


def _require_today(entry: WorkLogEntry) -> None:
    if entry.entry_date != today():
        raise ConflictError(LOCKED, code="work_log_entry_locked")


async def add(
    db: AsyncSession, user_id: uuid.UUID, body: schemas.EntryCreate
) -> schemas.EntryResponse:
    now = nairobi_now()
    entry = WorkLogEntry(
        author_user_id=user_id,
        kind=body.kind,
        text=body.text,
        entry_date=now.date(),
        created_at=now,
        updated_at=now,
        # A line added as already done was finished when it was written.
        completed_at=now if body.kind == WorkLogKind.DONE else None,
    )
    db.add(entry)
    await db.flush()
    return as_response(entry, now.date())


async def edit(
    db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID, body: schemas.EntryUpdate
) -> schemas.EntryResponse:
    entry = await _own(db, user_id, entry_id, lock=True)
    _require_today(entry)
    entry.text = body.text
    entry.updated_at = nairobi_now()
    await db.flush()
    return as_response(entry, today())


async def complete(
    db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID
) -> schemas.EntryResponse:
    """
    Allowed on any day: a plan made yesterday is usually finished today. Marking a line that is
    already done changes nothing, so a double tap is harmless.
    """
    entry = await _own(db, user_id, entry_id, lock=True)
    if entry.kind == WorkLogKind.PLANNED:
        now = nairobi_now()
        entry.kind = WorkLogKind.DONE
        entry.completed_at = now
        entry.updated_at = now
        await db.flush()
    return as_response(entry, today())


async def remove(db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    entry = await _own(db, user_id, entry_id, lock=True)
    _require_today(entry)
    await db.delete(entry)
    await db.flush()


def _name(full_name: str | None, email: str) -> str:
    return full_name or email


async def list_team(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    start: date | None,
    end: date | None,
    limit: int,
    offset: int,
) -> list[schemas.TeamEntryResponse]:
    check_range(start, end)
    # Staff often have no alumni profile, so the name is an outer join and falls back to the email.
    stmt = (
        select(WorkLogEntry, User.email, AlumniProfile.full_name)
        .join(User, User.id == WorkLogEntry.author_user_id)
        .outerjoin(AlumniProfile, AlumniProfile.user_id == User.id)
    )
    if user_id is not None:
        stmt = stmt.where(WorkLogEntry.author_user_id == user_id)
    if start is not None:
        stmt = stmt.where(WorkLogEntry.entry_date >= start)
    if end is not None:
        stmt = stmt.where(WorkLogEntry.entry_date <= end)
    stmt = (
        stmt.order_by(
            WorkLogEntry.entry_date.desc(), WorkLogEntry.created_at.desc(), WorkLogEntry.id
        )
        .limit(limit)
        .offset(offset)
    )
    return [
        schemas.TeamEntryResponse(
            id=e.id,
            author_user_id=e.author_user_id,
            author_name=_name(full_name, email),
            author_email=email,
            kind=e.kind,
            text=e.text,
            entry_date=e.entry_date,
            created_at=e.created_at,
            completed_at=e.completed_at,
        )
        for e, email, full_name in (await db.execute(stmt)).all()
    ]


async def list_people(db: AsyncSession) -> list[schemas.PersonResponse]:
    """Admins and moderators now, plus anyone who wrote entries and has since lost the role."""
    holders = select(Membership.user_id).where(
        Membership.status == MembershipStatus.ACTIVE,
        Membership.role.in_((Role.ADMIN, Role.MODERATOR)),
    )
    authors = select(WorkLogEntry.author_user_id).distinct()
    stmt = (
        select(User.id, User.email, AlumniProfile.full_name)
        .outerjoin(AlumniProfile, AlumniProfile.user_id == User.id)
        .where(
            User.status != UserStatus.DELETED,
            or_(User.id.in_(holders), User.id.in_(authors)),
        )
        .order_by(func.lower(func.coalesce(AlumniProfile.full_name, User.email)), User.id)
    )
    return [
        schemas.PersonResponse(user_id=uid, name=_name(full_name, email), email=email)
        for uid, email, full_name in (await db.execute(stmt)).all()
    ]
