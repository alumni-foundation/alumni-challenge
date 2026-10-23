import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.moderation.models import ReportStatus, ReportTargetType


class ReportCreate(BaseModel):
    target_type: ReportTargetType
    target_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A reason is required.")
        return value


class ReportReview(BaseModel):
    status: ReportStatus


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reporter_user_id: uuid.UUID
    target_type: ReportTargetType
    target_id: uuid.UUID
    reason: str
    status: ReportStatus
    reviewed_by: uuid.UUID | None
    created_at: datetime
    resolved_at: datetime | None
