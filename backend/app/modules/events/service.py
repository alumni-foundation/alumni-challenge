"""
Events: creating, editing, publishing, and the read models (summary, detail) the API returns.

Seat changes (bookings) are NOT here; they live in bookings.seats, the only place seat counters
are written.
"""

import math
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.modules.audit.service import record as record_audit
from app.modules.events import access, schemas
from app.modules.events.models import (
    Event,
    EventConsent,
    EventQuestion,
    EventSeries,
    EventSlot,
    EventStatus,
    EventVisibility,
    QuestionKind,
)
from app.modules.files.urls import public_file_path
from app.modules.identity.models import User
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.organizations.models import Organization
from app.modules.organizations.service import get_active_organization

# Longer holds are for events paid for outside the app (manual M-Pesa); see slice 5.5.
MAX_HOLD_MINUTES_WITHOUT_MANUAL_PAYMENT = 60

_NOT_NULL_EVENT_FIELDS = frozenset(
    {
        "title",
        "category",
        "visibility",
        "starts_at",
        "ends_at",
        "price_minor",
        "currency",
        "max_party_size",
        "hold_minutes",
        "waitlist_enabled",
        "show_attendee_list",
        "reminder_hours_before",
    }
)


# ----------------------------------------------------------------------------- helpers


def _now() -> datetime:
    return datetime.now(UTC)


def _org_context(organization_id: uuid.UUID | None) -> dict[str, Any]:
    return {"organization_id": str(organization_id)} if organization_id else {}


async def _audit(
    db: AsyncSession,
    *,
    actor: User,
    action: str,
    event: Event,
    target_type: str = "event",
    target_id: uuid.UUID | None = None,
    **context: Any,
) -> None:
    await record_audit(
        db,
        actor_user_id=actor.id,
        action=action,
        target_type=target_type,
        target_id=target_id or event.id,
        context={**_org_context(event.organization_id), "event_id": str(event.id), **context},
    )


def seats_left(capacity: int | None, confirmed: int, held: int) -> int | None:
    return None if capacity is None else max(capacity - confirmed - held, 0)


def availability_of(capacity: int | None, left: int | None) -> str:
    """open, few_left or full. Unlimited is always open."""
    if capacity is None or left is None:
        return "open"
    if left == 0:
        return "full"
    return "few_left" if left <= max(3, math.ceil(capacity * 0.1)) else "open"


def registration_state(event: Event, now: datetime) -> str:
    if event.status == EventStatus.DRAFT:
        return "draft"
    if event.status == EventStatus.CANCELLED:
        return "cancelled"
    if event.status == EventStatus.COMPLETED or now >= event.ends_at:
        return "ended"
    if event.status == EventStatus.CLOSED:
        return "closed"
    if event.registration_opens_at is not None and now < event.registration_opens_at:
        return "not_open_yet"
    if event.registration_closes_at is not None and now >= event.registration_closes_at:
        return "closed"
    return "open"


def _check_times(
    *,
    starts_at: datetime,
    ends_at: datetime,
    opens_at: datetime | None,
    closes_at: datetime | None,
) -> None:
    if ends_at <= starts_at:
        raise ValidationError("The event must end after it starts.", code="invalid_times")
    if opens_at is not None and closes_at is not None and closes_at <= opens_at:
        raise ValidationError(
            "Registration must close after it opens.", code="invalid_registration_window"
        )
    if closes_at is not None and closes_at > ends_at:
        raise ValidationError(
            "Registration cannot stay open after the event has ended.",
            code="invalid_registration_window",
        )


# ------------------------------------------------------------------------- read models


async def _slots_by_event(
    db: AsyncSession, event_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[EventSlot]]:
    out: dict[uuid.UUID, list[EventSlot]] = {i: [] for i in event_ids}
    if not event_ids:
        return out
    rows = await db.scalars(
        select(EventSlot)
        .where(EventSlot.event_id.in_(event_ids))
        .order_by(EventSlot.position, EventSlot.starts_at, EventSlot.id)
    )
    for slot in rows:
        out[slot.event_id].append(slot)
    return out


def slot_out(slot: EventSlot) -> schemas.SlotOut:
    left = seats_left(slot.capacity, slot.seats_confirmed, slot.seats_held)
    return schemas.SlotOut(
        id=slot.id,
        label=slot.label,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        capacity=slot.capacity,
        seats_confirmed=slot.seats_confirmed,
        seats_held=slot.seats_held,
        position=slot.position,
        spots_left=left,
        availability=availability_of(slot.capacity, left),
    )


def _event_availability(slots: list[EventSlot]) -> tuple[int | None, str]:
    """Across all slots: seats left (None if any slot is unlimited) and the overall word."""
    if not slots:
        return 0, "full"
    if any(s.capacity is None for s in slots):
        return None, "open"
    total_capacity = sum(s.capacity or 0 for s in slots)
    left = sum(seats_left(s.capacity, s.seats_confirmed, s.seats_held) or 0 for s in slots)
    return left, availability_of(total_capacity, left)


async def build_summaries(db: AsyncSession, events: list[Event]) -> list[schemas.EventSummary]:
    ids = [e.id for e in events]
    slots = await _slots_by_event(db, ids)

    org_ids = {e.organization_id for e in events if e.organization_id}
    orgs: dict[uuid.UUID, Organization] = {}
    if org_ids:
        orgs = {
            o.id: o
            for o in await db.scalars(select(Organization).where(Organization.id.in_(org_ids)))
        }
    series_ids = {e.series_id for e in events if e.series_id}
    series: dict[uuid.UUID, EventSeries] = {}
    if series_ids:
        series = {
            s.id: s
            for s in await db.scalars(select(EventSeries).where(EventSeries.id.in_(series_ids)))
        }

    now = _now()
    out: list[schemas.EventSummary] = []
    for e in events:
        left, word = _event_availability(slots[e.id])
        org = orgs.get(e.organization_id) if e.organization_id else None
        ser = series.get(e.series_id) if e.series_id else None
        out.append(
            schemas.EventSummary(
                id=e.id,
                title=e.title,
                category=e.category,
                status=e.status,
                visibility=e.visibility,
                starts_at=e.starts_at,
                ends_at=e.ends_at,
                venue_name=e.venue_name,
                poster_url=public_file_path(e.poster_file_id) if e.poster_file_id else None,
                organizer=schemas.OrganizerInfo(
                    id=org.id, name=org.name, slug=org.slug, type=org.type
                )
                if org
                else None,
                price_minor=e.price_minor,
                currency=e.currency,
                max_party_size=e.max_party_size,
                series=schemas.SeriesInfo(
                    id=ser.id, title=ser.title, round_number=e.round_number or 0
                )
                if ser
                else None,
                going_count=sum(s.seats_confirmed for s in slots[e.id]),
                spots_left=left,
                availability=word,
                registration=schemas.RegistrationInfo(
                    state=registration_state(e, now),
                    opens_at=e.registration_opens_at,
                    closes_at=e.registration_closes_at,
                ),
            )
        )
    return out


async def build_detail(db: AsyncSession, event: Event, *, can_manage: bool) -> schemas.EventDetail:
    summary = (await build_summaries(db, [event]))[0]
    slots = (await _slots_by_event(db, [event.id]))[event.id]
    questions = (
        await db.scalars(
            select(EventQuestion)
            .where(EventQuestion.event_id == event.id)
            .order_by(EventQuestion.position, EventQuestion.created_at, EventQuestion.id)
        )
    ).all()
    consents = (
        await db.scalars(
            select(EventConsent)
            .where(EventConsent.event_id == event.id)
            .order_by(EventConsent.created_at, EventConsent.id)
        )
    ).all()
    return schemas.EventDetail(
        **summary.model_dump(),
        description=event.description,
        venue_address=event.venue_address,
        contact_email=event.contact_email,
        contact_phone=event.contact_phone,
        refund_policy_text=event.refund_policy_text,
        waitlist_enabled=event.waitlist_enabled,
        show_attendee_list=event.show_attendee_list,
        reminder_hours_before=event.reminder_hours_before,
        hold_minutes=event.hold_minutes,
        slots=[slot_out(s) for s in slots],
        questions=[schemas.QuestionOut.model_validate(q) for q in questions],
        consents=[schemas.ConsentOut.model_validate(c) for c in consents],
        can_manage=can_manage,
    )


async def _managed_scope(db: AsyncSession, user: User) -> tuple[bool, set[uuid.UUID]]:
    """(is a platform admin, organizations where the user holds an event-running role)."""
    rows = (
        await db.execute(
            select(Membership.role, Membership.organization_id).where(
                Membership.user_id == user.id, Membership.status == MembershipStatus.ACTIVE
            )
        )
    ).all()
    platform = any(role in access.PLATFORM_ADMIN_ROLES for role, _ in rows)
    orgs = {org for role, org in rows if org is not None and role in access.MANAGER_ROLES}
    return platform, orgs


async def list_events(
    db: AsyncSession,
    *,
    viewer: User | None,
    category: str | None,
    organization_id: uuid.UUID | None,
    series_id: uuid.UUID | None,
    starts_after: datetime | None,
    starts_before: datetime | None,
    q: str | None,
    past: bool,
    manage: bool,
    limit: int,
    offset: int,
) -> tuple[list[Event], int]:
    now = _now()
    stmt = select(Event)
    if manage:
        if viewer is None:
            raise ForbiddenError("Sign in to see the events you run.")
        platform, orgs = await _managed_scope(db, viewer)
        if not platform:
            if not orgs:
                return [], 0
            stmt = stmt.where(Event.organization_id.in_(orgs))
    else:
        if past:
            stmt = stmt.where(
                Event.status.in_(
                    (EventStatus.PUBLISHED, EventStatus.CLOSED, EventStatus.COMPLETED)
                ),
                Event.ends_at < now,
            )
        else:
            stmt = stmt.where(
                Event.status.in_((EventStatus.PUBLISHED, EventStatus.CLOSED)), Event.ends_at >= now
            )
        if viewer is None:
            stmt = stmt.where(Event.visibility == EventVisibility.PUBLIC)

    if category:
        stmt = stmt.where(Event.category == category)
    if organization_id:
        stmt = stmt.where(Event.organization_id == organization_id)
    if series_id:
        stmt = stmt.where(Event.series_id == series_id)
    if starts_after:
        stmt = stmt.where(Event.starts_at >= starts_after)
    if starts_before:
        stmt = stmt.where(Event.starts_at < starts_before)
    if q:
        escaped = re.sub(r"([\\%_])", r"\\\1", q.strip())
        stmt = stmt.where(Event.title.ilike(f"%{escaped}%", escape="\\"))

    total = int(await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    order = (
        (Event.starts_at.desc(), Event.id) if (past and not manage) else (Event.starts_at, Event.id)
    )
    rows = (await db.scalars(stmt.order_by(*order).limit(limit).offset(offset))).all()
    return list(rows), total


# ---------------------------------------------------------------------------- creating


async def _require_can_run(
    db: AsyncSession, *, user: User, organization_id: uuid.UUID | None, admin_only: bool = False
) -> None:
    roles = await access.event_roles(db, user=user, organization_id=organization_id)
    # For a platform event `roles` holds platform-wide roles only, so only platform admins pass.
    needed = access.ADMIN_ROLES if admin_only else access.MANAGER_ROLES
    if not roles & needed:
        raise ForbiddenError("You do not have permission to manage events here.")


async def _check_series(
    db: AsyncSession,
    *,
    series_id: uuid.UUID | None,
    round_number: int | None,
    organization_id: uuid.UUID | None,
    event_id: uuid.UUID | None,
) -> None:
    if (series_id is None) != (round_number is None):
        raise ValidationError(
            "A series and a round number go together.", code="series_round_required"
        )
    if series_id is None:
        return
    series = await db.get(EventSeries, series_id)
    if series is None or series.organization_id != organization_id:
        raise NotFoundError("Series not found.")
    clash = await db.scalar(
        select(Event.id).where(
            Event.series_id == series_id,
            Event.round_number == round_number,
            Event.id != (event_id or uuid.UUID(int=0)),
        )
    )
    if clash is not None:
        raise ConflictError("That round already exists in this series.", code="round_taken")


def _check_slot_capacity(capacity: int | None, price_minor: int) -> None:
    if capacity is None and price_minor > 0:
        raise ValidationError(
            "A paid event needs a capacity on every slot.", code="capacity_required"
        )


def _check_slot_times(starts_at: datetime, ends_at: datetime) -> None:
    if ends_at <= starts_at:
        raise ValidationError("A slot must end after it starts.", code="invalid_times")


def _check_hold(hold_minutes: int) -> None:
    if hold_minutes > MAX_HOLD_MINUTES_WITHOUT_MANUAL_PAYMENT:
        raise ValidationError(
            "Reservations can be held for 60 minutes at most.", code="hold_too_long"
        )


async def create_event(db: AsyncSession, *, actor: User, body: schemas.EventCreate) -> Event:
    if body.organization_id is not None:
        await get_active_organization(db, organization_id=body.organization_id)
    await _require_can_run(db, user=actor, organization_id=body.organization_id)

    _check_times(
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        opens_at=body.registration_opens_at,
        closes_at=body.registration_closes_at,
    )
    _check_hold(body.hold_minutes)
    await _check_series(
        db,
        series_id=body.series_id,
        round_number=body.round_number,
        organization_id=body.organization_id,
        event_id=None,
    )
    slot_inputs = body.slots or [
        schemas.SlotInput(
            label=None, starts_at=body.starts_at, ends_at=body.ends_at, capacity=body.capacity
        )
    ]
    for s in slot_inputs:
        _check_slot_times(s.starts_at, s.ends_at)
        _check_slot_capacity(s.capacity, body.price_minor)

    event = Event(
        **body.model_dump(exclude={"capacity", "slots"}),
        status=EventStatus.DRAFT,
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.add(event)
    await db.flush()
    for i, s in enumerate(slot_inputs):
        db.add(
            EventSlot(
                event_id=event.id,
                label=s.label,
                starts_at=s.starts_at,
                ends_at=s.ends_at,
                capacity=s.capacity,
                position=s.position or i,
            )
        )
    await db.flush()
    await _audit(db, actor=actor, action="event.create", event=event, title=event.title)
    return event


async def _has_bookings(db: AsyncSession, event: Event) -> bool:
    from app.modules.bookings.models import Booking

    return (
        await db.scalar(select(Booking.id).where(Booking.event_id == event.id).limit(1))
    ) is not None


async def update_event(
    db: AsyncSession, *, actor: User, event: Event, body: schemas.EventUpdate
) -> Event:
    if event.status in (EventStatus.CANCELLED, EventStatus.COMPLETED):
        raise ConflictError("This event can no longer be changed.", code="event_final")
    changes = body.model_dump(exclude_unset=True)
    for key in changes:
        if changes[key] is None and key in _NOT_NULL_EVENT_FIELDS:
            raise ValidationError(f"{key} cannot be empty.", code="field_required")
    if "hold_minutes" in changes:
        _check_hold(changes["hold_minutes"])
    frozen = {"price_minor", "currency", "max_party_size"} & {
        k for k, v in changes.items() if v != getattr(event, k)
    }
    if frozen and await _has_bookings(db, event):
        raise ConflictError(
            "People have already booked, so the price, currency and group size can no longer "
            "change.",
            code="event_has_bookings",
        )

    merged = {
        "starts_at": changes.get("starts_at", event.starts_at),
        "ends_at": changes.get("ends_at", event.ends_at),
        "opens_at": changes.get("registration_opens_at", event.registration_opens_at),
        "closes_at": changes.get("registration_closes_at", event.registration_closes_at),
    }
    _check_times(**merged)
    if "series_id" in changes or "round_number" in changes:
        await _check_series(
            db,
            series_id=changes.get("series_id", event.series_id),
            round_number=changes.get("round_number", event.round_number),
            organization_id=event.organization_id,
            event_id=event.id,
        )
    if changes.get("price_minor", 0) > 0:
        unlimited = await db.scalar(
            select(EventSlot.id)
            .where(EventSlot.event_id == event.id, EventSlot.capacity.is_(None))
            .limit(1)
        )
        if unlimited is not None:
            raise ValidationError(
                "Give every slot a capacity before charging for the event.",
                code="capacity_required",
            )

    for key, value in changes.items():
        setattr(event, key, value)
    event.updated_by = actor.id
    await db.flush()
    await _audit(db, actor=actor, action="event.update", event=event, fields=sorted(changes))
    return event


async def delete_draft(db: AsyncSession, *, actor: User, event: Event) -> None:
    if event.status != EventStatus.DRAFT:
        raise ConflictError(
            "Only a draft can be deleted. Cancel a published event instead.", code="not_a_draft"
        )
    await _audit(db, actor=actor, action="event.delete", event=event, title=event.title)
    await db.delete(event)
    await db.flush()


# ------------------------------------------------------------------------- transitions


async def publish(db: AsyncSession, *, actor: User, event: Event) -> Event:
    if event.status != EventStatus.DRAFT:
        raise ConflictError("Only a draft can be published.", code="not_a_draft")
    if event.ends_at <= _now():
        raise ValidationError("The event is already over.", code="event_in_past")
    slots = (await db.scalars(select(EventSlot).where(EventSlot.event_id == event.id))).all()
    if not slots:
        raise ValidationError("Add at least one slot before publishing.", code="no_slots")
    for s in slots:
        _check_slot_capacity(s.capacity, event.price_minor)
    event.status = EventStatus.PUBLISHED
    event.updated_by = actor.id
    await db.flush()
    await _audit(db, actor=actor, action="event.publish", event=event)
    return event


async def close_registration(db: AsyncSession, *, actor: User, event: Event) -> Event:
    if event.status != EventStatus.PUBLISHED:
        raise ConflictError("Only a published event can be closed.", code="not_published")
    event.status = EventStatus.CLOSED
    event.updated_by = actor.id
    await db.flush()
    await _audit(db, actor=actor, action="event.close", event=event)
    return event


async def reopen_registration(db: AsyncSession, *, actor: User, event: Event) -> Event:
    if event.status != EventStatus.CLOSED:
        raise ConflictError("Only a closed event can be reopened.", code="not_closed")
    if event.ends_at <= _now():
        raise ConflictError("The event is already over.", code="event_in_past")
    event.status = EventStatus.PUBLISHED
    event.updated_by = actor.id
    await db.flush()
    await _audit(db, actor=actor, action="event.reopen", event=event)
    return event


async def complete(db: AsyncSession, *, actor: User, event: Event) -> Event:
    if event.status not in (EventStatus.PUBLISHED, EventStatus.CLOSED):
        raise ConflictError("Only a published event can be completed.", code="not_published")
    if event.starts_at > _now():
        raise ConflictError("The event has not started yet.", code="event_not_started")
    event.status = EventStatus.COMPLETED
    event.updated_by = actor.id
    await db.flush()
    await _audit(db, actor=actor, action="event.complete", event=event)
    return event


async def cancel(db: AsyncSession, *, actor: User, event: Event, reason: str) -> Event:
    if event.status not in (EventStatus.PUBLISHED, EventStatus.CLOSED):
        raise ConflictError("Only a published event can be cancelled.", code="not_published")
    from app.modules.bookings.service import cancel_all_for_event

    event.status = EventStatus.CANCELLED
    event.updated_by = actor.id
    await db.flush()
    cancelled = await cancel_all_for_event(db, actor=actor, event=event, reason=reason)
    await _audit(
        db, actor=actor, action="event.cancel", event=event, reason=reason, bookings=cancelled
    )
    return event


# ------------------------------------------------------------------------------- slots


def _editable(event: Event) -> None:
    if event.status in (EventStatus.CANCELLED, EventStatus.COMPLETED):
        raise ConflictError("This event can no longer be changed.", code="event_final")


async def add_slot(
    db: AsyncSession, *, actor: User, event: Event, body: schemas.SlotInput
) -> EventSlot:
    _editable(event)
    _check_slot_times(body.starts_at, body.ends_at)
    _check_slot_capacity(body.capacity, event.price_minor)
    slot = EventSlot(event_id=event.id, **body.model_dump())
    db.add(slot)
    await db.flush()
    await _audit(
        db,
        actor=actor,
        action="event_slot.create",
        event=event,
        target_type="event_slot",
        target_id=slot.id,
    )
    return slot


async def _locked_slot(db: AsyncSession, *, event: Event, slot_id: uuid.UUID) -> EventSlot:
    slot = await db.scalar(
        select(EventSlot)
        .where(EventSlot.id == slot_id, EventSlot.event_id == event.id)
        .with_for_update()
    )
    if slot is None:
        raise NotFoundError("Slot not found.")
    return slot


async def update_slot(
    db: AsyncSession, *, actor: User, event: Event, slot_id: uuid.UUID, body: schemas.SlotUpdate
) -> EventSlot:
    _editable(event)
    slot = await _locked_slot(db, event=event, slot_id=slot_id)
    changes = body.model_dump(exclude_unset=True)
    starts = changes.get("starts_at") or slot.starts_at
    ends = changes.get("ends_at") or slot.ends_at
    _check_slot_times(starts, ends)
    if "capacity" in changes:
        capacity = changes["capacity"]
        _check_slot_capacity(capacity, event.price_minor)
        if capacity is not None and capacity < slot.seats_confirmed + slot.seats_held:
            raise ConflictError(
                "That is fewer places than are already taken or held.",
                code="capacity_below_taken",
            )
    for key, value in changes.items():
        if key in ("starts_at", "ends_at", "position") and value is None:
            continue
        setattr(slot, key, value)
    await db.flush()
    await _audit(
        db,
        actor=actor,
        action="event_slot.update",
        event=event,
        target_type="event_slot",
        target_id=slot.id,
        fields=sorted(changes),
    )
    return slot


async def delete_slot(db: AsyncSession, *, actor: User, event: Event, slot_id: uuid.UUID) -> None:
    _editable(event)
    slot = await _locked_slot(db, event=event, slot_id=slot_id)
    from app.modules.bookings.models import Booking

    if slot.seats_confirmed or slot.seats_held:
        raise ConflictError("This slot has bookings.", code="slot_has_bookings")
    if (await db.scalar(select(Booking.id).where(Booking.slot_id == slot.id).limit(1))) is not None:
        raise ConflictError("This slot has bookings.", code="slot_has_bookings")
    remaining = await db.scalar(
        select(func.count()).select_from(EventSlot).where(EventSlot.event_id == event.id)
    )
    if event.status != EventStatus.DRAFT and (remaining or 0) <= 1:
        raise ConflictError("A published event needs at least one slot.", code="last_slot")
    await _audit(
        db,
        actor=actor,
        action="event_slot.delete",
        event=event,
        target_type="event_slot",
        target_id=slot.id,
    )
    await db.delete(slot)
    await db.flush()


# --------------------------------------------------------------------------- questions


def _check_question(
    kind: QuestionKind, options: list[schemas.ChoiceOption] | None
) -> list[dict[str, Any]] | None:
    if kind in (QuestionKind.CHOICE, QuestionKind.MULTI_CHOICE):
        if not options:
            raise ValidationError("A choice question needs options.", code="options_required")
        values = [o.value for o in options]
        if len(set(values)) != len(values):
            raise ValidationError("Option values must be different.", code="duplicate_options")
        return [o.model_dump() for o in options]
    if options:
        raise ValidationError("Only choice questions have options.", code="options_not_allowed")
    return None


async def add_question(
    db: AsyncSession, *, actor: User, event: Event, body: schemas.QuestionCreate
) -> EventQuestion:
    _editable(event)
    exists = await db.scalar(
        select(EventQuestion.id).where(
            EventQuestion.event_id == event.id, EventQuestion.key == body.key
        )
    )
    if exists is not None:
        raise ConflictError("A question with that key already exists.", code="key_taken")
    question = EventQuestion(
        event_id=event.id,
        key=body.key,
        label=body.label,
        kind=body.kind,
        options=_check_question(body.kind, body.options),
        required=body.required,
        asked_of=body.asked_of,
        position=body.position,
    )
    db.add(question)
    await db.flush()
    await _audit(
        db,
        actor=actor,
        action="event_question.create",
        event=event,
        target_type="event_question",
        target_id=question.id,
        key=body.key,
    )
    return question


async def _question(db: AsyncSession, *, event: Event, question_id: uuid.UUID) -> EventQuestion:
    q = await db.scalar(
        select(EventQuestion).where(
            EventQuestion.id == question_id, EventQuestion.event_id == event.id
        )
    )
    if q is None:
        raise NotFoundError("Question not found.")
    return q


async def update_question(
    db: AsyncSession,
    *,
    actor: User,
    event: Event,
    question_id: uuid.UUID,
    body: schemas.QuestionUpdate,
) -> EventQuestion:
    _editable(event)
    q = await _question(db, event=event, question_id=question_id)
    changes = body.model_dump(exclude_unset=True)
    if "options" in changes:
        q.options = _check_question(q.kind, body.options)
    for key in ("label", "required", "asked_of", "position"):
        if key in changes and changes[key] is not None:
            setattr(q, key, changes[key])
    await db.flush()
    await _audit(
        db,
        actor=actor,
        action="event_question.update",
        event=event,
        target_type="event_question",
        target_id=q.id,
        fields=sorted(changes),
    )
    return q


async def delete_question(
    db: AsyncSession, *, actor: User, event: Event, question_id: uuid.UUID
) -> None:
    _editable(event)
    from app.modules.bookings.models import BookingAnswer

    q = await _question(db, event=event, question_id=question_id)
    if (
        await db.scalar(select(BookingAnswer.id).where(BookingAnswer.question_id == q.id).limit(1))
    ) is not None:
        raise ConflictError("People have already answered this question.", code="question_answered")
    await _audit(
        db,
        actor=actor,
        action="event_question.delete",
        event=event,
        target_type="event_question",
        target_id=q.id,
        key=q.key,
    )
    await db.delete(q)
    await db.flush()


# ---------------------------------------------------------------------------- consents


async def add_consent(
    db: AsyncSession, *, actor: User, event: Event, body: schemas.ConsentCreate
) -> EventConsent:
    _editable(event)
    exists = await db.scalar(
        select(EventConsent.id).where(
            EventConsent.event_id == event.id, EventConsent.key == body.key
        )
    )
    if exists is not None:
        raise ConflictError("A consent with that key already exists.", code="key_taken")
    consent = EventConsent(event_id=event.id, key=body.key, text=body.text, required=body.required)
    db.add(consent)
    await db.flush()
    await _audit(
        db,
        actor=actor,
        action="event_consent.create",
        event=event,
        target_type="event_consent",
        target_id=consent.id,
        key=body.key,
    )
    return consent


async def _consent(db: AsyncSession, *, event: Event, consent_id: uuid.UUID) -> EventConsent:
    c = await db.scalar(
        select(EventConsent).where(EventConsent.id == consent_id, EventConsent.event_id == event.id)
    )
    if c is None:
        raise NotFoundError("Consent not found.")
    return c


async def update_consent(
    db: AsyncSession,
    *,
    actor: User,
    event: Event,
    consent_id: uuid.UUID,
    body: schemas.ConsentUpdate,
) -> EventConsent:
    _editable(event)
    c = await _consent(db, event=event, consent_id=consent_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("text") is not None and changes["text"] != c.text:
        c.text = changes["text"]
        c.version += 1  # people who accepted the old words are not taken to have accepted these
    if changes.get("required") is not None:
        c.required = changes["required"]
    await db.flush()
    await _audit(
        db,
        actor=actor,
        action="event_consent.update",
        event=event,
        target_type="event_consent",
        target_id=c.id,
        version=c.version,
    )
    return c


async def delete_consent(
    db: AsyncSession, *, actor: User, event: Event, consent_id: uuid.UUID
) -> None:
    _editable(event)
    from app.modules.bookings.models import BookingConsent

    c = await _consent(db, event=event, consent_id=consent_id)
    if (
        await db.scalar(select(BookingConsent.id).where(BookingConsent.consent_id == c.id).limit(1))
    ) is not None:
        raise ConflictError("People have already accepted this.", code="consent_accepted")
    await _audit(
        db,
        actor=actor,
        action="event_consent.delete",
        event=event,
        target_type="event_consent",
        target_id=c.id,
        key=c.key,
    )
    await db.delete(c)
    await db.flush()


# ------------------------------------------------------------------------------ series


async def create_series(
    db: AsyncSession, *, actor: User, body: schemas.SeriesCreate
) -> EventSeries:
    if body.organization_id is not None:
        await get_active_organization(db, organization_id=body.organization_id)
    await _require_can_run(db, user=actor, organization_id=body.organization_id)
    series = EventSeries(
        organization_id=body.organization_id,
        title=body.title,
        description=body.description,
        created_by=actor.id,
    )
    db.add(series)
    await db.flush()
    await record_audit(
        db,
        actor_user_id=actor.id,
        action="event_series.create",
        target_type="event_series",
        target_id=series.id,
        context=_org_context(body.organization_id),
    )
    return series


async def series_detail(
    db: AsyncSession, *, series_id: uuid.UUID, viewer: User | None
) -> schemas.SeriesDetail:
    series = await db.get(EventSeries, series_id)
    if series is None:
        raise NotFoundError("Series not found.")
    roles = await access.event_roles(db, user=viewer, organization_id=series.organization_id)
    is_manager = bool(roles & access.MANAGER_ROLES)
    events = (
        await db.scalars(
            select(Event).where(Event.series_id == series_id).order_by(Event.round_number)
        )
    ).all()
    rounds = [
        schemas.SeriesRound(
            id=e.id,
            round_number=e.round_number or 0,
            title=e.title,
            starts_at=e.starts_at,
            status=e.status,
        )
        for e in events
        if access.can_see(e, signed_in=viewer is not None, is_manager=is_manager)
    ]
    if not rounds and not is_manager:
        raise NotFoundError("Series not found.")
    return schemas.SeriesDetail(
        id=series.id,
        organization_id=series.organization_id,
        title=series.title,
        description=series.description,
        rounds=rounds,
    )


async def list_my_series(db: AsyncSession, *, user: User) -> list[EventSeries]:
    platform, orgs = await _managed_scope(db, user)
    stmt = select(EventSeries)
    if not platform:
        if not orgs:
            return []
        stmt = stmt.where(EventSeries.organization_id.in_(orgs))
    return list((await db.scalars(stmt.order_by(EventSeries.title).limit(200))).all())
