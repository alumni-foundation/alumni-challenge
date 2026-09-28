import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.modules.alumni.models import AlumniProfile
from app.modules.connections.models import Connection, ConnectionStatus


async def _find_existing_pair(
    db: AsyncSession, *, user_a: uuid.UUID, user_b: uuid.UUID
) -> Connection | None:
    """
    Checks BOTH directions. The unique constraint on the table only
    covers (requester_id, addressee_id) in one order — without this
    check, A could request B, and B could separately "request" A,
    creating two rows for what should be a single relationship.
    """
    stmt = select(Connection).where(
        ((Connection.requester_id == user_a) & (Connection.addressee_id == user_b))
        | ((Connection.requester_id == user_b) & (Connection.addressee_id == user_a))
    )
    return await db.scalar(stmt)


async def send_request(
    db: AsyncSession, *, requester_id: uuid.UUID, addressee_id: uuid.UUID
) -> Connection:
    if requester_id == addressee_id:
        raise ValidationError("You cannot connect with yourself.")

    existing = await _find_existing_pair(db, user_a=requester_id, user_b=addressee_id)
    if existing is not None:
        if existing.status == ConnectionStatus.ACCEPTED:
            raise ConflictError("You are already connected.")
        if existing.status == ConnectionStatus.PENDING:
            raise ConflictError("A connection request is already pending.")
        if existing.status == ConnectionStatus.BLOCKED:
            raise ForbiddenError("Unable to send a connection request.")
        # DECLINED or REMOVED: allow a fresh request by resetting this row.
        existing.requester_id = requester_id
        existing.addressee_id = addressee_id
        existing.status = ConnectionStatus.PENDING
        await db.flush()
        return existing

    connection = Connection(
        requester_id=requester_id, addressee_id=addressee_id, status=ConnectionStatus.PENDING
    )
    db.add(connection)
    await db.flush()
    return connection


async def _get_owned_connection(
    db: AsyncSession, *, connection_id: uuid.UUID, user_id: uuid.UUID
) -> Connection:
    connection = await db.get(Connection, connection_id)
    if connection is None or user_id not in (connection.requester_id, connection.addressee_id):
        raise NotFoundError("Connection not found.")
    return connection


async def accept_request(
    db: AsyncSession, *, connection_id: uuid.UUID, current_user_id: uuid.UUID
) -> Connection:
    connection = await _get_owned_connection(
        db, connection_id=connection_id, user_id=current_user_id
    )
    if connection.addressee_id != current_user_id:
        raise ForbiddenError("Only the recipient can accept a connection request.")
    if connection.status != ConnectionStatus.PENDING:
        raise ConflictError("This request is no longer pending.")
    connection.status = ConnectionStatus.ACCEPTED
    await db.flush()
    return connection


async def decline_request(
    db: AsyncSession, *, connection_id: uuid.UUID, current_user_id: uuid.UUID
) -> Connection:
    connection = await _get_owned_connection(
        db, connection_id=connection_id, user_id=current_user_id
    )
    if connection.addressee_id != current_user_id:
        raise ForbiddenError("Only the recipient can decline a connection request.")
    if connection.status != ConnectionStatus.PENDING:
        raise ConflictError("This request is no longer pending.")
    connection.status = ConnectionStatus.DECLINED
    await db.flush()
    return connection


async def remove_connection(
    db: AsyncSession, *, connection_id: uuid.UUID, current_user_id: uuid.UUID
) -> None:
    connection = await _get_owned_connection(
        db, connection_id=connection_id, user_id=current_user_id
    )
    connection.status = ConnectionStatus.REMOVED
    await db.flush()


async def list_my_connections(
    db: AsyncSession, *, user_id: uuid.UUID, status_filter: ConnectionStatus | None = None
) -> list[Connection]:
    stmt = select(Connection).where(
        (Connection.requester_id == user_id) | (Connection.addressee_id == user_id)
    )
    if status_filter is not None:
        stmt = stmt.where(Connection.status == status_filter)
    result = await db.scalars(stmt)
    return list(result.all())


async def list_my_connections_detailed(
    db: AsyncSession, *, user_id: uuid.UUID
) -> list[dict[str, object]]:
    """
    Connections for the caller with the other person's name attached (one extra query,
    not one per row). Blocked rows are left out: the person who was blocked must not be
    able to tell.
    """
    stmt = (
        select(Connection)
        .where(
            ((Connection.requester_id == user_id) | (Connection.addressee_id == user_id))
            & (Connection.status != ConnectionStatus.BLOCKED)
        )
        .order_by(Connection.created_at.desc(), Connection.id)
    )
    connections = list((await db.scalars(stmt)).all())
    other_ids = {
        c.addressee_id if c.requester_id == user_id else c.requester_id for c in connections
    }
    profiles: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
    if other_ids:
        rows = await db.execute(
            select(AlumniProfile.user_id, AlumniProfile.id, AlumniProfile.full_name).where(
                AlumniProfile.user_id.in_(other_ids)
            )
        )
        profiles = {uid: (pid, name) for uid, pid, name in rows.all()}

    items: list[dict[str, object]] = []
    for c in connections:
        other_id = c.addressee_id if c.requester_id == user_id else c.requester_id
        profile = profiles.get(other_id)
        items.append(
            {
                "id": c.id,
                "requester_id": c.requester_id,
                "addressee_id": c.addressee_id,
                "status": c.status,
                "created_at": c.created_at,
                "other_user_id": other_id,
                "other_profile_id": profile[0] if profile else None,
                "other_full_name": profile[1] if profile else None,
            }
        )
    return items
