import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db_session
from app.modules.connections import schemas, service
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/connections", tags=["connections"])


@router.post("", response_model=schemas.ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection_request(
    body: schemas.ConnectionRequestCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> object:
    connection = await service.send_request(
        db, requester_id=current_user.id, addressee_id=body.addressee_id
    )
    await db.commit()
    return connection


@router.get("", response_model=list[schemas.ConnectionListItem])
async def list_connections(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, object]]:
    return await service.list_my_connections_detailed(db, user_id=current_user.id)


@router.patch("/{connection_id}/accept", response_model=schemas.ConnectionResponse)
async def accept_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> object:
    connection = await service.accept_request(
        db, connection_id=connection_id, current_user_id=current_user.id
    )
    await db.commit()
    return connection


@router.patch("/{connection_id}/decline", response_model=schemas.ConnectionResponse)
async def decline_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> object:
    connection = await service.decline_request(
        db, connection_id=connection_id, current_user_id=current_user.id
    )
    await db.commit()
    return connection


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    await service.remove_connection(
        db, connection_id=connection_id, current_user_id=current_user.id
    )
    await db.commit()
