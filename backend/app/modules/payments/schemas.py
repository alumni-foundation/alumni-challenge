import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.modules.payments.models import MpesaKind, PaymentProvider

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


def _digits(v: str) -> str:
    v = v.strip()
    if not (v.isascii() and v.isdigit() and 4 <= len(v) <= 10):
        raise ValueError("A paybill or till number is 4 to 10 digits.")
    return v


class PaymentAccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Null means the platform's own account (platform admins only).
    organization_id: uuid.UUID | None = None
    label: Label
    mpesa_kind: MpesaKind
    shortcode_or_till: str

    _number = field_validator("shortcode_or_till")(_digits)


class PaymentAccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Label | None = None
    shortcode_or_till: str | None = None
    active: bool | None = None

    @field_validator("shortcode_or_till")
    @classmethod
    def _number(cls, v: str | None) -> str | None:
        return None if v is None else _digits(v)


class PaymentAccountOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    label: str
    provider: PaymentProvider
    mpesa_kind: MpesaKind
    shortcode_or_till: str
    currency: str
    active: bool


class PayeeInfo(BaseModel):
    """What a booker sees on the event: where to pay. Public numbers, nothing secret."""

    method: PaymentProvider
    kind: MpesaKind
    number: str
    payee_name: str = Field(description="The label the organizer gave this account.")
    currency: str
