import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.connections.models import ConnectionStatus


class ConnectionRequestCreate(BaseModel):
    addressee_id: uuid.UUID


class ConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_id: uuid.UUID
    addressee_id: uuid.UUID
    status: ConnectionStatus
    created_at: datetime


class ConnectionListItem(ConnectionResponse):
    """
    A connection as seen by one of its two parties. `other_*` describe the OTHER person.
    Only their name is exposed here (never company, bio or any other profile field): both
    sides of a connection row already know who the other person is, because one of them
    asked and the other answered. Full profile data still goes through the privacy rules.
    """

    other_user_id: uuid.UUID
    other_profile_id: uuid.UUID | None
    other_full_name: str | None
