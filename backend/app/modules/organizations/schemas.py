import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.permissions.roles import Role
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
    created_at: datetime


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
