"""
Slice 5.2 concurrency tests (design section 10, tests 1 to 5).

These do NOT use the per-test rollback session: every request gets its own connection and really
commits, like production, so the database's locks are what is being tested. The data they make is
committed, so it is tagged with a per-run prefix and removed afterwards (and any leftovers from a
crashed earlier run are removed first). They only ever touch the test database.
"""

import asyncio
import contextlib
import os
import random
import uuid
from collections.abc import AsyncGenerator, Awaitable, Sequence
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.errors.exceptions import AppError
from app.core.permissions.roles import Role
from app.infrastructure.database.session import get_db_session
from app.main import app
from app.modules.bookings import seats
from app.modules.bookings import service as bookings_service
from app.modules.bookings import tickets as tickets_module
from app.modules.bookings.models import Booking
from app.modules.bookings.schemas import BookingCreate, ParticipantInput
from app.modules.events.models import EventSlot
from app.modules.identity.models import User
from app.modules.identity.security import create_access_token, hash_password
from app.modules.memberships.models import Membership
from app.modules.organizations.models import Organization, OrganizationType

API = "/api/v1"
ROUNDS = int(os.environ.get("CONCURRENCY_ROUNDS", "4"))
PEOPLE = 200

pytestmark = pytest.mark.asyncio


@dataclass
class Person:
    user_id: uuid.UUID
    headers: dict[str, str]


class World:
    """Committed data for one test, plus a client whose every request has its own connection."""

    def __init__(self, factory: async_sessionmaker[AsyncSession], client: AsyncClient) -> None:
        self.factory = factory
        self.client = client
        self.tag = f"conc-{uuid.uuid4().hex[:10]}"
        self._hash = hash_password("not-used-by-these-tests")
        self.admin: Person | None = None
        self.org_id: uuid.UUID | None = None
        self._n = 0

    async def person(self) -> Person:
        self._n += 1
        async with self.factory() as db:
            user = User(email=f"{self.tag}-{self._n}@example.com", password_hash=self._hash)
            db.add(user)
            await db.commit()
            return Person(user.id, {"Authorization": f"Bearer {create_access_token(user.id)}"})

    async def people(self, n: int) -> list[Person]:
        return list(await asyncio.gather(*(self.person() for _ in range(n))))

    async def setup_organizer(self) -> None:
        self.admin = await self.person()
        async with self.factory() as db:
            org = Organization(type=OrganizationType.SCHOOL, name=self.tag, slug=self.tag)
            db.add(org)
            await db.flush()
            db.add(
                Membership(
                    user_id=self.admin.user_id, organization_id=org.id, role=Role.SCHOOL_ADMIN
                )
            )
            await db.commit()
            self.org_id = org.id

    async def event(self, **over: Any) -> dict[str, Any]:
        assert self.admin is not None
        from datetime import UTC, datetime, timedelta

        now = datetime.now(UTC)
        body = {
            "organization_id": str(self.org_id),
            "title": f"{self.tag} event",
            "category": "networking",
            "starts_at": (now + timedelta(days=10)).isoformat(),
            "ends_at": (now + timedelta(days=10, hours=3)).isoformat(),
            "capacity": 10,
            "max_party_size": 4,
        }
        body.update(over)
        r = await self.client.post(f"{API}/events", json=body, headers=self.admin.headers)
        assert r.status_code == 201, r.text
        pub = await self.client.post(
            f"{API}/events/{r.json()['id']}/publish", headers=self.admin.headers
        )
        assert pub.status_code == 200, pub.text
        data: dict[str, Any] = pub.json()
        return data

    async def book(
        self,
        person: Person,
        event: dict[str, Any],
        *,
        size: int = 1,
        key: str | None = None,
    ) -> Response:
        names = [{"full_name": f"Player {i}"} for i in range(1, size + 1)]
        return await self.client.post(
            f"{API}/events/{event['id']}/bookings",
            json={
                "slot_id": event["slots"][0]["id"],
                "participants": names,
                "others_consent_confirmed": size > 1,
            },
            headers={**person.headers, "Idempotency-Key": key or uuid.uuid4().hex},
        )

    async def truth(self, slot_id: str) -> tuple[tuple[int, int], tuple[int, int], int | None]:
        """((counter confirmed, counter held), (recounted confirmed, held), capacity)."""
        async with self.factory() as db:
            slot = await db.get(EventSlot, uuid.UUID(slot_id))
            assert slot is not None
            return (
                (slot.seats_confirmed, slot.seats_held),
                await seats.recount(db, slot.id),
                slot.capacity,
            )

    async def cleanup(self) -> None:
        async with self.factory() as db:
            await _purge(db, self.tag)
            await db.commit()


async def _purge(db: AsyncSession, tag_like: str) -> None:
    """Deletes everything a World (or, with a wildcard, every old World) made."""
    like = f"{tag_like}%"
    params = {"like": like}
    await db.execute(
        text(
            "DELETE FROM domain_events WHERE payload->>'booking_id' IN ("
            " SELECT b.id::text FROM bookings b WHERE b.booker_user_id IN"
            " (SELECT id FROM users WHERE email LIKE :em))"
        ),
        {"em": f"{tag_like}%@example.com"},
    )
    await db.execute(
        text(
            "DELETE FROM bookings WHERE event_id IN (SELECT id FROM events WHERE"
            " organization_id IN (SELECT id FROM organizations WHERE slug LIKE :like))"
        ),
        params,
    )
    await db.execute(
        text(
            "DELETE FROM events WHERE organization_id IN"
            " (SELECT id FROM organizations WHERE slug LIKE :like)"
        ),
        params,
    )
    await db.execute(
        text(
            "DELETE FROM audit_log WHERE metadata->>'organization_id' IN"
            " (SELECT id::text FROM organizations WHERE slug LIKE :like)"
        ),
        params,
    )
    await db.execute(
        text(
            "DELETE FROM memberships WHERE user_id IN (SELECT id FROM users WHERE email LIKE :em)"
        ),
        {"em": f"{tag_like}%@example.com"},
    )
    await db.execute(text("DELETE FROM organizations WHERE slug LIKE :like"), params)
    await db.execute(
        text(
            "DELETE FROM audit_log WHERE actor_user_id IN"
            " (SELECT id FROM users WHERE email LIKE :em)"
        ),
        {"em": f"{tag_like}%@example.com"},
    )
    await db.execute(
        text("DELETE FROM users WHERE email LIKE :em"), {"em": f"{tag_like}%@example.com"}
    )


@pytest.fixture
async def world() -> AsyncGenerator[World, None]:
    engine = create_async_engine(str(get_settings().database_url), pool_size=30, max_overflow=0)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db_session] = _session
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        w = World(factory, client)
        async with factory() as db:
            await _purge(db, "conc-")  # leftovers from a crashed earlier run
            await db.commit()
        await w.setup_organizer()
        try:
            yield w
        finally:
            seats.capacity_check_hook = None
            tickets_module.check_in_hook = None
            await w.cleanup()
    app.dependency_overrides.clear()
    await engine.dispose()


def _codes(results: Sequence[Response]) -> list[int]:
    return sorted(r.status_code for r in results)


# ------------------------------------------------------------- 1. last seat, two people


async def test_two_people_booking_the_last_seat_at_the_same_instant_one_wins(
    world: World,
) -> None:
    event = await world.event(capacity=1)
    a, b = await world.people(2)
    arrived = 0
    both_here = asyncio.Event()

    async def hold_between_check_and_write() -> None:
        # Every booking that reaches this point has already been told "there is room". With the
        # slot lock working, only one gets here at a time, so the wait times out and carries on.
        # Without the lock both arrive together, are released together, and both try to write.
        nonlocal arrived
        arrived += 1
        if arrived >= 2:
            both_here.set()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(both_here.wait(), timeout=1.0)

    seats.capacity_check_hook = hold_between_check_and_write
    results = await asyncio.gather(world.book(a, event), world.book(b, event))
    assert _codes(results) == [201, 409], [r.text for r in results]
    loser = next(r for r in results if r.status_code == 409)
    assert loser.json()["error"]["code"] == "sold_out"
    counters, recounted, capacity = await world.truth(event["slots"][0]["id"])
    assert counters == recounted == (1, 0)
    assert capacity == 1


# ------------------------------------------------------------- 2. many against few


async def test_two_hundred_people_against_ten_seats_never_oversell_and_fill_every_seat(
    world: World,
) -> None:
    people = await world.people(PEOPLE)
    rng = random.Random(2026)
    for round_no in range(ROUNDS):
        paid = round_no % 3 == 2
        event = await world.event(capacity=10, **({"price_minor": 100_000} if paid else {}))
        sizes = [rng.randint(1, 4) for _ in people]
        results = await asyncio.gather(
            *(world.book(p, event, size=s) for p, s in zip(people, sizes, strict=True))
        )
        codes = {r.status_code for r in results}
        assert codes <= {201, 409}, (
            round_no,
            codes,
            [r.text for r in results if r.status_code >= 500][:2],
        )
        for r in results:
            if r.status_code == 409:
                assert r.json()["error"]["code"] in {"sold_out", "too_many_holds"}, r.text
        won = sum(s for r, s in zip(results, sizes, strict=True) if r.status_code == 201)
        counters, recounted, capacity = await world.truth(event["slots"][0]["id"])
        assert counters == recounted, (round_no, counters, recounted)
        assert sum(counters) <= (capacity or 0)
        assert sum(counters) == won
        # Demand far exceeded supply, so a seat left empty means the lock was too coarse or a
        # request was turned away that could have fitted.
        assert sum(counters) == 10, (round_no, counters)
        if paid:
            # Free the unpaid holds so these people can take part in the next round.
            async with world.factory() as db:
                await db.execute(
                    text(
                        "UPDATE bookings SET status = 'cancelled', hold_expires_at = NULL"
                        " WHERE status = 'pending_payment' AND event_id = :e"
                    ),
                    {"e": event["id"]},
                )
                await db.commit()


# ------------------------------------------------------------- 3. double clicks


async def test_the_same_key_sent_ten_times_at_once_makes_one_booking(world: World) -> None:
    event = await world.event(capacity=10)
    (p,) = await world.people(1)
    results = await asyncio.gather(*(world.book(p, event, key="double-click") for _ in range(10)))
    assert {r.status_code for r in results} <= {201, 409}, [r.text for r in results]
    created = [r for r in results if r.status_code == 201]
    assert created and len({r.json()["id"] for r in created}) == 1
    for r in results:
        if r.status_code == 409:
            assert r.json()["error"]["code"] in {"idempotency_in_progress", "conflict"}, r.text
    counters, recounted, _ = await world.truth(event["slots"][0]["id"])
    assert counters == recounted == (1, 0)


async def test_ten_different_keys_at_once_make_one_booking(world: World) -> None:
    event = await world.event(capacity=10)
    (p,) = await world.people(1)
    results = await asyncio.gather(*(world.book(p, event) for _ in range(10)))
    assert _codes(results) == [201] + [409] * 9, [r.text for r in results]
    assert {r.json()["error"]["code"] for r in results if r.status_code == 409} == {
        "already_booked"
    }
    counters, recounted, _ = await world.truth(event["slots"][0]["id"])
    assert counters == recounted == (1, 0)


async def test_the_same_key_reaching_the_service_ten_times_at_once_returns_one_booking(
    world: World,
) -> None:
    """Skips the web layer's Redis check, so this is the database's own idempotency."""
    event = await world.event(capacity=10)
    (p,) = await world.people(1)
    body = BookingCreate(
        slot_id=uuid.UUID(event["slots"][0]["id"]),
        participants=[ParticipantInput(full_name="Ann Alum")],
    )

    async def attempt() -> uuid.UUID | AppError:
        async with world.factory() as db:
            user = await db.get(User, p.user_id)
            assert user is not None
            try:
                booking = await bookings_service.create_booking(
                    db,
                    user=user,
                    event_id=uuid.UUID(event["id"]),
                    body=body,
                    idempotency_key="svc-double",
                )
                await db.commit()
                return booking.id
            except AppError as exc:
                await db.rollback()
                return exc

    results = await asyncio.gather(*(attempt() for _ in range(10)))
    ids = {r for r in results if isinstance(r, uuid.UUID)}
    errors = [r for r in results if isinstance(r, AppError)]
    assert len(ids) == 1, results
    assert not errors, [e.code for e in errors]
    async with world.factory() as db:
        count = await db.scalar(
            select(text("count(*)")).select_from(Booking).where(Booking.booker_user_id == p.user_id)
        )
    assert count == 1
    counters, recounted, _ = await world.truth(event["slots"][0]["id"])
    assert counters == recounted == (1, 0)


# ------------------------------------------------------------- 4. races between operations


async def test_cancelling_booking_and_hold_expiry_on_one_slot_keep_the_counters_true(
    world: World,
) -> None:
    holders = await world.people(8)
    newcomers = await world.people(12)
    rng = random.Random(7)
    for round_no in range(max(3, ROUNDS // 2)):
        event = await world.event(capacity=8, price_minor=100_000)
        slot_id = event["slots"][0]["id"]
        booked = await asyncio.gather(*(world.book(p, event) for p in holders))
        assert all(r.status_code == 201 for r in booked), [r.text for r in booked]
        ids = [r.json()["id"] for r in booked]
        expiring = rng.sample(ids, 3)
        async with world.factory() as db:
            await db.execute(
                text(
                    "UPDATE bookings SET hold_expires_at = now() - interval '1 minute'"
                    " WHERE id = ANY(CAST(:ids AS uuid[]))"
                ),
                {"ids": expiring},
            )
            await db.commit()
        cancelling = rng.sample([i for i in ids if i not in expiring], 3)
        owner = {i: p for i, p in zip(ids, holders, strict=True)}
        tasks: list[Awaitable[Response]] = [
            world.client.post(f"{API}/bookings/{i}/cancel", headers=owner[i].headers)
            for i in cancelling
        ]
        tasks += [world.book(p, event) for p in newcomers]
        tasks_shuffled = list(tasks)
        rng.shuffle(tasks_shuffled)
        results = await asyncio.gather(*tasks_shuffled)
        assert max(r.status_code for r in results) < 500, [
            r.text for r in results if r.status_code >= 500
        ][:2]
        counters, recounted, capacity = await world.truth(slot_id)
        assert counters == recounted, (round_no, counters, recounted)
        assert sum(counters) <= (capacity or 0)
        # 8 seats, 3 expired + 3 cancelled freed and 12 hopefuls: the slot must end up full.
        assert sum(counters) == 8, (round_no, counters)
        async with world.factory() as db:
            await db.execute(
                text(
                    "UPDATE bookings SET status = 'cancelled', hold_expires_at = NULL"
                    " WHERE status = 'pending_payment' AND event_id = :e"
                ),
                {"e": event["id"]},
            )
            await db.commit()


# ------------------------------------------------------------- 5. the database refuses alone


async def test_the_database_refuses_to_oversell_with_the_application_bypassed(
    world: World,
) -> None:
    event = await world.event(capacity=2)
    async with world.factory() as db:
        with pytest.raises(Exception, match="ck_event_slots_not_oversold"):
            await db.execute(
                text("UPDATE event_slots SET seats_confirmed = 3 WHERE id = :i"),
                {"i": event["slots"][0]["id"]},
            )
        await db.rollback()
        with pytest.raises(Exception, match="ck_event_slots_counters_not_negative"):
            await db.execute(
                text("UPDATE event_slots SET seats_held = -1 WHERE id = :i"),
                {"i": event["slots"][0]["id"]},
            )
        await db.rollback()


async def test_two_raw_writers_cannot_both_take_the_last_seat(world: World) -> None:
    """Even code that forgot to lock cannot oversell: the second UPDATE is refused."""
    event = await world.event(capacity=1)
    slot_id = event["slots"][0]["id"]
    async with world.factory() as one, world.factory() as two:
        await one.execute(
            text("UPDATE event_slots SET seats_confirmed = seats_confirmed + 1 WHERE id = :i"),
            {"i": slot_id},
        )

        async def second() -> str:
            try:
                await two.execute(
                    text(
                        "UPDATE event_slots SET seats_confirmed = seats_confirmed + 1 WHERE id = :i"
                    ),
                    {"i": slot_id},
                )
                await two.commit()
                return "both"
            except Exception as exc:  # noqa: BLE001 - the point is that it is refused
                return type(exc).__name__ + ": " + str(exc)

        pending = asyncio.create_task(second())
        await asyncio.sleep(0.3)
        await one.commit()
        outcome = await pending
    assert "ck_event_slots_not_oversold" in outcome, outcome


# ------------------------------------------------------------- 6. waiting for a busy slot


async def test_a_slot_that_stays_locked_gives_a_clean_retryable_503(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = await world.event(capacity=5)
    (p,) = await world.people(1)
    monkeypatch.setattr(seats, "LOCK_TIMEOUT", "300ms")
    async with world.factory() as blocker:
        await blocker.execute(
            text("SELECT 1 FROM event_slots WHERE id = :i FOR UPDATE"),
            {"i": event["slots"][0]["id"]},
        )
        r = await world.book(p, event)
        await blocker.rollback()
    assert r.status_code == 503 and r.json()["error"]["code"] == "busy", r.text
    counters, recounted, _ = await world.truth(event["slots"][0]["id"])
    assert counters == recounted == (0, 0)
    # Nothing was left half-done: the same person can book as soon as the slot is free.
    again = await world.book(p, event)
    assert again.status_code == 201, again.text


# ------------------------------------------------------------- 7. ten phones, one ticket


async def test_ten_scans_of_one_ticket_at_once_agree_on_a_single_first_scan(world: World) -> None:
    event = await world.event(capacity=5)
    (p,) = await world.people(1)
    booking = (await world.book(p, event)).json()
    mine = await world.client.get(f"{API}/bookings/{booking['id']}/tickets", headers=p.headers)
    code = mine.json()[0]["code"]
    assert world.admin is not None

    arrived = 0
    both_here = asyncio.Event()

    async def hold_between_read_and_write() -> None:
        # Every scan that gets here has found the ticket unused. With the ticket locked only one
        # gets here, so the wait times out; without the lock several arrive together.
        nonlocal arrived
        arrived += 1
        if arrived >= 2:
            both_here.set()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(both_here.wait(), timeout=1.0)

    tickets_module.check_in_hook = hold_between_read_and_write
    try:
        results = await _scan_ten(world, event, code)
    finally:
        tickets_module.check_in_hook = None
    assert {r.status_code for r in results} == {200}, [r.text for r in results]
    outcomes = sorted(r.json()["result"] for r in results)
    assert outcomes == ["already_checked_in"] * 9 + ["checked_in"]
    assert len({r.json()["checked_in_at"] for r in results}) == 1


async def _scan_ten(world: World, event: dict[str, Any], code: str) -> list[Response]:
    assert world.admin is not None
    results = await asyncio.gather(
        *(
            world.client.post(
                f"{API}/events/{event['id']}/check-in",
                json={"code": code},
                headers=world.admin.headers,
            )
            for _ in range(10)
        )
    )
    return list(results)
