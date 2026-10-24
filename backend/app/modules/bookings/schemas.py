import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.bookings.models import BookingStatus
from app.modules.events.models import EventCategory

_PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")


def clean_name(value: str) -> str:
    name = " ".join(value.split())
    if not 1 <= len(name) <= 120:
        raise ValueError("A name must be between 1 and 120 characters.")
    return name


def clean_phone(value: str) -> str:
    phone = re.sub(r"[\s\-().]", "", value)
    if not _PHONE_RE.match(phone):
        raise ValueError("Enter a phone number with 7 to 15 digits, for example +254700000000.")
    return phone


class ParticipantInput(BaseModel):
    full_name: str = Field(max_length=300)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    listed: bool = True

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return clean_name(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return clean_phone(v) if v else None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return v.lower() if v else None


class AnswerInput(BaseModel):
    question_key: str = Field(min_length=2, max_length=60)
    # Which participant the answer is for: 1 is the booker. Booker-level questions use 1.
    position: int = Field(default=1, ge=1, le=4)
    value: Any


class BookingCreate(BaseModel):
    slot_id: uuid.UUID
    participants: list[ParticipantInput] = Field(min_length=1, max_length=4)
    answers: list[AnswerInput] = Field(default_factory=list, max_length=200)
    accepted_consents: list[str] = Field(default_factory=list, max_length=50)
    # Needed when other people are named: the booker confirms they may share these details.
    others_consent_confirmed: bool = False


class ParticipantUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=300)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    listed: bool | None = None

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return clean_name(v) if v is not None else None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return clean_phone(v) if v else None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return v.lower() if v else None


class CancelBookingRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ParticipantOut(BaseModel):
    position: int
    full_name: str
    email: str | None
    phone: str | None
    listed: bool
    # True once that person has attached the ticket to their own account.
    claimed: bool


class AnswerOut(BaseModel):
    question_key: str
    position: int
    value: Any


class BookingConsentOut(BaseModel):
    key: str
    version: int
    accepted_at: datetime


class BookingEventInfo(BaseModel):
    id: uuid.UUID
    title: str
    category: EventCategory
    starts_at: datetime
    ends_at: datetime
    venue_name: str | None
    poster_url: str | None


class BookingSlotInfo(BaseModel):
    id: uuid.UUID
    label: str | None
    starts_at: datetime
    ends_at: datetime


class BookingOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: BookingStatus
    event: BookingEventInfo
    slot: BookingSlotInfo
    party_size: int
    unit_price_minor: int
    amount_minor: int
    currency: str
    hold_expires_at: datetime | None
    created_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    can_cancel: bool
    participants: list[ParticipantOut]
    answers: list[AnswerOut]
    consents: list[BookingConsentOut]


class BookingBrief(BaseModel):
    """The caller's own booking, shown on the event page."""

    id: uuid.UUID
    reference: str
    status: BookingStatus
    slot_id: uuid.UUID
    party_size: int
    hold_expires_at: datetime | None
