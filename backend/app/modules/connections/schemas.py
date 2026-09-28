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
