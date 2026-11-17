import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.modules.work_log.models import TEXT_MAX, WorkLogKind

# Trimmed first, then 1 to 500 characters, so a line of spaces is rejected.
EntryText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TEXT_MAX)
]


class EntryCreate(BaseModel):
    """No date here on purpose: the server decides the day. Anything extra is a 422."""

    model_config = ConfigDict(extra="forbid")

    kind: WorkLogKind
    text: EntryText


class EntryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: EntryText


class EntryResponse(BaseModel):
    id: uuid.UUID
    kind: WorkLogKind
    text: str
    entry_date: date
    created_at: datetime
    completed_at: datetime | None
    # True while it is still the day the line was added (Nairobi time), decided by the server.
    editable: bool


class TeamEntryResponse(BaseModel):
    id: uuid.UUID
    author_user_id: uuid.UUID
    author_name: str
    author_email: str
    kind: WorkLogKind
    text: str
    entry_date: date
    created_at: datetime
    completed_at: datetime | None


class PersonResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
