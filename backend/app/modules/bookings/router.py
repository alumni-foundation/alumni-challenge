import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db_session
from app.modules.bookings import service
from app.modules.bookings.models import BookingStatus
from app.modules.bookings.schemas import (
    BookingCreate,
    BookingOut,
    CancelBookingRequest,
    ParticipantUpdate,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

events_router = APIRouter(prefix="/events", tags=["bookings"])
router = APIRouter(prefix="/bookings", tags=["bookings"])


@events_router.post(
    "/{event_id}/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED
)
async def create_booking(
    event_id: uuid.UUID,
    body: BookingCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> BookingOut:
    """
    Books places. Free events confirm straight away; paid events hold the places for
    `hold_minutes` while payment is made. Send a fresh `Idempotency-Key` per attempt and
    re-send the same one when retrying after a timeout: you will get the same booking back.
    """
    booking = await service.create_booking(
        db, user=user, event_id=event_id, body=body, idempotency_key=idempotency_key
    )
    out = await service.build_out(db, booking)
    await db.commit()
    return out


@router.get("", response_model=list[BookingOut])
async def my_bookings(
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    booking_status: BookingStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[BookingOut]:
    rows, total = await service.list_my_bookings(
        db, user=user, status=booking_status, limit=limit, offset=offset
    )
    response.headers["X-Total-Count"] = str(total)
    return [await service.build_out(db, b) for b in rows]


@router.get("/{booking_id}", response_model=BookingOut)
async def get_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> BookingOut:
    booking = await service.get_booking(db, booking_id=booking_id, viewer=user)
    return await service.build_out(db, booking)


@router.patch("/{booking_id}/participants/{position}", response_model=BookingOut)
async def update_participant(
    booking_id: uuid.UUID,
    position: int,
    body: ParticipantUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> BookingOut:
    booking = await service.update_participant(
        db, actor=user, booking_id=booking_id, position=position, body=body
    )
    out = await service.build_out(db, booking)
    await db.commit()
    return out


@router.post("/{booking_id}/cancel", response_model=BookingOut)
async def cancel_booking(
    booking_id: uuid.UUID,
    body: CancelBookingRequest | None = None,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> BookingOut:
    booking = await service.cancel_booking(
        db, actor=user, booking_id=booking_id, reason=body.reason if body else None
    )
    out = await service.build_out(db, booking)
    await db.commit()
    return out
