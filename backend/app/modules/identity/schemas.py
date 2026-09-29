import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    confirm_18_or_older: bool = Field(
        description="Must be true — self-attestation that the user is 18 or older. "
        "The platform does not accept registrations from minors."
    )

    @field_validator("confirm_18_or_older")
    @classmethod
    def must_confirm_age(cls, value: bool) -> bool:
        if not value:
            raise ValueError("You must confirm you are 18 or older to register.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    status: str
    email_verified_at: datetime | None
    created_at: datetime


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_label: str | None
    ip_address: str | None
    created_at: datetime
    last_used_at: datetime


class VerifyEmailConfirmRequest(BaseModel):
    token: str


class PasswordForgotRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=128)


class MessageResponse(BaseModel):
    message: str
