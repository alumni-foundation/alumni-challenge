"""How a hand-made M-Pesa payment looks to the booker and to the organizer. Reading only."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.models import Booking, BookingStatus, ManualPaymentState
from app.modules.bookings.schemas import BookingPaymentOut, RegistrationPayment
from app.modules.events.models import Event, EventStatus
from app.modules.payments.models import MpesaKind, PaymentAccount, PaymentProvider
from app.modules.payments.schemas import PayeeInfo

# A code may be sent while the places are held, and also after the hold ran out or the booking
# was cancelled: the person may have paid anyway, and the money must not go unnoticed.
_MAY_SEND_CODE = (BookingStatus.PENDING_PAYMENT, BookingStatus.EXPIRED, BookingStatus.CANCELLED)


async def manual_payee(db: AsyncSession, event: Event) -> PaymentAccount | None:
    """The event's payment account, if people pay it by hand."""
    if event.payment_account_id is None:
        return None
    account = await db.get(PaymentAccount, event.payment_account_id)
    if account is None or account.provider != PaymentProvider.MANUAL_MPESA:
        return None
    return account


def event_still_on(event: Event, now: datetime) -> bool:
    return event.status != EventStatus.CANCELLED and now < event.ends_at


def booking_payment(
    booking: Booking, event: Event, payee: PaymentAccount | None, now: datetime
) -> BookingPaymentOut | None:
    if payee is None or booking.amount_minor == 0:
        return None
    return BookingPaymentOut(
        payee=PayeeInfo(
            method=payee.provider,
            kind=payee.mpesa_kind,
            number=payee.shortcode_or_till,
            payee_name=payee.label,
            currency=payee.currency,
        ),
        account_reference=booking.reference if payee.mpesa_kind == MpesaKind.PAYBILL else None,
        state=booking.payment_state,
        code=booking.payment_reference_code,
        submitted_at=booking.payment_submitted_at,
        decided_at=booking.payment_decided_at,
        rejection_reason=(
            booking.payment_note if booking.payment_state == ManualPaymentState.REJECTED else None
        ),
        marked_paid_by_hand=booking.paid_without_code,
        can_submit_code=(
            booking.status in _MAY_SEND_CODE
            and booking.payment_state in (None, ManualPaymentState.REJECTED)
            and event_still_on(event, now)
        ),
    )


def registration_payment(booking: Booking) -> RegistrationPayment | None:
    if booking.amount_minor == 0:
        return None
    return RegistrationPayment(
        state=booking.payment_state,
        code=booking.payment_reference_code,
        submitted_at=booking.payment_submitted_at,
        decided_at=booking.payment_decided_at,
        rejection_reason=(
            booking.payment_note if booking.payment_state == ManualPaymentState.REJECTED else None
        ),
        marked_paid_by_hand=booking.paid_without_code,
        note=(
            booking.payment_note if booking.payment_state != ManualPaymentState.REJECTED else None
        ),
    )
