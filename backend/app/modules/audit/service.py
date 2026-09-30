import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLogEntry


async def record(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None = None,
    context: dict[str, Any] | None = None,
) -> AuditLogEntry:
    """
    Adds the entry to the SAME session/transaction as the action it's
    recording, deliberately — no separate commit here. If the action
    that triggered this gets rolled back, the audit entry rolls back
    with it, which is correct: an audit log for something that never
    actually happened would be worse than no entry at all.
    """
    entry = AuditLogEntry(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        context=context or {},
    )
    db.add(entry)
    await db.flush()
    return entry


async def list_entries(
    db: AsyncSession,
    *,
    organization_ids: set[uuid.UUID] | None,
    limit: int,
    offset: int,
) -> list[AuditLogEntry]:
    """
    organization_ids=None means unrestricted (platform admin). Otherwise
    only rows whose context carries one of the caller's organization_ids
    are returned — an entry with no organization_id in its context is
    invisible to an org-scoped admin, by design (see router docstring).
    """
    stmt = select(AuditLogEntry).order_by(AuditLogEntry.created_at.desc(), AuditLogEntry.id)
    if organization_ids is not None:
        org_strings = [str(org_id) for org_id in organization_ids]
        stmt = stmt.where(AuditLogEntry.context["organization_id"].astext.in_(org_strings))
    stmt = stmt.limit(limit).offset(offset)
    return list((await db.scalars(stmt)).all())
