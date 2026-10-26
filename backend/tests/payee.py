"""A payment account for tests that publish a paid event (publishing needs one)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.models import MpesaKind, PaymentAccount, PaymentProvider


async def payee_id(db: AsyncSession, organization_id: uuid.UUID) -> str:
    account = PaymentAccount(
        organization_id=organization_id,
        label="Test paybill",
        provider=PaymentProvider.MANUAL_MPESA,
        mpesa_kind=MpesaKind.PAYBILL,
        shortcode_or_till="123456",
    )
    db.add(account)
    await db.flush()
    return str(account.id)
