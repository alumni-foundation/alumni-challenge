import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import rate_limit
from app.infrastructure.database.session import get_db_session
from app.modules.bookings import manual_payment, service
from app.modules.bookings.models import BookingStatus
from app.modules.bookings.schemas import (
    BookingCreate,
    BookingOut,
    CancelBookingRequest,
    MarkPaidRequest,
    MarkRefundedRequest,
    OrganizerCancelRequest,
    ParticipantUpdate,
    PaymentReferenceRequest,
    RejectPaymentRequest,
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


# ------------------------------------------------------------- paying by hand (manual M-Pesa)


@router.post("/{booking_id}/payment-reference", response_model=BookingOut)
async def send_payment_reference(
    booking_id: uuid.UUID,
    body: PaymentReferenceRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _limit: None = Depends(rate_limit("payment_code_ip", limit=30, window_seconds=3600)),
) -> BookingOut:
    """
    The booker pastes the M-Pesa code from their payment message. The organizer then confirms
    it. A code can belong to one booking only (409 `payment_code_used` otherwise). Sending the
    same code twice is harmless. Limited per account, per booking and per address.
    """
    booking = await manual_payment.submit_code(db, user=user, booking_id=booking_id, code=body.code)
    out = await service.build_out(db, booking)
    await db.commit()
    return out


@router.post("/{booking_id}/confirm-manual", response_model=BookingOut)
async def confirm_manual_payment(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> BookingOut:
    """
    An organization admin confirms the payment was received. Confirming again changes nothing.
    If the hold had run out and the places are gone, the booking stays expired and the payment
    moves to `needs_refund` instead: read `payment.state` in the answer.
    """
    booking = await manual_payment.confirm(db, actor=user, booking_id=booking_id)
    out = await service.build_out(db, booking)
    await db.commit()
    return out


@router.post("/{booking_id}/mark-paid", response_model=BookingOut)
async def mark_booking_paid(
    booking_id: uuid.UUID,
    body: MarkPaidRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> BookingOut:
    """
    An organization admin says the money arrived without an M-Pesa code (cash, a transfer, a code
    never sent). A written reason is required and audited. Settles like a confirmed code, late
    payment rules included. Doing it again changes nothing.
    """
    booking = await manual_payment.mark_paid(
        db, actor=user, booking_id=booking_id, reason=body.reason
    )
    out = await service.build_out(db, booking)
    await db.commit()
    return out


@router.post("/{booking_id}/reject-manual", response_model=BookingOut)
async def reject_manual_payment(
    booking_id: uuid.UUID,
    body: RejectPaymentRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> BookingOut:
    """The code did not match a payment. The booker is emailed and may send another code."""
    booking = await manual_payment.reject(db, actor=user, booking_id=booking_id, reason=body.reason)
    out = await service.build_out(db, booking)
    await db.commit()
    return out


@router.post("/{booking_id}/mark-refunded", response_model=BookingOut)
async def mark_payment_refunded(
    booking_id: uuid.UUID,
    body: MarkRefundedRequest | None = None,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> BookingOut:
    """The organizer sent the money back by hand. Only for payments in `needs_refund`."""
    booking = await manual_payment.mark_refunded(
        db, actor=user, booking_id=booking_id, note=body.note if body else None
    )
    out = await service.build_out(db, booking)
    await db.commit()
    return out


@router.post("/{booking_id}/organizer-cancel", response_model=BookingOut)
async def organizer_cancel_booking(
    booking_id: uuid.UUID,
    body: OrganizerCancelRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> BookingOut:
    """Cancels a booking (organization admins). `refund: true` queues a paid one for refund."""
    booking = await manual_payment.organizer_cancel(
        db, actor=user, booking_id=booking_id, reason=body.reason, refund=body.refund
    )
    out = await service.build_out(db, booking)
    await db.commit()
    return out
