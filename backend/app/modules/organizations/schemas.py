import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.core.permissions.roles import Role
from app.modules.alumni.models import VerificationMethod, VerificationStatus
from app.modules.files.urls import public_file_path
from app.modules.identity.models import UserStatus
from app.modules.memberships.models import MembershipStatus
from app.modules.organizations.models import OrganizationStatus, OrganizationType

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


class OrganizationCreate(BaseModel):
    type: OrganizationType
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("Slug may contain lowercase letters, digits and single hyphens only.")
        return v


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: OrganizationType
    name: str
    slug: str
    description: str | None
    status: OrganizationStatus
    logo_file_id: uuid.UUID | None = None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def logo_url(self) -> str | None:
        """A permanent public address: a new logo gets a new address."""
        return public_file_path(self.logo_file_id) if self.logo_file_id else None


class MembershipCreate(BaseModel):
    user_id: uuid.UUID
    role: Role


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID | None
    role: Role


class EmailDomainCreate(BaseModel):
    domain: str

    @field_validator("domain")
    @classmethod
    def valid_domain(cls, v: str) -> str:
        v = v.strip().lower()
        if not _DOMAIN_RE.match(v):
            raise ValueError("Enter a valid domain such as school.ac.ke.")
        return v


class EmailDomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    domain: str


class UserLookupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class UserLookupMatch(BaseModel):
    user_id: uuid.UUID
    full_name: str | None
    roles_in_organization: list[Role]
    verification_status: VerificationStatus | None


class UserLookupResponse(BaseModel):
    """`match` is null for every address that is not a member of this organization."""

    match: UserLookupMatch | None


class MemberListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: Role
    status: MembershipStatus
    account_status: UserStatus
    since: datetime


class RosterItem(BaseModel):
    """What a school admin needs to verify someone, and nothing else."""

    model_config = ConfigDict(from_attributes=True)

    profile_id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    graduation_year: int | None
    country: str | None
    verification_status: VerificationStatus
    verification_method: VerificationMethod | None
    email_verified: bool
    joined_at: datetime


class SetLogoRequest(BaseModel):
    file_id: uuid.UUID
