import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.files.models import FilePurpose, FileVisibility


class FileResponse(BaseModel):
    """
    Describes a stored file. The storage key is never part of this: it is an internal
    detail, and what the client asked for (file name, claimed type) is not kept at all.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purpose: FilePurpose
    visibility: FileVisibility
    organization_id: uuid.UUID | None
    mime_type: str
    size_bytes: int
    width: int
    height: int
    created_at: datetime
