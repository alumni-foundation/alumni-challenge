"""
Demo events for local development: a free meetup, a paid evening, a four-slot golf day and a
draft. Added to the seed as each event slice lands. Invented, like everything in the seed.

A rerun changes nothing that exists (events are found by organizer and title).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events import schemas, service
from app.modules.events.models import Event
from app.modules.identity.models import User
from app.modules.organizations.models import Organization

MEETUP = "Demo Alumni Meetup"
EVENING = "Demo Careers Evening"
GOLF = "Demo Golf Day"
DRAFT = "Demo Draft Dinner"

# (label, start, end) of the four tee-off periods, in Nairobi time (UTC+3).
_TEE_PERIODS = [
    ("Early morning 6:30 to 7:30", (6, 30), (7, 30)),
    ("Mid morning 7:40 to 8:40", (7, 40), (8, 40)),
    ("Early afternoon 11:20 to 12:20", (11, 20), (12, 20)),
    ("Mid afternoon 12:30 to 1:30", (12, 30), (13, 30)),
]


def _day(days_ahead: int) -> datetime:
    """Midnight Nairobi time (21:00 UTC the evening before), `days_ahead` days from now."""
    today = datetime.now(UTC).replace(hour=21, minute=0, second=0, microsecond=0)
    return today + timedelta(days=days_ahead - 1)


async def _exists(db: AsyncSession, school: Organization, title: str) -> bool:
    return (
        await db.scalar(
            select(Event.id).where(Event.organization_id == school.id, Event.title == title)
        )
        is not None
    )


async def ensure_demo_events(
    db: AsyncSession, *, school: Organization, manager: User, admin: User
) -> None:
    """`manager` makes the drafts, `admin` (the school's admin) publishes them."""
    if not await _exists(db, school, MEETUP):
        start = _day(14) + timedelta(hours=18)  # 6pm Nairobi
        event = await service.create_event(
            db,
            actor=manager,
            body=schemas.EventCreate(
                organization_id=school.id,
                title=MEETUP,
                description="Come and meet fellow alumni. Free, no payment.",
                category="networking",
                starts_at=start,
                ends_at=start + timedelta(hours=3),
                venue_name="Demo Hall, Nairobi",
                capacity=60,
                max_party_size=2,
                waitlist_enabled=True,
            ),
        )
        await service.publish(db, actor=admin, event=event)

    if not await _exists(db, school, EVENING):
        start = _day(21) + timedelta(hours=18)
        event = await service.create_event(
            db,
            actor=manager,
            body=schemas.EventCreate(
                organization_id=school.id,
                title=EVENING,
                description="Talks and networking with alumni from many careers.",
                category="forum",
                starts_at=start,
                ends_at=start + timedelta(hours=3),
                venue_name="Demo Conference Centre",
                price_minor=150_000,  # KES 1,500
                capacity=50,
                max_party_size=2,
            ),
        )
        await service.publish(db, actor=admin, event=event)

    if not await _exists(db, school, GOLF):
        day = _day(30)
        slots = [
            schemas.SlotInput(
                label=label,
                starts_at=day + timedelta(hours=a[0], minutes=a[1]),
                ends_at=day + timedelta(hours=b[0], minutes=b[1]),
                capacity=40,
                position=i,
            )
            for i, (label, a, b) in enumerate(_TEE_PERIODS)
        ]
        event = await service.create_event(
            db,
            actor=manager,
            body=schemas.EventCreate(
                organization_id=school.id,
                title=GOLF,
                description="A demo four-ball day. Invented; no real club or fee.",
                category="golf_tournament",
                starts_at=slots[0].starts_at,
                ends_at=slots[-1].ends_at,
                venue_name="Demo Golf and Resort",
                price_minor=350_000,  # KES 3,500 per player
                max_party_size=4,
                waitlist_enabled=True,
                slots=slots,
            ),
        )
        await service.publish(db, actor=admin, event=event)

    if not await _exists(db, school, DRAFT):
        start = _day(45) + timedelta(hours=19)
        await service.create_event(
            db,
            actor=manager,
            body=schemas.EventCreate(
                organization_id=school.id,
                title=DRAFT,
                category="homecoming",
                starts_at=start,
                ends_at=start + timedelta(hours=4),
                capacity=100,
            ),
        )
