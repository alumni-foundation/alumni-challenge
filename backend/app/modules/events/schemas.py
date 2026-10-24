import re
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.bookings.schemas import BookingBrief
from app.modules.events.models import (
    MAX_PARTY_SIZE,
    EventCategory,
    EventStatus,
    EventVisibility,
    QuestionAskedOf,
    QuestionKind,
)
from app.modules.organizations.models import OrganizationType

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,59}$")
MAX_PRICE_MINOR = 100_000_000_00  # 100 million shillings, a sanity ceiling

Currency = Literal["KES"]
Money = Annotated[int, Field(ge=0, le=MAX_PRICE_MINOR)]


# ------------------------------------------------------------------------------ input


class SlotInput(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    capacity: int | None = Field(default=None, ge=0, le=100_000)
    position: int = Field(default=0, ge=0, le=1000)


class SlotUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    capacity: int | None = Field(default=None, ge=0, le=100_000)
    position: int | None = Field(default=None, ge=0, le=1000)


class EventCreate(BaseModel):
    organization_id: uuid.UUID | None = Field(
        default=None, description="null means the platform itself runs the event"
    )
    series_id: uuid.UUID | None = None
    round_number: int | None = Field(default=None, ge=1, le=100)
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    category: EventCategory
    visibility: EventVisibility = EventVisibility.PUBLIC
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    venue_name: str | None = Field(default=None, max_length=255)
    venue_address: str | None = Field(default=None, max_length=500)
    registration_opens_at: AwareDatetime | None = None
    registration_closes_at: AwareDatetime | None = None
    price_minor: Money = 0
    currency: Currency = "KES"
    max_party_size: int = Field(default=1, ge=1, le=MAX_PARTY_SIZE)
    hold_minutes: int = Field(default=15, ge=5, le=2880)
    waitlist_enabled: bool = False
    show_attendee_list: bool = True
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    refund_policy_text: str | None = Field(default=None, max_length=5000)
    reminder_hours_before: int = Field(default=24, ge=0, le=720)
    # Convenience: with no slots given, one unlabelled slot covering the whole event is made,
    # with this capacity (null = unlimited, allowed for free events only).
    capacity: int | None = Field(default=None, ge=0, le=100_000)
    slots: list[SlotInput] = Field(default_factory=list, max_length=50)


class EventUpdate(BaseModel):
    """Only fields that make sense to change. Organization, status and money-state never."""

    series_id: uuid.UUID | None = None
    round_number: int | None = Field(default=None, ge=1, le=100)
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    category: EventCategory | None = None
    visibility: EventVisibility | None = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    venue_name: str | None = Field(default=None, max_length=255)
    venue_address: str | None = Field(default=None, max_length=500)
    registration_opens_at: AwareDatetime | None = None
    registration_closes_at: AwareDatetime | None = None
    price_minor: Money | None = None
    currency: Currency | None = None
    max_party_size: int | None = Field(default=None, ge=1, le=MAX_PARTY_SIZE)
    hold_minutes: int | None = Field(default=None, ge=5, le=2880)
    waitlist_enabled: bool | None = None
    show_attendee_list: bool | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    refund_policy_text: str | None = Field(default=None, max_length=5000)
    reminder_hours_before: int | None = Field(default=None, ge=0, le=720)


class CancelEventRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class SetPosterRequest(BaseModel):
    file_id: uuid.UUID


class ChoiceOption(BaseModel):
    value: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_\-\.]+$")
    label: str = Field(min_length=1, max_length=200)


class QuestionCreate(BaseModel):
    key: str = Field(min_length=2, max_length=60)
    label: str = Field(min_length=1, max_length=300)
    kind: QuestionKind
    options: list[ChoiceOption] | None = Field(default=None, max_length=100)
    required: bool = False
    asked_of: QuestionAskedOf = QuestionAskedOf.BOOKER
    position: int = Field(default=0, ge=0, le=1000)

    @field_validator("key")
    @classmethod
    def valid_key(cls, v: str) -> str:
        if not _KEY_RE.match(v):
            raise ValueError(
                "Use lowercase letters, digits and underscores, starting with a letter."
            )
        return v


class QuestionUpdate(BaseModel):
    """The key and kind never change; delete and recreate while nobody has answered."""

    label: str | None = Field(default=None, min_length=1, max_length=300)
    options: list[ChoiceOption] | None = Field(default=None, max_length=100)
    required: bool | None = None
    asked_of: QuestionAskedOf | None = None
    position: int | None = Field(default=None, ge=0, le=1000)


class ConsentCreate(BaseModel):
    key: str = Field(min_length=2, max_length=60)
    text: str = Field(min_length=1, max_length=5000)
    required: bool = True

    @field_validator("key")
    @classmethod
    def valid_key(cls, v: str) -> str:
        if not _KEY_RE.match(v):
            raise ValueError(
                "Use lowercase letters, digits and underscores, starting with a letter."
            )
        return v


class ConsentUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=5000)
    required: bool | None = None


class SeriesCreate(BaseModel):
    organization_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)


# ---------------------------------------------------------------------------- output


class OrganizerInfo(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    type: OrganizationType


class RegistrationInfo(BaseModel):
    """Whether booking is possible now. `state` is one of: draft, cancelled, ended, closed,
    not_open_yet, open."""

    state: str
    opens_at: datetime | None
    closes_at: datetime | None


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str | None
    starts_at: datetime
    ends_at: datetime
    capacity: int | None
    seats_confirmed: int
    seats_held: int
    position: int
    spots_left: int | None
    availability: str


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    label: str
    kind: QuestionKind
    options: list[dict[str, Any]] | None
    required: bool
    asked_of: QuestionAskedOf
    position: int


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    text: str
    version: int
    required: bool


class SeriesOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    title: str
    description: str | None


class SeriesRound(BaseModel):
    id: uuid.UUID
    round_number: int
    title: str
    starts_at: datetime
    status: EventStatus


class SeriesDetail(SeriesOut):
    rounds: list[SeriesRound]


class SeriesInfo(BaseModel):
    id: uuid.UUID
    title: str
    round_number: int


class EventSummary(BaseModel):
    id: uuid.UUID
    title: str
    category: EventCategory
    status: EventStatus
    visibility: EventVisibility
    starts_at: datetime
    ends_at: datetime
    venue_name: str | None
    poster_url: str | None
    organizer: OrganizerInfo | None
    price_minor: int
    currency: str
    max_party_size: int
    series: SeriesInfo | None
    going_count: int
    spots_left: int | None
    availability: str
    registration: RegistrationInfo


class EventDetail(EventSummary):
    description: str | None
    venue_address: str | None
    contact_email: str | None
    contact_phone: str | None
    refund_policy_text: str | None
    waitlist_enabled: bool
    show_attendee_list: bool
    reminder_hours_before: int
    hold_minutes: int
    slots: list[SlotOut]
    questions: list[QuestionOut]
    consents: list[ConsentOut]
    # True when the caller may run this event (tells the app whether to show organizer tools).
    can_manage: bool
    # The caller's own current booking for this event (null when signed out or not booked).
    my_booking: BookingBrief | None = None
