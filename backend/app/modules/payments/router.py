import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import rate_limit
from app.infrastructure.database.session import get_db_session
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.payments import schemas, service
from app.modules.payments.models import PaymentAccount

router = APIRouter(prefix="/payment-accounts", tags=["payments"])


def _out(a: PaymentAccount) -> schemas.PaymentAccountOut:
    return schemas.PaymentAccountOut.model_validate(a, from_attributes=True)


@router.post("", response_model=schemas.PaymentAccountOut, status_code=status.HTTP_201_CREATED)
async def create_payment_account(
    body: schemas.PaymentAccountCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _limit: None = Depends(rate_limit("payment_account_write", limit=30, window_seconds=3600)),
) -> schemas.PaymentAccountOut:
    """The paybill or till an event is paid to. Organization admins, for their own organization."""
    account = await service.create(db, actor=user, body=body)
    out = _out(account)
    await db.commit()
    return out


@router.get("", response_model=list[schemas.PaymentAccountOut])
async def my_payment_accounts(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> list[schemas.PaymentAccountOut]:
    return [_out(a) for a in await service.list_mine(db, actor=user)]


@router.patch("/{account_id}", response_model=schemas.PaymentAccountOut)
async def update_payment_account(
    account_id: uuid.UUID,
    body: schemas.PaymentAccountUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _limit: None = Depends(rate_limit("payment_account_write", limit=30, window_seconds=3600)),
) -> schemas.PaymentAccountOut:
    account = await service.update(db, actor=user, account_id=account_id, body=body)
    out = _out(account)
    await db.commit()
    return out
