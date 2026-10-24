"""Slice 5.4: tickets, QR codes, claiming, check-in, roster, CSV, tee sheet and messages."""

import csv
import io
import re
import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.domain_events.handlers as handlers_module
from app.core.config import Settings
from app.core.permissions.roles import Role
from app.modules.audit.models import AuditLogEntry
from app.modules.bookings import seats
from app.modules.bookings import tickets as tickets_module
from app.modules.bookings.models import Booking, Ticket
from app.modules.domain_events.models import DomainEvent
from app.modules.domain_events.service import drain_pending
from app.modules.domain_events.service import publish as publish_event
from tests.conftest import Mailbox
from tests.test_alumni_privacy import Actor, _make_actor
from tests.test_bookings import _add_question, _book, _event
from tests.test_events_core import API, _create, _publish, _run_school

pytestmark = pytest.mark.asyncio


async def _tickets_of(client: AsyncClient, actor: Actor, booking_id: str) -> list[dict[str, Any]]:
    r = await client.get(f"{API}/bookings/{booking_id}/tickets", headers=actor.headers)
    assert r.status_code == 200, r.text
    data: list[dict[str, Any]] = r.json()
    return data


async def _booked_pair(
    client: AsyncClient, db: AsyncSession, **event_over: Any
) -> tuple[Actor, dict[str, Any], Actor, dict[str, Any], list[dict[str, Any]]]:
    admin, event = await _event(client, db, **event_over)
    member = await _make_actor(client)
    r = await _book(client, member, event, names=("Ann Alum", "Ben Friend"))
    assert r.status_code == 201, r.text
    booking = r.json()
    return admin, event, member, booking, await _tickets_of(client, member, booking["id"])


async def _scan(client: AsyncClient, actor: Actor, event_id: str, code: str) -> Any:
    return await client.post(
        f"{API}/events/{event_id}/check-in", json={"code": code}, headers=actor.headers
    )


# ------------------------------------------------------------------------ the tickets


async def test_a_confirmed_booking_has_one_ticket_per_person(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, _member, booking, tickets = await _booked_pair(client, db_session)
    assert [t["position"] for t in tickets] == [1, 2]
    assert [t["holder_name"] for t in tickets] == ["Ann Alum", "Ben Friend"]
    assert all(t["status"] == "valid" for t in tickets)
    rows = (
        await db_session.scalars(
            select(Ticket).where(Ticket.booking_id == uuid.UUID(booking["id"]))
        )
    ).all()
    by_id = {t.id.hex: t for t in rows}
    assert tickets_module.CODE_LENGTH == 64
    for t in tickets:
        code = t["code"]
        # 64 hex characters: 32 of ticket id (128 bits) then 32 of signature (128 bits).
        assert len(code) == 64 and re.fullmatch(r"[0-9a-f]{64}", code)
        ticket = by_id[code[:32]]
        assert len(code[32:]) == tickets_module._SIG_BYTES * 2 == 32
        assert code == tickets_module.make_code(ticket)
        assert code[32:] == tickets_module._sign(ticket.id, ticket.qr_version)
    assert len({t["code"] for t in tickets}) == 2
    assert tickets[0]["booking_reference"] == booking["reference"]
    stranger = await _make_actor(client)
    r = await client.get(f"{API}/bookings/{booking['id']}/tickets", headers=stranger.headers)
    assert r.status_code == 404
    assert (await client.get(f"{API}/bookings/{booking['id']}/tickets")).status_code == 401


async def test_an_unpaid_booking_has_no_tickets_until_it_is_confirmed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session, price_minor=100_000)
    member = await _make_actor(client)
    b = (await _book(client, member, event)).json()
    assert await _tickets_of(client, member, b["id"]) == []


async def test_the_ticket_page_opens_without_signing_in_and_shows_no_contact_details(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event, _, _, tickets = await _booked_pair(client, db_session)
    r = await client.get(f"{API}/tickets/{tickets[1]['code']}")
    assert r.status_code == 200, r.text
    assert r.headers["Cache-Control"] == "no-store"
    page = r.json()
    assert page["holder_name"] == "Ben Friend"
    assert page["event"]["id"] == event["id"]
    assert "email" not in r.text and "phone" not in r.text


async def test_forged_and_malformed_codes_are_just_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, _, _, tickets = await _booked_pair(client, db_session)
    code = tickets[0]["code"]
    flipped = code[:-1] + ("0" if code[-1] != "0" else "1")
    for bad in (
        flipped,
        code[:32] + "0" * 32,
        uuid.uuid4().hex + code[32:],
        "x" * 64,
        "abc",
        code[:40],
    ):
        assert (await client.get(f"{API}/tickets/{bad}")).status_code == 404, bad


async def test_the_signature_depends_on_the_signing_key(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, _, _, tickets = await _booked_pair(client, db_session)
    code = tickets[0]["code"]
    assert (await client.get(f"{API}/tickets/{code}")).status_code == 200
    monkeypatch.setattr(
        tickets_module,
        "get_settings",
        lambda: Settings(
            _env_file=None,
            secret_key="a-completely-different-secret-key-0000",  # type: ignore[arg-type]
            database_url="postgresql+asyncpg://u:p@localhost:5432/x",  # type: ignore[arg-type]
            redis_url="redis://localhost:6379/0",  # type: ignore[arg-type]
        ),
    )
    assert (await client.get(f"{API}/tickets/{code}")).status_code == 404


async def test_reissuing_kills_the_old_qr_and_gives_a_new_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event, member, booking, tickets = await _booked_pair(client, db_session)
    old = tickets[1]["code"]
    r = await client.post(
        f"{API}/bookings/{booking['id']}/tickets/2/reissue", headers=member.headers
    )
    assert r.status_code == 200, r.text
    new = r.json()["code"]
    assert new != old and new[:32] == old[:32]
    assert (await client.get(f"{API}/tickets/{old}")).status_code == 404
    assert (await client.get(f"{API}/tickets/{new}")).status_code == 200
    assert (await _scan(client, admin, event["id"], old)).status_code == 404
    other = await _make_actor(client)
    nope = await client.post(
        f"{API}/bookings/{booking['id']}/tickets/1/reissue", headers=other.headers
    )
    assert nope.status_code == 404
    assert (await _scan(client, admin, event["id"], new)).status_code == 200
    used = await client.post(
        f"{API}/bookings/{booking['id']}/tickets/2/reissue", headers=member.headers
    )
    assert used.status_code == 409


async def test_a_cancelled_booking_makes_every_ticket_void(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, member, booking, tickets = await _booked_pair(client, db_session)
    await client.post(f"{API}/bookings/{booking['id']}/cancel", headers=member.headers)
    page = await client.get(f"{API}/tickets/{tickets[0]['code']}")
    assert page.status_code == 200 and page.json()["status"] == "void"


# --------------------------------------------------------------------------- claiming


async def test_a_player_claims_their_ticket_and_then_finds_it_under_my_tickets(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, member, booking, tickets = await _booked_pair(client, db_session)
    ben = await _make_actor(client)
    code = tickets[1]["code"]
    r = await client.post(f"{API}/tickets/claim", json={"code": code}, headers=ben.headers)
    assert r.status_code == 200, r.text
    assert r.json()["claimed"] is True
    again = await client.post(f"{API}/tickets/claim", json={"code": code}, headers=ben.headers)
    assert again.status_code == 200
    mine = await client.get(f"{API}/tickets/mine", headers=ben.headers)
    assert [t["holder_name"] for t in mine.json()] == ["Ben Friend"]
    booker_sees = await client.get(f"{API}/tickets/mine", headers=member.headers)
    assert [t["holder_name"] for t in booker_sees.json()] == ["Ann Alum", "Ben Friend"]
    # Ben can see only his own ticket, not the booking
    assert (
        await client.get(f"{API}/bookings/{booking['id']}", headers=ben.headers)
    ).status_code == 404
    third = await _make_actor(client)
    taken = await client.post(f"{API}/tickets/claim", json={"code": code}, headers=third.headers)
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "already_claimed"
    assert (await client.post(f"{API}/tickets/claim", json={"code": code})).status_code == 401
    bogus = await client.post(f"{API}/tickets/claim", json={"code": "0" * 64}, headers=ben.headers)
    assert bogus.status_code == 404


# --------------------------------------------------------------------------- check-in


async def test_check_in_marks_a_person_once_and_a_second_scan_is_not_an_error(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event, _, _, tickets = await _booked_pair(client, db_session)
    first = await _scan(client, admin, event["id"], tickets[0]["code"])
    assert first.status_code == 200, first.text
    assert first.json()["result"] == "checked_in"
    assert first.json()["holder_name"] == "Ann Alum"
    assert first.json()["party_size"] == 2
    second = await _scan(client, admin, event["id"], tickets[0]["code"])
    assert second.status_code == 200
    assert second.json()["result"] == "already_checked_in"
    assert second.json()["checked_in_at"] == first.json()["checked_in_at"]
    assert second.json()["first_scan_by_you"] is True
    page = await client.get(f"{API}/tickets/{tickets[0]['code']}")
    assert page.json()["status"] == "checked_in"
    # the other person of the party is still to arrive
    other = await client.get(f"{API}/tickets/{tickets[1]['code']}")
    assert other.json()["status"] == "valid"
    audited = (
        await db_session.scalars(
            select(AuditLogEntry).where(AuditLogEntry.action == "ticket.check_in")
        )
    ).all()
    assert len(audited) == 1


async def test_check_in_names_what_is_wrong_with_a_ticket(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event, member, booking, tickets = await _booked_pair(client, db_session)
    other_admin, other_event = await _event(client, db_session)
    wrong = await _scan(client, other_admin, other_event["id"], tickets[0]["code"])
    assert wrong.status_code == 409 and wrong.json()["error"]["code"] == "wrong_event"
    await client.post(f"{API}/bookings/{booking['id']}/cancel", headers=member.headers)
    void = await _scan(client, admin, event["id"], tickets[0]["code"])
    assert void.status_code == 409 and void.json()["error"]["code"] == "void"
    forged = await _scan(client, admin, event["id"], "0" * 64)
    assert forged.status_code == 404


async def test_only_the_people_who_run_the_event_can_check_people_in(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event, member, _, tickets = await _booked_pair(client, db_session)
    _, elsewhere = await _run_school(client, db_session, Role.EVENT_MANAGER)
    for actor in (member, elsewhere):
        assert (await _scan(client, actor, event["id"], tickets[0]["code"])).status_code == 403
    no_login = await client.post(
        f"{API}/events/{event['id']}/check-in", json={"code": tickets[0]["code"]}
    )
    assert no_login.status_code == 401
    school_manager = await _make_actor(client)
    org_id = (await client.get(f"{API}/events/{event['id']}", headers=admin.headers)).json()[
        "organizer"
    ]["id"]
    await db_session.execute(
        text(
            "INSERT INTO memberships (id, user_id, organization_id, role, status)"
            " VALUES (gen_random_uuid(), :u, :o, 'event_manager', 'active')"
        ),
        {"u": school_manager.user_id, "o": org_id},
    )
    ok = await _scan(client, school_manager, event["id"], tickets[0]["code"])
    assert ok.status_code == 200 and ok.json()["first_scan_by_you"] is True


# ---------------------------------------------------------------------- the roster


async def test_the_roster_is_for_organizers_and_shows_contact_details(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event = await _event(client, db_session)
    member, other = await _make_actor(client), await _make_actor(client)
    r = await _book(
        client,
        member,
        event,
        participants=[
            {"full_name": "Ann Alum", "phone": "+254700000001"},
            {"full_name": "Ben Friend", "email": "ben@example.com"},
        ],
        others_consent_confirmed=True,
    )
    assert r.status_code == 201
    assert (await _book(client, other, event, names=("Cara Clark",))).status_code == 201
    url = f"{API}/events/{event['id']}/registrations"
    for who in (member, await _make_actor(client)):
        assert (await client.get(url, headers=who.headers)).status_code == 403
    assert (await client.get(url)).status_code == 401
    all_rows = await client.get(url, headers=admin.headers)
    assert all_rows.status_code == 200 and all_rows.headers["X-Total-Count"] == "2"
    assert all_rows.headers["Cache-Control"] == "no-store"
    first = next(x for x in all_rows.json() if x["booker_name"] == "Ann Alum")
    assert first["participants"][1]["email"] == "ben@example.com"
    assert first["participants"][0]["phone"] == "+254700000001"
    assert first["participants"][0]["ticket_status"] == "valid"
    found = await client.get(url, params={"q": "cara"}, headers=admin.headers)
    assert [x["booker_name"] for x in found.json()] == ["Cara Clark"]
    odd = await client.get(url, params={"q": "100%_"}, headers=admin.headers)
    assert odd.json() == []
    cancelled = await client.get(url, params={"status": "cancelled"}, headers=admin.headers)
    assert cancelled.json() == []
    page = await client.get(url, params={"limit": 1, "offset": 1}, headers=admin.headers)
    assert len(page.json()) == 1
    assert page.headers["X-Total-Count"] == "2"


async def test_the_tee_sheet_groups_people_by_slot(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event = await _event(client, db_session)
    add = await client.post(
        f"{API}/events/{event['id']}/slots",
        json={
            "label": "Afternoon",
            "starts_at": event["slots"][0]["starts_at"],
            "ends_at": event["slots"][0]["ends_at"],
            "capacity": 4,
            "position": 1,
        },
        headers=admin.headers,
    )
    assert add.status_code == 201, add.text
    detail = (await client.get(f"{API}/events/{event['id']}")).json()
    morning, afternoon = detail["slots"][0], detail["slots"][1]
    a, b = await _make_actor(client), await _make_actor(client)
    await client.post(
        f"{API}/events/{event['id']}/bookings",
        json={"slot_id": morning["id"], "participants": [{"full_name": "Early Bird"}]},
        headers={**a.headers, "Idempotency-Key": "a"},
    )
    await client.post(
        f"{API}/events/{event['id']}/bookings",
        json={"slot_id": afternoon["id"], "participants": [{"full_name": "Late Larry"}]},
        headers={**b.headers, "Idempotency-Key": "b"},
    )
    r = await client.get(f"{API}/events/{event['id']}/tee-sheet", headers=admin.headers)
    assert r.status_code == 200, r.text
    sheet = r.json()
    names = {s["slot"]["id"]: [x["booker_name"] for x in s["bookings"]] for s in sheet}
    assert names == {morning["id"]: ["Early Bird"], afternoon["id"]: ["Late Larry"]}
    assert (
        await client.get(f"{API}/events/{event['id']}/tee-sheet", headers=a.headers)
    ).status_code == 403


# ------------------------------------------------------------------------------ CSV


async def test_the_csv_lists_every_person_defuses_formulas_and_is_audited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event = await _event(client, db_session)
    member = await _make_actor(client)
    r = await _book(
        client,
        member,
        event,
        participants=[
            {"full_name": '=HYPERLINK("http://evil")'},
            {"full_name": "+1 plus", "email": "p@example.com"},
        ],
        others_consent_confirmed=True,
    )
    assert r.status_code == 201, r.text
    url = f"{API}/events/{event['id']}/registrations.csv"
    assert (await client.get(url, headers=member.headers)).status_code == 403
    res = await client.get(url, headers=admin.headers)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/csv")
    assert res.headers["Cache-Control"] == "no-store"
    assert "attachment" in res.headers["content-disposition"]
    lines = res.text.strip().splitlines()
    assert lines[0].startswith("reference,booking_status,slot")
    assert len(lines) == 3
    assert "'=HYPERLINK" in lines[1] and "'+1 plus" in lines[2]
    assert ",=HYPERLINK" not in res.text and ",+1 plus" not in res.text
    audited = (
        await db_session.scalars(
            select(AuditLogEntry).where(AuditLogEntry.action == "event.export_registrations")
        )
    ).all()
    assert len(audited) == 1 and audited[0].context["rows"] == 2


async def test_csv_exports_are_limited_to_five_an_hour(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event = await _event(client, db_session)
    url = f"{API}/events/{event['id']}/registrations.csv"
    codes = [(await client.get(url, headers=admin.headers)).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]


# ---------------------------------------------------------------------------- messages


async def test_a_message_is_queued_for_every_confirmed_booker_and_no_addresses_come_back(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    admin, event = await _event(client, db_session)
    stay, leave = await _make_actor(client), await _make_actor(client)
    assert (await _book(client, stay, event)).status_code == 201
    gone = (await _book(client, leave, event)).json()
    await client.post(f"{API}/bookings/{gone['id']}/cancel", headers=leave.headers)
    await drain_pending(db_session)
    mailbox.sent.clear()

    url = f"{API}/events/{event['id']}/messages"
    r = await client.post(
        url, json={"subject": "Parking", "body": "Use gate B."}, headers=admin.headers
    )
    assert r.status_code == 201, r.text
    assert r.json()["recipient_count"] == 1
    assert "@" not in r.text
    await drain_pending(db_session)
    assert len(mailbox.sent) == 1
    assert "Use gate B." in (mailbox.sent[0]["body"] or "")
    assert "Parking" in (mailbox.sent[0]["subject"] or "")
    assert (
        await client.post(url, json={"subject": "x", "body": "y"}, headers=stay.headers)
    ).status_code == 403


async def test_a_message_can_go_to_one_slot_and_must_be_one_line(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event = await _event(client, db_session)
    member = await _make_actor(client)
    await _book(client, member, event)
    url = f"{API}/events/{event['id']}/messages"
    other_slot = str(uuid.uuid4())
    bad_slot = await client.post(
        url, json={"subject": "s", "body": "b", "slot_id": other_slot}, headers=admin.headers
    )
    assert bad_slot.status_code == 422 and bad_slot.json()["error"]["code"] == "invalid_slot"
    multi = await client.post(
        url, json={"subject": "a\nBcc: x@evil", "body": "b"}, headers=admin.headers
    )
    assert multi.status_code == 422
    ok = await client.post(
        url,
        json={"subject": "s", "body": "b", "slot_id": event["slots"][0]["id"]},
        headers=admin.headers,
    )
    assert ok.status_code == 201 and ok.json()["recipient_count"] == 1


async def test_messages_are_limited_to_five_an_hour(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event = await _event(client, db_session)
    url = f"{API}/events/{event['id']}/messages"
    codes = [
        (
            await client.post(url, json={"subject": "s", "body": "b"}, headers=admin.headers)
        ).status_code
        for _ in range(6)
    ]
    assert codes == [201] * 5 + [429]


# ------------------------------------------------------------------------------ emails


async def test_the_confirmation_email_carries_every_ticket_link_and_named_players_get_their_own(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    r = await _book(
        client,
        member,
        event,
        participants=[
            {"full_name": "Ann Alum"},
            {"full_name": "Ben Friend", "email": "ben@example.com"},
            {"full_name": "Cara NoEmail"},
        ],
        others_consent_confirmed=True,
    )
    assert r.status_code == 201, r.text
    mailbox.sent.clear()
    await drain_pending(db_session)
    tickets = {
        t["holder_name"]: t["code"] for t in await _tickets_of(client, member, r.json()["id"])
    }
    to_booker = next(m for m in mailbox.sent if "Booking confirmed" in (m["subject"] or ""))
    for code in tickets.values():
        assert code in (to_booker["body"] or "")
    to_ben = [m for m in mailbox.sent if m["to"] == "ben@example.com"]
    assert len(to_ben) == 1
    assert tickets["Ben Friend"] in (to_ben[0]["body"] or "")
    assert tickets["Ann Alum"] not in (to_ben[0]["body"] or "")
    assert len([m for m in mailbox.sent if "Booking confirmed" in (m["subject"] or "")]) == 1


# ----------------------------------------------------------------------------- config


def _prod(**over: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "production",
        "secret_key": "k9Zr2vQp7LmX4wTb8NcY1hGfJdS6aUeV0oIxRtMq3Bn",
        "database_url": "postgresql+asyncpg://u:p@localhost:5432/x",
        "redis_url": "redis://localhost:6379/0",
        "mail_backend": "resend",
        "resend_api_key": "re_x",
        "frontend_url": "https://app.example.org",
        "storage_backend": "r2",
        "storage_endpoint_url": "https://x.invalid",
        "storage_access_key": "a",
        "storage_secret_key": "s",
        "storage_bucket_name": "b",
        **over,
    }
    return Settings(_env_file=None, **values)


def test_production_needs_its_own_ticket_signing_key() -> None:
    with pytest.raises(ValueError, match="TICKET_SIGNING_KEY"):
        _prod()
    with pytest.raises(ValueError, match="TICKET_SIGNING_KEY"):
        _prod(ticket_signing_key="short")
    with pytest.raises(ValueError, match="TICKET_SIGNING_KEY"):
        _prod(ticket_signing_key="k9Zr2vQp7LmX4wTb8NcY1hGfJdS6aUeV0oIxRtMq3Bn")
    assert _prod(ticket_signing_key="a-different-ticket-key-of-32-chars-plus!!")


async def test_tickets_exist_in_the_database_with_the_right_shape(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, _, booking, _ = await _booked_pair(client, db_session)
    rows = (
        await db_session.scalars(
            select(Ticket).where(Ticket.booking_id == uuid.UUID(booking["id"]))
        )
    ).all()
    assert len(rows) == 2 and {t.qr_version for t in rows} == {1}
    assert (
        await db_session.scalar(
            text("SELECT count(*) FROM domain_events WHERE event_type = 'booking.confirmed'")
        )
    ) == 1


# ------------------------------------------------- CSV: every user-supplied column is defused


async def test_no_csv_cell_can_start_a_spreadsheet_formula_whatever_the_column(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    draft = await _create(client, admin, school, capacity=10, max_party_size=2)
    await _add_question(
        client, admin, draft, key="note", label="Note", kind="text", asked_of="each_participant"
    )
    event = (await _publish(client, admin, draft["id"])).json()
    member = await _make_actor(client)
    evil = ['=HYPERLINK("http://evil","x")', "@SUM(1+1)", "+cmd|' /C calc'!A0", "-2+3"]
    r = await _book(
        client,
        member,
        event,
        participants=[
            {"full_name": evil[0], "phone": "+254700000001"},
            {"full_name": evil[1], "email": "p@example.com"},
        ],
        others_consent_confirmed=True,
        answers=[
            {"question_key": "note", "position": 1, "value": evil[2]},
            {"question_key": "note", "position": 2, "value": evil[3]},
        ],
    )
    assert r.status_code == 201, r.text

    res = await client.get(f"{API}/events/{event['id']}/registrations.csv", headers=admin.headers)
    assert res.status_code == 200, res.text
    cells = [c for row in csv.reader(io.StringIO(res.text)) for c in row]
    assert cells
    assert [c for c in cells if c[:1] in ("=", "+", "-", "@", "\t", "\r")] == []
    for value in evil:  # nothing is lost, just made safe
        assert "'" + value in cells


# ------------------------------------------------------ emails: one queued event per recipient


class _FlakyMailer:
    """Fails the first send to one address, then behaves."""

    def __init__(self, fail_once_to: str) -> None:
        self.fail_once_to = fail_once_to
        self.sent: list[dict[str, str | None]] = []
        self.failures = 0

    async def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        if to == self.fail_once_to and self.failures == 0:
            self.failures += 1
            raise RuntimeError("mail provider down")
        self.sent.append({"to": to, "subject": subject, "body": body})


async def test_a_failed_second_email_is_retried_alone_and_never_resends_the_first(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    flaky = _FlakyMailer(fail_once_to="ben@example.com")
    monkeypatch.setattr(handlers_module, "get_mailer", lambda: flaky)
    r = await _book(
        client,
        member,
        event,
        participants=[{"full_name": "Ann"}, {"full_name": "Ben", "email": "ben@example.com"}],
        others_consent_confirmed=True,
    )
    assert r.status_code == 201, r.text

    await drain_pending(db_session)  # the booker's email goes; Ben's send fails
    assert flaky.failures == 1
    assert len([m for m in flaky.sent if "Booking confirmed" in (m["subject"] or "")]) == 1
    assert [m for m in flaky.sent if m["to"] == "ben@example.com"] == []

    await db_session.execute(
        text("UPDATE domain_events SET next_attempt_at = NULL WHERE status = 'pending'")
    )
    await drain_pending(db_session)  # the retry
    assert len([m for m in flaky.sent if "Booking confirmed" in (m["subject"] or "")]) == 1
    to_ben = [m for m in flaky.sent if m["to"] == "ben@example.com"]
    assert len(to_ben) == 1 and "Your ticket" in (to_ben[0]["subject"] or "")


async def test_confirming_twice_queues_each_email_once(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    r = await _book(
        client,
        member,
        event,
        participants=[{"full_name": "Ann"}, {"full_name": "Ben", "email": "ben@example.com"}],
        others_consent_confirmed=True,
    )
    booking = await db_session.get(Booking, uuid.UUID(r.json()["id"]))
    assert booking is not None
    await tickets_module.announce_confirmed(db_session, booking)
    await tickets_module.announce_confirmed(db_session, booking)
    for kind in ("booking.confirmed", "booking.ticket_issued"):
        rows = (
            await db_session.scalars(select(DomainEvent).where(DomainEvent.event_type == kind))
        ).all()
        assert len(rows) == 1, kind


async def test_publishing_the_same_dedupe_key_twice_queues_one_event(
    db_session: AsyncSession,
) -> None:
    one = await publish_event(db_session, event_type="x.y", payload={"a": 1}, dedupe_key="k-1")
    two = await publish_event(db_session, event_type="x.y", payload={"a": 2}, dedupe_key="k-1")
    other = await publish_event(db_session, event_type="x.y", payload={"a": 3}, dedupe_key="k-2")
    assert one is not None and two is None and other is not None
    plain_1 = await publish_event(db_session, event_type="x.y", payload={})
    plain_2 = await publish_event(db_session, event_type="x.y", payload={})
    assert plain_1 is not None and plain_2 is not None  # no key: always queued


# -------------------------------------------------------------- the ticket page's rate limit


async def test_the_ticket_page_is_rate_limited_per_ip_but_generously(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, _, _, tickets = await _booked_pair(client, db_session)
    url = f"{API}/tickets/{tickets[0]['code']}"
    first = await client.get(url)
    assert first.status_code == 200 and first.headers["Cache-Control"] == "no-store"
    statuses = {(await client.get(url)).status_code for _ in range(599)}  # 600 in all
    assert statuses == {200}
    assert (await client.get(url)).status_code == 429  # the 601st


# ------------------------------------------------------- the test seams cannot act in production


def test_the_test_seams_are_off_by_default_and_nothing_in_the_app_turns_them_on() -> None:
    assert tickets_module.check_in_hook is None
    assert seats.capacity_check_hook is None
    app_dir = Path(__file__).resolve().parents[1] / "app"
    assigned = [
        f"{path.relative_to(app_dir)}:{n}"
        for path in app_dir.rglob("*.py")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if re.search(r"\b(check_in_hook|capacity_check_hook)\s*=", line)
    ]
    assert assigned == []
