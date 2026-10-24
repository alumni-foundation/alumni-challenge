"""Tickets for the people going, and the organizer's day: roster, tee sheet, check-in, messages."""

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import rate_limit
from app.infrastructure.database.session import get_db_session
from app.modules.bookings import organizer, service, tickets
from app.modules.bookings.models import BookingStatus
from app.modules.bookings.schemas import (
    CheckInRequest,
    CheckInResult,
    ClaimTicketRequest,
    MessageCreate,
    MessageOut,
    RegistrationRow,
    TeeSheetSlot,
    TicketOut,
)
from app.modules.events import access
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

NO_STORE = {"Cache-Control": "no-store"}

tickets_router = APIRouter(prefix="/tickets", tags=["tickets"])
booking_tickets_router = APIRouter(prefix="/bookings", tags=["tickets"])
organizer_router = APIRouter(prefix="/events", tags=["organizer"])


# ----------------------------------------------------------------------------- tickets


@tickets_router.get("/mine", response_model=list[TicketOut])
async def my_tickets(
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> list[TicketOut]:
    """Tickets for events that have not ended: those in bookings I made and those I claimed."""
    response.headers.update(NO_STORE)
    return [tickets.ticket_out(v) for v in await tickets.my_tickets(db, user=user)]


@tickets_router.post("/claim", response_model=TicketOut)
async def claim_ticket(
    body: ClaimTicketRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _limit: None = Depends(rate_limit("ticket_claim", limit=30, window_seconds=3600)),
) -> TicketOut:
    """Attach the ticket from your emailed link to your own account. Repeating it is harmless."""
    view = await tickets.claim(db, user=user, code=body.code)
    out = tickets.ticket_out(view)
    await db.commit()
    response.headers.update(NO_STORE)
    return out


@tickets_router.get("/{code}", response_model=TicketOut)
async def get_ticket(
    code: str,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    _limit: None = Depends(rate_limit("ticket_view", limit=600, window_seconds=900)),
) -> TicketOut:
    """
    The ticket page behind a QR code or an emailed link. No sign-in: the code is the
    credential, so a player without an account can use it. A wrong or revoked code is a 404.
    Per IP, 600 requests per 15 minutes: generous enough for a whole venue on one wifi network.
    """
    ticket = await tickets.find_by_code(db, code)
    out = tickets.ticket_out(await tickets.load_view(db, ticket))
    response.headers.update(NO_STORE)
    return out


@booking_tickets_router.get("/{booking_id}/tickets", response_model=list[TicketOut])
async def booking_tickets(
    booking_id: uuid.UUID,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> list[TicketOut]:
    """The tickets of a booking: for the booker and the event's organizers."""
    booking = await service.get_booking(db, booking_id=booking_id, viewer=user)
    response.headers.update(NO_STORE)
    return [tickets.ticket_out(v) for v in await tickets.tickets_of_booking(db, booking)]


@booking_tickets_router.post("/{booking_id}/tickets/{position}/reissue", response_model=TicketOut)
async def reissue_ticket(
    booking_id: uuid.UUID,
    position: int,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> TicketOut:
    """Kills the old QR of one person's ticket and returns a new one (if a code leaked)."""
    booking = await service.get_booking(db, booking_id=booking_id, viewer=user)
    ticket = await tickets.reissue(db, actor=user, booking=booking, position=position)
    out = tickets.ticket_out(await tickets.load_view(db, ticket))
    await db.commit()
    response.headers.update(NO_STORE)
    return out


# --------------------------------------------------------------------- organizer's day


@organizer_router.get("/{event_id}/registrations", response_model=list[RegistrationRow])
async def registrations(
    event_id: uuid.UUID,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    booking_status: BookingStatus | None = Query(default=None, alias="status"),
    slot_id: uuid.UUID | None = None,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[RegistrationRow]:
    """Everyone booked, with contact details and answers. For the people who run the event."""
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    rows, total = await organizer.registrations(
        db, event=event, status=booking_status, slot_id=slot_id, q=q, limit=limit, offset=offset
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers.update(NO_STORE)
    return rows


@organizer_router.get("/{event_id}/registrations.csv")
async def registrations_csv(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    """The roster as a spreadsheet, one row per person. Audited; 5 an hour."""
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    text = await organizer.export_csv(db, actor=user, event=event)
    await db.commit()
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={
            **NO_STORE,
            "Content-Disposition": 'attachment; filename="registrations.csv"',
        },
    )


@organizer_router.get("/{event_id}/tee-sheet", response_model=list[TeeSheetSlot])
async def tee_sheet(
    event_id: uuid.UUID,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> list[TeeSheetSlot]:
    """Active bookings and their people grouped by time slot."""
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    response.headers.update(NO_STORE)
    return await organizer.tee_sheet(db, event=event)


@organizer_router.post("/{event_id}/check-in", response_model=CheckInResult)
async def check_in(
    event_id: uuid.UUID,
    body: CheckInRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> CheckInResult:
    """
    Scan a ticket at the door. Scanning twice is not an error: the second answer is
    `already_checked_in` with the first time. 404: not a ticket we issued. 409 `wrong_event`
    or `void` (the booking was cancelled) name what is wrong.
    """
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    result, view = await tickets.check_in(
        db, actor=user, event=event, code=body.code, now=await service.db_now(db)
    )
    out = CheckInResult(
        result=result,
        holder_name=view.person.full_name,
        position=view.person.position,
        booking_reference=view.booking.reference,
        slot=tickets.ticket_out(view).slot,
        party_size=view.booking.party_size,
        checked_in_at=view.ticket.checked_in_at,
        first_scan_by_you=view.ticket.checked_in_by == user.id,
    )
    await db.commit()
    return out


@organizer_router.post(
    "/{event_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED
)
async def send_message(
    event_id: uuid.UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> MessageOut:
    """Email everyone with a confirmed booking (or just one slot). You get a count back, never
    their addresses. 5 an hour."""
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    message = await organizer.send_message(
        db, actor=user, event=event, subject=body.subject, body=body.body, slot_id=body.slot_id
    )
    out = MessageOut(
        id=message.id, recipient_count=message.recipient_count, created_at=message.created_at
    )
    await db.commit()
    return out
