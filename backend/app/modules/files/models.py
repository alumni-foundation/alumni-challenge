from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.enum_column import str_enum
from app.infrastructure.database.mixins import UUIDPrimaryKeyMixin
from app.infrastructure.database.session import Base


class FileVisibility(enum.StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class File(UUIDPrimaryKeyMixin, Base):
    """
    Metadata only — the actual bytes live in object storage (Cloudflare
    R2, per Phase 0's tool choice). Full upload flow (signed URLs, MIME
    validation, image variants) is built out in Phase 4; this table
    exists now only because Organization.logo_file_id needs somewhere
    valid to point.
    """

    __tablename__ = "files"

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    visibility: Mapped[FileVisibility] = mapped_column(
        str_enum(FileVisibility, name="file_visibility"),
        nullable=False,
        default=FileVisibility.PRIVATE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
