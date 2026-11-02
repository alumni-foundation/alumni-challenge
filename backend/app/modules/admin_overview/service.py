"""
Numbers for the admin dashboard. Every query counts rows; none returns a person. `scope` is the
set of organizations the numbers are about (None: the whole platform). A member of a school is
an active user whose profile names that school.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin_overview import schemas
from app.modules.alumni.models import AlumniProfile, VerificationStatus
from app.modules.audit.models import AuditLogEntry
from app.modules.bookings.models import Booking, BookingStatus, ManualPaymentState
from app.modules.connections.models import Connection, ConnectionStatus
from app.modules.events.models import Event, EventSlot, EventStatus
from app.modules.identity.models import User, UserStatus
from app.modules.moderation.models import Report, ReportStatus

PERIOD_DAYS = {"30d": 30, "90d": 90, "365d": 365}
STEPS = ("signed_up", "profile_complete", "verified", "connected", "booked_an_event")


def _percent(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def _total(value: int, previous: int) -> schemas.Total:
    change = round(100 * (value - previous) / previous, 1) if previous else None
    return schemas.Total(value=value, previous=previous, change_percent=change)


def _members(scope: set[uuid.UUID] | None) -> Select[Any]:
    """The people in scope: users joined to their profile (kept only when it names a school in
    scope, unless the whole platform is asked about)."""
    base = select(User.id).select_from(User)
    if scope is None:
        base = base.outerjoin(AlumniProfile, AlumniProfile.user_id == User.id)
    else:
        base = base.join(
            AlumniProfile,
            and_(AlumniProfile.user_id == User.id, AlumniProfile.school_id.in_(scope)),
        )
    return base.where(User.status == UserStatus.ACTIVE)


async def totals(
    db: AsyncSession, scope: set[uuid.UUID] | None, start: datetime, previous_start: datetime
) -> schemas.Totals:
    verified = AlumniProfile.verification_status == VerificationStatus.VERIFIED
    columns = [
        func.count(),
        func.count().filter(User.created_at < start),
        func.count().filter(User.created_at >= start),
        func.count().filter(and_(User.created_at >= previous_start, User.created_at < start)),
        func.count().filter(verified),
        func.count().filter(and_(verified, AlumniProfile.updated_at < start)),
    ]
    row = (await db.execute(_members(scope).with_only_columns(*columns))).one()
    members, members_before, new, new_before, verified_now, verified_before = tuple(row)
    return schemas.Totals(
        members=_total(members, members_before),
        new_members=_total(new, new_before),
        verified_members=_total(verified_now, verified_before),
    )


async def funnel(db: AsyncSession, scope: set[uuid.UUID] | None) -> list[schemas.FunnelStep]:
    """Each step counts only people who passed the steps before it, so it never grows."""
    complete = and_(
        AlumniProfile.school_id.is_not(None), AlumniProfile.graduation_year.is_not(None)
    )
    verified = and_(complete, AlumniProfile.verification_status == VerificationStatus.VERIFIED)
    # Whole sets, built once (a hashed semi-join), not asked again for every member.
    accepted = Connection.status == ConnectionStatus.ACCEPTED
    connected_ids = (
        select(Connection.requester_id)
        .where(accepted)
        .union(select(Connection.addressee_id).where(accepted))
    )
    booker_ids = select(Booking.booker_user_id).where(Booking.status == BookingStatus.CONFIRMED)
    connected = and_(verified, User.id.in_(connected_ids))
    booked = and_(connected, User.id.in_(booker_ids))
    conditions: list[ColumnElement[bool]] = [complete, verified, connected, booked]
    columns = [func.count(), *(func.count().filter(c) for c in conditions)]
    counts = list((await db.execute(_members(scope).with_only_columns(*columns))).one())
    return [
        schemas.FunnelStep(
            step=name,
            count=count,
            percent_of_previous=100.0 if i == 0 else _percent(count, counts[i - 1]),
        )
        for i, (name, count) in enumerate(zip(STEPS, counts, strict=True))
    ]


async def attention(
    db: AsyncSession, scope: set[uuid.UUID] | None, *, with_reports: bool, with_org_work: bool
) -> schemas.Attention:
    reports_open = reports_reviewing = None
    if with_reports:
        report_rows = (
            await db.execute(
                select(Report.status, func.count())
                .where(Report.status.in_((ReportStatus.OPEN, ReportStatus.REVIEWING)))
                .group_by(Report.status)
            )
        ).all()
        rows = {status: n for status, n in report_rows}
        reports_open = rows.get(ReportStatus.OPEN, 0)
        reports_reviewing = rows.get(ReportStatus.REVIEWING, 0)
    if not with_org_work:
        return schemas.Attention(
            reports_open=reports_open,
            reports_reviewing=reports_reviewing,
            verification_requests_waiting=None,
            payments_waiting_confirmation=None,
            refunds_due=None,
            events_in_draft=None,
        )

    # Unverified people who have named a school and a graduation year: they are waiting for
    # an admin or for vouches. (There is no separate "request" record to count.)
    waiting_stmt = (
        select(func.count())
        .select_from(AlumniProfile)
        .join(User, User.id == AlumniProfile.user_id)
        .where(
            User.status == UserStatus.ACTIVE,
            AlumniProfile.verification_status == VerificationStatus.UNVERIFIED,
            AlumniProfile.school_id.is_not(None),
            AlumniProfile.graduation_year.is_not(None),
        )
    )
    if scope is not None:
        waiting_stmt = waiting_stmt.where(AlumniProfile.school_id.in_(scope))
    waiting = await db.scalar(waiting_stmt) or 0

    money = (
        select(Booking.payment_state, func.count())
        .join(Event, Event.id == Booking.event_id)
        .where(
            Booking.payment_state.in_(
                (ManualPaymentState.AWAITING_CONFIRMATION, ManualPaymentState.NEEDS_REFUND)
            )
        )
        .group_by(Booking.payment_state)
    )
    drafts = select(func.count()).select_from(Event).where(Event.status == EventStatus.DRAFT)
    if scope is not None:
        money = money.where(Event.organization_id.in_(scope))
        drafts = drafts.where(Event.organization_id.in_(scope))
    by_state = {state: n for state, n in (await db.execute(money)).all()}
    return schemas.Attention(
        reports_open=reports_open,
        reports_reviewing=reports_reviewing,
        verification_requests_waiting=waiting,
        payments_waiting_confirmation=by_state.get(ManualPaymentState.AWAITING_CONFIRMATION, 0),
        refunds_due=by_state.get(ManualPaymentState.NEEDS_REFUND, 0),
        events_in_draft=await db.scalar(drafts) or 0,
    )


async def upcoming(
    db: AsyncSession, scope: set[uuid.UUID] | None, now: datetime
) -> list[schemas.UpcomingEvent]:
    stmt = (
        select(
            Event.id,
            Event.title,
            Event.starts_at,
            func.coalesce(func.sum(EventSlot.seats_confirmed), 0),
            func.sum(EventSlot.capacity),
            func.bool_or(EventSlot.capacity.is_(None)),
        )
        .join(EventSlot, EventSlot.event_id == Event.id)
        .where(Event.status == EventStatus.PUBLISHED, Event.starts_at > now)
        .group_by(Event.id)
        .order_by(Event.starts_at, Event.id)
        .limit(5)
    )
    if scope is not None:
        stmt = stmt.where(Event.organization_id.in_(scope))
    return [
        schemas.UpcomingEvent(
            id=event_id,
            title=title,
            starts_at=starts_at,
            confirmed_seats=int(confirmed),
            capacity=None if unlimited or capacity is None else int(capacity),
        )
        for event_id, title, starts_at, confirmed, capacity, unlimited in (
            await db.execute(stmt)
        ).all()
    ]


async def signups(
    db: AsyncSession, scope: set[uuid.UUID] | None, start: datetime, days: int, today: date
) -> list[schemas.SignupDay]:
    day = func.date(func.timezone("UTC", User.created_at))
    stmt = _members(scope).with_only_columns(day, func.count()).where(User.created_at >= start)
    counted: dict[date, int] = {d: n for d, n in (await db.execute(stmt.group_by(day))).all()}
    first = today - timedelta(days=days - 1)
    return [
        schemas.SignupDay(day=d, count=counted.get(d, 0))
        for d in (first + timedelta(days=i) for i in range(days))
    ]


async def recent_audit(db: AsyncSession, scope: set[uuid.UUID] | None) -> list[schemas.AuditItem]:
    org = AuditLogEntry.context["organization_id"].astext
    stmt = select(
        AuditLogEntry.id,
        AuditLogEntry.action,
        AuditLogEntry.target_type,
        AuditLogEntry.target_id,
        AuditLogEntry.actor_user_id,
        org,
        AuditLogEntry.created_at,
    ).order_by(AuditLogEntry.created_at.desc(), AuditLogEntry.id)
    if scope is not None:
        stmt = stmt.where(org.in_([str(o) for o in scope]))
    rows = (await db.execute(stmt.limit(8))).all()
    return [
        schemas.AuditItem(
            id=entry_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            actor_user_id=actor,
            organization_id=uuid.UUID(o) if o else None,
            created_at=created,
        )
        for entry_id, action, target_type, target_id, actor, o, created in rows
    ]


async def build(
    db: AsyncSession,
    *,
    period: str,
    organization_id: uuid.UUID | None,
    scope: set[uuid.UUID] | None,
    see_members: bool,
    see_reports: bool,
    see_audit: bool,
) -> schemas.Overview:
    days = PERIOD_DAYS[period]
    now = datetime.now(UTC)
    start = now - timedelta(days=days)
    return schemas.Overview(
        period=period,
        organization_id=organization_id,
        totals=(
            await totals(db, scope, start, start - timedelta(days=days)) if see_members else None
        ),
        funnel=await funnel(db, scope) if see_members else None,
        attention=await attention(db, scope, with_reports=see_reports, with_org_work=see_members),
        upcoming_events=await upcoming(db, scope, now) if see_members else None,
        signups_per_day=(
            await signups(db, scope, start, days, now.date()) if see_members else None
        ),
        recent_audit=await recent_audit(db, scope) if see_audit else None,
    )
