import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.alumni.models import ProfileVisibility, VerificationStatus


class AlumniProfileCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    bio: str | None = Field(default=None, max_length=2000)
    graduation_year: int | None = Field(default=None, ge=1900, le=2100)
    school_id: uuid.UUID | None = None
    country: str | None = Field(default=None, max_length=100)
    profession: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    profile_visibility: ProfileVisibility = ProfileVisibility.MEMBERS_ONLY


class AlumniProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    bio: str | None = Field(default=None, max_length=2000)
    graduation_year: int | None = Field(default=None, ge=1900, le=2100)
    school_id: uuid.UUID | None = None
    country: str | None = Field(default=None, max_length=100)
    profession: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    profile_visibility: ProfileVisibility | None = None


class AlumniProfileResponse(BaseModel):
    """
    Field-by-field visibility is enforced BEFORE this schema is built —
    see alumni/service.py's build_profile_response. Fields the viewer
    isn't allowed to see are omitted at that stage (set to None here),
    not filtered client-side. A None here can mean either "not set" or
    "not visible to you" — the API never distinguishes the two, which
    is itself a privacy property: a viewer can't probe whether a
    hidden field has a value.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    bio: str | None
    graduation_year: int | None
    school_id: uuid.UUID | None
    country: str | None
    profession: str | None
    company: str | None
    verification_status: VerificationStatus
    profile_visibility: ProfileVisibility
    avatar_file_id: uuid.UUID | None
    created_at: datetime
    skills: list[str] = []
    interests: list[str] = []
    # Number of verified same-school alumni who vouched. Hidden from anonymous viewers.
    vouch_count: int | None = None


class AlumniProfileSummary(BaseModel):
    """Lighter shape for directory listings."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    school_id: uuid.UUID | None
    graduation_year: int | None
    verification_status: VerificationStatus


class VerifyProfileRequest(BaseModel):
    verified: bool


class SetTagsRequest(BaseModel):
    """Full replacement list of skills or interests: trimmed, lowercased, de-duplicated."""

    names: list[str] = Field(max_length=30)

    @field_validator("names")
    @classmethod
    def normalise(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in values:
            name = " ".join(raw.split()).lower()
            if not 1 <= len(name) <= 50:
                raise ValueError("Each name must be between 1 and 50 characters.")
            if name not in cleaned:
                cleaned.append(name)
        return cleaned
