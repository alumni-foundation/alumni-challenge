import uuid
from datetime import date, datetime

from pydantic import BaseModel


class Total(BaseModel):
    """`previous` is the same measure one period earlier; `change_percent` is null when that
    was zero (there is nothing to compare with)."""

    value: int
    previous: int
    change_percent: float | None


class Totals(BaseModel):
    members: Total
    new_members: Total
    # `previous` is a lower bound: the database does not record when someone was verified, so
    # it counts people verified now whose profile has not changed since the period began.
    verified_members: Total


class FunnelStep(BaseModel):
    step: str
    count: int
    percent_of_previous: float | None


class Attention(BaseModel):
    """Reports are platform-wide, so they are null in any one organization's view."""

    reports_open: int | None
    reports_reviewing: int | None
    verification_requests_waiting: int | None
    payments_waiting_confirmation: int | None
    refunds_due: int | None
    events_in_draft: int | None


class UpcomingEvent(BaseModel):
    id: uuid.UUID
    title: str
    starts_at: datetime
    confirmed_seats: int
    capacity: int | None  # null: at least one slot has no limit


class SignupDay(BaseModel):
    day: date
    count: int


class AuditItem(BaseModel):
    """What happened and to what, never the details (they can hold names and emails)."""

    id: uuid.UUID
    action: str
    target_type: str
    target_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    organization_id: uuid.UUID | None
    created_at: datetime


class Overview(BaseModel):
    """Aggregated counts only. A section a caller may not see is null."""

    period: str
    organization_id: uuid.UUID | None
    totals: Totals | None
    funnel: list[FunnelStep] | None
    attention: Attention
    upcoming_events: list[UpcomingEvent] | None
    signups_per_day: list[SignupDay] | None
    recent_audit: list[AuditItem] | None
