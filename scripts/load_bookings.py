"""
Load run for event bookings (design section 10, item 7): fire many bookings at one event through
the real HTTP API and check that the seats still add up.

What it does, per run:
  1. Makes an organizer, a school, one event with six time slots (one hot slot) and one account
     per booking, directly in the database. Accounts get tokens signed with the app's key, so no
     sign-up or login rate limit is in the way and no password hashing is paid for.
  2. Sends `--bookings` booking requests to the API at `--api`, at most `--concurrency` at a time.
     About 60% go to the hot slot; party sizes run from 1 to 4; about 10% are sent twice at the
     same moment with the same Idempotency-Key, like a double click or a retry.
  3. Reads the database and checks: no slot has more seats taken than its capacity; each slot's
     counters equal the seats really booked (a recount); every booking the API said yes to is a
     row and no other active row exists; nobody holds two active bookings; no answer was a 5xx
     other than the documented 503 "busy" (lock wait too long), which is counted and reported.
  4. Deletes everything it made.

It refuses to start unless the database name ends in `_test` and the Redis index is not 0 (the
development one). The API it talks to must be using
that same database (the organizer it makes must be known to the API, or the first call fails).
Do not point it at a development or production API: start a separate API process for the run
(the runner in PLAN.md's load-run note does this) on the test database and Redis index 15.

Run from the backend directory, inside the API image:
    python load_bookings.py --api http://127.0.0.1:8001 --bookings 3000
Exit code 0 if every check held, 1 otherwise.
"""

import argparse
import asyncio
import json
import os
import random
import statistics
import sys
import time
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

sys.path.insert(0, os.getcwd())

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.infrastructure.database.all_models  # noqa: E402, F401  (registers every table)
from app.core.config import get_settings  # noqa: E402
from app.core.permissions.roles import Role  # noqa: E402
from app.modules.identity.models import User  # noqa: E402
from app.modules.identity.security import create_access_token, hash_password  # noqa: E402
from app.modules.memberships.models import Membership  # noqa: E402
from app.modules.organizations.models import Organization, OrganizationType  # noqa: E402

API_V1 = "/api/v1"
# (label, capacity): the first is the hot slot.
SLOTS = [("hot", 100), ("a", 40), ("b", 60), ("c", 80), ("d", 20), ("e", 150)]
PARTY_SIZES = [1] * 4 + [2] * 3 + [3] * 1 + [4] * 2  # average 2.1 seats a booking


def database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def refusal(database_url: str, redis_url: str) -> str | None:
    """Why this must not run against these targets, or None if they are test targets."""
    if not database_name(database_url).endswith("_test"):
        return f"database {database_name(database_url)!r} does not end in _test"
    index = urlsplit(redis_url).path.lstrip("/") or "0"
    if index == "0":
        return "Redis index 0 is the development index; use a different one (the tests use 15)"
    return None


async def purge(db: Any, tag: str) -> None:
    like, em = f"{tag}%", f"{tag}%@example.com"
    steps = [
        (
            "DELETE FROM domain_events WHERE payload->>'booking_id' IN (SELECT b.id::text"
            " FROM bookings b WHERE b.booker_user_id IN (SELECT id FROM users WHERE email LIKE :em))",
            {"em": em},
        ),
        (
            "DELETE FROM bookings WHERE event_id IN (SELECT id FROM events WHERE organization_id"
            " IN (SELECT id FROM organizations WHERE slug LIKE :like))",
            {"like": like},
        ),
        (
            "DELETE FROM events WHERE organization_id IN"
            " (SELECT id FROM organizations WHERE slug LIKE :like)",
            {"like": like},
        ),
        (
            "DELETE FROM audit_log WHERE metadata->>'organization_id' IN"
            " (SELECT id::text FROM organizations WHERE slug LIKE :like)",
            {"like": like},
        ),
        (
            "DELETE FROM memberships WHERE user_id IN (SELECT id FROM users WHERE email LIKE :em)",
            {"em": em},
        ),
        ("DELETE FROM organizations WHERE slug LIKE :like", {"like": like}),
        (
            "DELETE FROM audit_log WHERE actor_user_id IN (SELECT id FROM users WHERE email LIKE :em)",
            {"em": em},
        ),
        ("DELETE FROM users WHERE email LIKE :em", {"em": em}),
    ]
    for sql, params in steps:
        await db.execute(text(sql), params)


async def one_run(args: argparse.Namespace, factory: Any, run_no: int) -> dict[str, Any]:
    tag = f"load-{uuid.uuid4().hex[:10]}"
    rng = random.Random(args.seed + run_no)
    pw_hash = hash_password("not-used-by-the-load-run")
    problems: list[str] = []

    # ---- 1. set up
    async with factory() as db:
        await purge(db, "load-")  # leftovers from a run that was killed
        await db.commit()
        org = Organization(type=OrganizationType.SCHOOL, name=tag, slug=tag)
        organizer = User(email=f"{tag}-org@example.com", password_hash=pw_hash)
        db.add_all([org, organizer])
        await db.flush()
        db.add(Membership(user_id=organizer.id, organization_id=org.id, role=Role.SCHOOL_ADMIN))
        users = [
            User(email=f"{tag}-{i}@example.com", password_hash=pw_hash)
            for i in range(args.bookings)
        ]
        db.add_all(users)
        await db.commit()
        organizer_headers = {"Authorization": f"Bearer {create_access_token(organizer.id)}"}
        tokens = [create_access_token(u.id) for u in users]
        user_ids = [u.id for u in users]

    # Shorter than the server's keep-alive, so we never reuse a connection it is closing.
    limits = httpx.Limits(
        max_connections=args.concurrency,
        max_keepalive_connections=args.concurrency,
        keepalive_expiry=2.0,
    )
    async with httpx.AsyncClient(base_url=args.api, timeout=60, limits=limits) as http:
        now = datetime.now(UTC)
        start = now + timedelta(days=10)
        r = await http.post(
            f"{API_V1}/events",
            headers=organizer_headers,
            json={
                "organization_id": str(org.id),
                "title": f"{tag} load event",
                "category": "networking",
                "starts_at": start.isoformat(),
                "ends_at": (start + timedelta(hours=8)).isoformat(),
                "max_party_size": 4,
                "slots": [
                    {
                        "label": label,
                        "starts_at": (start + timedelta(minutes=10 * i)).isoformat(),
                        "ends_at": (start + timedelta(minutes=10 * i + 9)).isoformat(),
                        "capacity": cap,
                        "position": i,
                    }
                    for i, (label, cap) in enumerate(SLOTS)
                ],
            },
        )
        if r.status_code != 201:
            raise SystemExit(f"could not create the event ({r.status_code}): {r.text[:300]}")
        event = r.json()
        pub = await http.post(f"{API_V1}/events/{event['id']}/publish", headers=organizer_headers)
        if pub.status_code != 200:
            raise SystemExit(f"could not publish the event ({pub.status_code}): {pub.text[:300]}")
        slots = {s["label"]: s for s in pub.json()["slots"]}

        # ---- 2. fire
        gate = asyncio.Semaphore(args.concurrency)
        latencies: list[float] = []
        outcomes: Counter[str] = Counter()
        accepted: dict[str, int] = {}  # booking id -> seats
        client_errors = 0

        async def send(i: int, key: str, slot_label: str, size: int) -> None:
            nonlocal client_errors
            body = {
                "slot_id": slots[slot_label]["id"],
                "participants": [{"full_name": f"Player {i}-{n}"} for n in range(size)],
                "others_consent_confirmed": size > 1,
            }
            async with gate:
                t0 = time.perf_counter()
                try:
                    res = await http.post(
                        f"{API_V1}/events/{event['id']}/bookings",
                        json=body,
                        headers={"Authorization": f"Bearer {tokens[i]}", "Idempotency-Key": key},
                    )
                except httpx.HTTPError as exc:
                    client_errors += 1
                    outcomes[f"client error {type(exc).__name__}"] += 1
                    return
                latencies.append(time.perf_counter() - t0)
            if res.status_code in (200, 201):
                data = res.json()
                accepted[data["id"]] = data["party_size"]
                outcomes[f"{res.status_code} booked"] += 1
            else:
                try:
                    code = res.json().get("error", {}).get("code", "?")
                except ValueError:
                    code = "not json"
                outcomes[f"{res.status_code} {code}"] += 1

        jobs = []
        for i in range(args.bookings):
            label = "hot" if rng.random() < 0.6 else rng.choice([s for s, _ in SLOTS[1:]])
            size = rng.choice(PARTY_SIZES)
            key = uuid.uuid4().hex
            jobs.append(send(i, key, label, size))
            if rng.random() < 0.10:  # the same request again, at the same moment
                jobs.append(send(i, key, label, size))
        rng.shuffle(jobs)
        t_start = time.perf_counter()
        await asyncio.gather(*jobs)
        elapsed = time.perf_counter() - t_start
        sent = len(jobs)

    # ---- 3. check the database
    active = "('pending_payment','confirmed','waitlisted')"
    async with factory() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT s.label, s.capacity, s.seats_confirmed, s.seats_held,"
                    " coalesce((SELECT sum(b.party_size) FROM bookings b WHERE b.slot_id = s.id"
                    f"  AND b.status = 'confirmed'), 0) AS real_confirmed,"
                    " coalesce((SELECT sum(b.party_size) FROM bookings b WHERE b.slot_id = s.id"
                    "  AND b.status = 'pending_payment'), 0) AS real_held"
                    " FROM event_slots s WHERE s.event_id = :e ORDER BY s.position"
                ),
                {"e": event["id"]},
            )
        ).all()
        in_db = {
            str(r[0]): r[1]
            for r in (
                await db.execute(
                    text(
                        f"SELECT id, party_size FROM bookings WHERE event_id = :e AND status IN {active}"
                    ),
                    {"e": event["id"]},
                )
            ).all()
        }
        per_user_max = await db.scalar(
            text(
                "SELECT coalesce(max(n), 0) FROM (SELECT count(*) n FROM bookings WHERE event_id = :e"
                f" AND status IN {active} GROUP BY booker_user_id) t"
            ),
            {"e": event["id"]},
        )
        await purge(db, tag)
        await db.commit()

    slot_report = []
    for label, cap, c_conf, c_held, r_conf, r_held in rows:
        slot_report.append(
            {"slot": label, "capacity": cap, "counter": c_conf + c_held, "real": int(r_conf + r_held)}
        )
        if c_conf + c_held > cap:
            problems.append(f"OVERBOOKED {label}: {c_conf + c_held} seats taken of {cap}")
        if (c_conf, c_held) != (int(r_conf), int(r_held)):
            problems.append(
                f"COUNTER DISAGREES {label}: counters {(c_conf, c_held)} vs recount {(int(r_conf), int(r_held))}"
            )
    if set(accepted) != set(in_db):
        problems.append(
            f"accepted bookings and database rows differ: {len(accepted)} said yes, {len(in_db)} rows"
            f" ({len(set(accepted) - set(in_db))} accepted but missing, {len(set(in_db) - set(accepted))} rows never acknowledged)"
        )
    if per_user_max and per_user_max > 1:
        problems.append(f"a user holds {per_user_max} active bookings")
    bad = {k: v for k, v in outcomes.items() if k.startswith("5") and "busy" not in k}
    if bad:
        problems.append(f"unexpected server errors: {bad}")

    lat = sorted(latencies)

    def pct(p: float) -> float:
        return round(lat[min(len(lat) - 1, int(len(lat) * p))] * 1000) if lat else 0

    return {
        "run": run_no,
        "requests_sent": sent,
        "seconds": round(elapsed, 1),
        "requests_per_second": round(sent / elapsed),
        "latency_ms": {
            "p50": pct(0.50),
            "p95": pct(0.95),
            "p99": pct(0.99),
            "max": round(max(lat) * 1000) if lat else 0,
            "mean": round(statistics.mean(lat) * 1000) if lat else 0,
        },
        "outcomes": dict(sorted(outcomes.items())),
        "seats_booked": sum(r["real"] for r in slot_report),
        "seats_capacity": sum(c for _, c in SLOTS),
        "slots": slot_report,
        "problems": problems,
    }


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8001")
    ap.add_argument("--bookings", type=int, default=3000)
    ap.add_argument("--concurrency", type=int, default=200)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    settings = get_settings()
    url = str(settings.database_url)
    why = refusal(url, str(settings.redis_url))
    if why:
        print(f"Refusing to start: {why}.")
        return 2
    engine = create_async_engine(url, pool_size=5)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    failed = 0
    for n in range(1, args.runs + 1):
        result = await one_run(args, factory, n)
        print(json.dumps(result))
        if result["problems"]:
            failed += 1
            for p in result["problems"]:
                print(f"  RUN {n} PROBLEM: {p}")
    await engine.dispose()
    print(f"{args.runs - failed} of {args.runs} runs clean")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
