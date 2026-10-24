"""
Demo events for local development: a free meetup, a paid evening, a four-slot golf day and a
draft. Invented, like everything in the seed. The meetup and the golf day are the two the
frontend is built against, so they are complete: published, with a poster, questions and
consent checkboxes; the golf day is paid to a demo paybill.

A rerun changes nothing that exists and is current (events are found by organizer and title).
A meetup or golf day from an older seed (one without a poster) that nobody has booked is
replaced with the current one; one that has bookings is left alone.
"""

import io
from datetime import UTC, datetime, timedelta

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.storage import get_storage
from app.modules.bookings.models import Booking
from app.modules.events import schemas, service
from app.modules.events.models import Event
from app.modules.files import attach
from app.modules.files import service as files_service
from app.modules.files.models import FilePurpose
from app.modules.identity.models import User
from app.modules.organizations.models import Organization
from app.modules.payments.models import MpesaKind, PaymentAccount, PaymentProvider

MEETUP = "Demo Alumni Meetup"
EVENING = "Demo Careers Evening"
GOLF = "Demo Golf Day"
DRAFT = "Demo Draft Dinner"

# An invented paybill number, so the booking page has somewhere to say "pay to".
DEMO_PAYEE_LABEL = "Demo Golf Day (invented paybill)"
DEMO_PAYBILL = "888880"

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


def make_poster(title: str, subtitle: str, colour: tuple[int, int, int]) -> bytes:
    """A plain generated picture: colour bands, the title and a line under it. Invented art."""
    width, height = 1200, 630
    image = Image.new("RGB", (width, height), colour)
    draw = ImageDraw.Draw(image)
    darker = (int(colour[0] * 0.7), int(colour[1] * 0.7), int(colour[2] * 0.7))
    for i in range(6):  # diagonal bands, so it does not look like a blank rectangle
        x = -200 + i * 260
        draw.polygon([(x, height), (x + 130, height), (x + 530, 0), (x + 400, 0)], fill=darker)
    draw.rectangle([0, height - 120, width, height], fill=(255, 255, 255))
    draw.text((60, 190), title, fill=(255, 255, 255), font=ImageFont.load_default(size=88))
    draw.text((60, 320), subtitle, fill=(255, 255, 255), font=ImageFont.load_default(size=44))
    draw.text(
        (60, height - 85),
        "Demo event - invented for development",
        fill=(40, 40, 40),
        font=ImageFont.load_default(size=36),
    )
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


async def _needs_creating(db: AsyncSession, school: Organization, title: str) -> bool:
    """True when the event is missing, or is an older-seed version nobody has booked (which is
    removed here so it can be made again). False when it exists and should be left alone."""
    event = await db.scalar(
        select(Event).where(Event.organization_id == school.id, Event.title == title)
    )
    if event is None:
        return True
    if event.poster_file_id is not None:
        return False  # current
    booked = await db.scalar(select(Booking.id).where(Booking.event_id == event.id).limit(1))
    if booked is not None:
        return False  # people are using it: do not pull it out from under them
    await db.execute(delete(Event).where(Event.id == event.id))  # slots, questions: cascade
    await db.flush()
    return True


async def _exists(db: AsyncSession, school: Organization, title: str) -> bool:
    return (
        await db.scalar(
            select(Event.id).where(Event.organization_id == school.id, Event.title == title)
        )
        is not None
    )


async def _payee(db: AsyncSession, school: Organization, manager: User) -> PaymentAccount:
    account = await db.scalar(
        select(PaymentAccount).where(
            PaymentAccount.organization_id == school.id, PaymentAccount.label == DEMO_PAYEE_LABEL
        )
    )
    if account is None:
        account = PaymentAccount(
            organization_id=school.id,
            label=DEMO_PAYEE_LABEL,
            provider=PaymentProvider.MANUAL_MPESA,
            mpesa_kind=MpesaKind.PAYBILL,
            shortcode_or_till=DEMO_PAYBILL,
            created_by=manager.id,
        )
        db.add(account)
        await db.flush()
    return account


async def _poster(
    db: AsyncSession,
    *,
    event: Event,
    school: Organization,
    manager: User,
    title: str,
    subtitle: str,
    colour: tuple[int, int, int],
) -> None:
    row = await files_service.upload_image(
        db,
        get_storage(),
        user=manager,
        purpose=FilePurpose.EVENT_POSTER,
        organization_id=school.id,
        data=make_poster(title, subtitle, colour),
    )
    await attach.set_event_poster(db, event=event, file_id=row.id)


async def ensure_demo_events(
    db: AsyncSession, *, school: Organization, manager: User, admin: User
) -> None:
    """`manager` makes the drafts, `admin` (the school's admin) publishes them."""
    if await _needs_creating(db, school, MEETUP):
        start = _day(14) + timedelta(hours=18)  # 6pm Nairobi
        event = await service.create_event(
            db,
            actor=manager,
            body=schemas.EventCreate(
                organization_id=school.id,
                title=MEETUP,
                description="Come and meet fellow alumni. Free, no payment. Invented for the demo.",
                category="networking",
                starts_at=start,
                ends_at=start + timedelta(hours=3),
                venue_name="Demo Hall, Nairobi",
                venue_address="1 Demo Road, Nairobi",
                capacity=40,
                max_party_size=2,
                waitlist_enabled=True,
            ),
        )
        await service.add_question(
            db,
            actor=manager,
            event=event,
            body=schemas.QuestionCreate(
                key="anything_we_should_know",
                label="Anything we should know? (optional)",
                kind="long_text",
                required=False,
                position=0,
            ),
        )
        await service.add_consent(
            db,
            actor=manager,
            event=event,
            body=schemas.ConsentCreate(
                key="terms",
                text="I agree to the event rules and to behave respectfully towards other guests.",
                required=True,
            ),
        )
        await service.add_consent(
            db,
            actor=manager,
            event=event,
            body=schemas.ConsentCreate(
                key="filming_photography",
                text="I am happy to appear in photos and filming taken at the event.",
                required=False,
            ),
        )
        await _poster(
            db,
            event=event,
            school=school,
            manager=manager,
            title="Demo Alumni Meetup",
            subtitle="Free. 40 places.",
            colour=(30, 90, 140),
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

    if await _needs_creating(db, school, GOLF):
        day = _day(30)
        slots = [
            schemas.SlotInput(
                label=label,
                starts_at=day + timedelta(hours=a[0], minutes=a[1]),
                ends_at=day + timedelta(hours=b[0], minutes=b[1]),
                capacity=24,
                position=i,
            )
            for i, (label, a, b) in enumerate(_TEE_PERIODS)
        ]
        payee = await _payee(db, school, manager)
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
                venue_address="Demo Fairway, Nairobi",
                price_minor=500_000,  # KES 5,000 per player
                max_party_size=4,
                waitlist_enabled=True,
                hold_minutes=1440,  # a day to pay by hand
                payment_account_id=payee.id,
                slots=slots,
            ),
        )
        # Asked of each player unless said otherwise. The `golf_` keys are the ones the later
        # golf tables will read, so these answers can be moved over.
        questions: list[tuple[str, str, str, bool, str, list[tuple[str, str]] | None]] = [
            (
                "golf_handicap_index",
                "Handicap index (leave empty if none)",
                "number",
                False,
                "each_participant",
                None,
            ),
            ("golf_team", "Team name", "text", False, "booker", None),
            (
                "shirt_size",
                "Shirt size",
                "choice",
                True,
                "each_participant",
                [(v, v) for v in ("S", "M", "L", "XL", "XXL")],
            ),
            (
                "meal_choice",
                "Meal choice",
                "choice",
                True,
                "each_participant",
                [("beef", "Beef"), ("chicken", "Chicken"), ("vegetarian", "Vegetarian")],
            ),
        ]
        for position, (key, label, kind, required, asked_of, options) in enumerate(questions):
            await service.add_question(
                db,
                actor=manager,
                event=event,
                body=schemas.QuestionCreate.model_validate(
                    {
                        "key": key,
                        "label": label,
                        "kind": kind,
                        "required": required,
                        "asked_of": asked_of,
                        "position": position,
                        "options": (
                            [{"value": v, "label": lbl} for v, lbl in options] if options else None
                        ),
                    }
                ),
            )
        await service.add_consent(
            db,
            actor=manager,
            event=event,
            body=schemas.ConsentCreate(
                key="terms",
                text="I agree to the club rules and the event terms.",
                required=True,
            ),
        )
        await _poster(
            db,
            event=event,
            school=school,
            manager=manager,
            title="Demo Golf Day",
            subtitle="KES 5,000 per player. Four tee times.",
            colour=(30, 110, 70),
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
