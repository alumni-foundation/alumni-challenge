"""Payee accounts: the paybill or till an event's money is paid to (manual M-Pesa for now)."""

import uuid

from sqlalchemy import ColumnElement, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.permissions.dependencies import get_user_roles
from app.modules.audit.service import record as record_audit
from app.modules.bookings.models import Booking
from app.modules.events import access
from app.modules.events.models import Event
from app.modules.identity.models import User
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.organizations.service import get_active_organization
from app.modules.payments import schemas
from app.modules.payments.models import PaymentAccount, PaymentProvider


def _org_context(organization_id: uuid.UUID | None) -> dict[str, str]:
    return {"organization_id": str(organization_id)} if organization_id else {}


async def _require_admin(
    db: AsyncSession, *, user: User, organization_id: uuid.UUID | None
) -> None:
    """Organization admins for their own accounts; platform admins for every account."""
    roles = await get_user_roles(db, user_id=user.id, organization_id=organization_id)
    if not roles & access.ADMIN_ROLES:
        raise ForbiddenError("You do not have permission to manage payment accounts here.")


async def create(
    db: AsyncSession, *, actor: User, body: schemas.PaymentAccountCreate
) -> PaymentAccount:
    if body.organization_id is not None:
        await get_active_organization(db, organization_id=body.organization_id)
    await _require_admin(db, user=actor, organization_id=body.organization_id)
    account = PaymentAccount(
        organization_id=body.organization_id,
        label=body.label,
        provider=PaymentProvider.MANUAL_MPESA,
        mpesa_kind=body.mpesa_kind,
        shortcode_or_till=body.shortcode_or_till,
        created_by=actor.id,
    )
    db.add(account)
    await db.flush()
    await record_audit(
        db,
        actor_user_id=actor.id,
        action="payment_account.create",
        target_type="payment_account",
        target_id=account.id,
        context={**_org_context(account.organization_id), "kind": account.mpesa_kind.value},
    )
    return account


async def get_for_admin(db: AsyncSession, *, actor: User, account_id: uuid.UUID) -> PaymentAccount:
    account = await db.get(PaymentAccount, account_id)
    if account is None:
        raise NotFoundError("Payment account not found.")
    roles = await get_user_roles(db, user_id=actor.id, organization_id=account.organization_id)
    if not roles & access.ADMIN_ROLES:
        raise NotFoundError("Payment account not found.")
    return account


async def update(
    db: AsyncSession,
    *,
    actor: User,
    account_id: uuid.UUID,
    body: schemas.PaymentAccountUpdate,
) -> PaymentAccount:
    account = await get_for_admin(db, actor=actor, account_id=account_id)
    changes = body.model_dump(exclude_unset=True)
    in_use = await db.scalar(
        select(func.count()).select_from(Event).where(Event.payment_account_id == account.id)
    )
    # Changing the number under an event that already has bookings would send people's money
    # somewhere they were not told. Switching an account off is always allowed.
    if "shortcode_or_till" in changes and changes["shortcode_or_till"] != account.shortcode_or_till:
        booked = await db.scalar(
            select(func.count())
            .select_from(Booking)
            .join(Event, Event.id == Booking.event_id)
            .where(Event.payment_account_id == account.id)
        )
        if in_use and booked:
            raise ConflictError(
                "People have already booked events paid to this number, so it can no longer "
                "change. Make a new account instead.",
                code="payment_account_in_use",
            )
    for key, value in changes.items():
        if value is None:
            continue
        setattr(account, key, value)
    await db.flush()
    await record_audit(
        db,
        actor_user_id=actor.id,
        action="payment_account.update",
        target_type="payment_account",
        target_id=account.id,
        context={**_org_context(account.organization_id), "fields": sorted(changes)},
    )
    return account


async def list_mine(db: AsyncSession, *, actor: User) -> list[PaymentAccount]:
    """Accounts of every organization the user administers, plus the platform's if they are a
    platform admin."""
    platform = await get_user_roles(db, user_id=actor.id, organization_id=None)
    org_ids = [
        m.organization_id
        for m in (
            await db.scalars(
                select(Membership).where(
                    Membership.user_id == actor.id,
                    Membership.status == MembershipStatus.ACTIVE,
                    Membership.organization_id.is_not(None),
                )
            )
        ).all()
        if m.organization_id is not None and m.role in access.ADMIN_ROLES
    ]
    is_platform_admin = bool(platform & access.PLATFORM_ADMIN_ROLES)
    conditions: list[ColumnElement[bool]] = []
    if org_ids:
        conditions.append(PaymentAccount.organization_id.in_(org_ids))
    if is_platform_admin:
        conditions.append(true())  # every account, platform ones included
    if not conditions:
        return []
    return list(
        (
            await db.scalars(
                select(PaymentAccount)
                .where(or_(*conditions))
                .order_by(PaymentAccount.created_at.desc(), PaymentAccount.id)
            )
        ).all()
    )
