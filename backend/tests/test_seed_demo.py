from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import cli
from app.core.permissions.roles import Role
from app.modules.alumni.models import AlumniProfile, ProfileVisibility, VerificationStatus
from app.modules.connections.models import Connection
from app.modules.identity.models import User
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.moderation.models import Report
from app.modules.organizations.models import Organization, OrganizationType
from app.seed import demo

API = "/api/v1"
PASSWORD = "seed-test-password-1"
OTHER_PASSWORD = "seed-test-password-2"


async def _grants(db: AsyncSession, email: str) -> set[tuple[Role, str | None]]:
    rows = await db.execute(
        select(Membership.role, Organization.slug)
        .join(User, User.id == Membership.user_id)
        .outerjoin(Organization, Organization.id == Membership.organization_id)
        .where(User.email == email, Membership.status == MembershipStatus.ACTIVE)
    )
    return {(role, slug) for role, slug in rows.all()}


async def _count(db: AsyncSession, model: type) -> int:
    return int(await db.scalar(select(func.count()).select_from(model)) or 0)


async def _login(client: AsyncClient, email: str, password: str) -> int:
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    return r.status_code


async def test_there_is_one_account_per_role_each_with_its_own_email(
    db_session: AsyncSession,
) -> None:
    result = await demo.seed_demo(db_session, password=PASSWORD)

    emails = [a.email for a in result.accounts]
    assert len(emails) == len(set(emails)), "two demo accounts share an email"
    assert all(e.endswith("@example.com") for e in emails)

    assert await _grants(db_session, demo.demo_email("super-admin")) == {(Role.SUPER_ADMIN, None)}
    assert await _grants(db_session, demo.demo_email("admin")) == {(Role.ADMIN, None)}
    assert await _grants(db_session, demo.demo_email("moderator")) == {(Role.MODERATOR, None)}
    assert await _grants(db_session, demo.demo_email("event-manager")) == {
        (Role.EVENT_MANAGER, "demo-school-a")
    }
    assert await _grants(db_session, demo.demo_email("sports-manager")) == {
        (Role.SPORTS_MANAGER, "demo-school-a")
    }


async def test_each_school_and_partner_admin_holds_only_their_own_organization(
    db_session: AsyncSession,
) -> None:
    await demo.seed_demo(db_session, password=PASSWORD)

    for suffix, slug in (("a", "demo-school-a"), ("b", "demo-school-b"), ("c", "demo-school-c")):
        assert await _grants(db_session, demo.demo_email("school-admin", suffix)) == {
            (Role.SCHOOL_ADMIN, slug)
        }
    for index, slug in ((1, "demo-partner-1"), (2, "demo-partner-2")):
        assert await _grants(db_session, demo.demo_email("partner-admin", str(index))) == {
            (Role.PARTNER_ADMIN, slug)
        }


async def test_it_creates_the_sample_data_the_brief_asks_for(db_session: AsyncSession) -> None:
    await demo.seed_demo(db_session, password=PASSWORD)

    schools = await _count_orgs(db_session, OrganizationType.SCHOOL)
    partners = await _count_orgs(db_session, OrganizationType.PARTNER)
    assert (schools, partners) == (3, 2)
    assert await _count(db_session, AlumniProfile) == demo.ALUMNI_COUNT
    assert await _count(db_session, Connection) > 0
    assert await _count(db_session, Report) >= 3

    visibilities = set(await db_session.scalars(select(AlumniProfile.profile_visibility)))
    assert visibilities == set(ProfileVisibility)
    statuses = set(await db_session.scalars(select(AlumniProfile.verification_status)))
    assert statuses == set(VerificationStatus)


async def _count_orgs(db: AsyncSession, org_type: OrganizationType) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(Organization).where(Organization.type == org_type)
        )
        or 0
    )


async def test_running_it_twice_changes_nothing(db_session: AsyncSession) -> None:
    first = await demo.seed_demo(db_session, password=PASSWORD)
    counts = {
        model: await _count(db_session, model)
        for model in (User, Membership, AlumniProfile, Connection, Report, Organization)
    }

    second = await demo.seed_demo(db_session, password=OTHER_PASSWORD)

    assert second.created_users == 0
    assert second.password_set_for == set()
    assert {a.email for a in second.accounts} == {a.email for a in first.accounts}
    for model, before in counts.items():
        assert await _count(db_session, model) == before, model.__name__


async def test_the_seeded_accounts_can_log_in_and_a_rerun_keeps_their_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await demo.seed_demo(db_session, password=PASSWORD)
    await demo.seed_demo(db_session, password=OTHER_PASSWORD)

    email = demo.demo_email("school-admin", "a")
    assert await _login(client, email, PASSWORD) == 200
    assert await _login(client, email, OTHER_PASSWORD) == 401


async def test_reset_passwords_gives_every_demo_account_the_new_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await demo.seed_demo(db_session, password=PASSWORD)
    result = await demo.seed_demo(db_session, password=OTHER_PASSWORD, reset_passwords=True)

    assert result.password_set_for == {a.email for a in result.accounts}
    email = demo.demo_email("admin")
    assert await _login(client, email, OTHER_PASSWORD) == 200
    assert await _login(client, email, PASSWORD) == 401


async def test_no_plain_text_password_is_stored(db_session: AsyncSession) -> None:
    await demo.seed_demo(db_session, password=PASSWORD)

    hashes = list(await db_session.scalars(select(User.password_hash)))
    assert hashes
    assert all(PASSWORD not in h and h.startswith("$argon2") for h in hashes)


def _use_session(monkeypatch: pytest.MonkeyPatch, db: AsyncSession) -> None:
    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield db

    monkeypatch.setattr(cli, "async_session_factory", _factory)


async def test_the_command_prints_the_password_once_and_only_for_new_accounts(
    monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    _use_session(monkeypatch, db_session)

    assert await cli._seed_demo(reset_passwords=False) == 0
    first = capsys.readouterr().out
    assert first.count("password: ") == 1
    printed = first.split("password: ", 1)[1].split()[0]
    assert len(printed) >= 12
    assert demo.demo_email("super-admin") in first

    assert await cli._seed_demo(reset_passwords=False) == 0
    second = capsys.readouterr().out
    assert "password: " not in second
    assert printed not in second
    assert "kept their password" in second


@pytest.mark.parametrize("environment", ["production", "staging"])
async def test_it_refuses_to_run_outside_development(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(environment=environment))

    def _must_not_touch_the_database() -> None:
        raise AssertionError("the command reached the database in a non-development environment")

    monkeypatch.setattr(cli, "async_session_factory", _must_not_touch_the_database)

    assert await cli._seed_demo(reset_passwords=False) == 1


def test_the_old_all_roles_account_command_is_gone() -> None:
    assert not hasattr(cli, "ensure_dev_account")
    assert not hasattr(cli, "_create_dev_account")


def test_the_demo_addresses_are_unique_per_account_kind() -> None:
    assert demo.demo_email("alumni", "01") != demo.demo_email("alumni", "02")
    assert demo.demo_email("school-admin", "a") != demo.demo_email("school-admin", "b")


async def test_the_seed_makes_a_meetup_a_paid_evening_a_four_slot_golf_day_and_a_draft(
    db_session: AsyncSession,
) -> None:
    from app.modules.events.models import Event, EventSlot, EventStatus
    from app.seed import demo_events

    await demo.seed_demo(db_session, password=PASSWORD)
    events = {
        e.title: e
        for e in await db_session.scalars(select(Event).where(Event.title.like("Demo %")))
    }
    assert set(events) >= {
        demo_events.MEETUP,
        demo_events.EVENING,
        demo_events.GOLF,
        demo_events.DRAFT,
    }
    assert events[demo_events.MEETUP].price_minor == 0
    assert events[demo_events.EVENING].price_minor == 150_000
    assert events[demo_events.GOLF].status == EventStatus.PUBLISHED
    assert events[demo_events.DRAFT].status == EventStatus.DRAFT
    golf_slots = list(
        await db_session.scalars(
            select(EventSlot).where(EventSlot.event_id == events[demo_events.GOLF].id)
        )
    )
    assert len(golf_slots) == 4 and {s.capacity for s in golf_slots} == {40}

    # a second run adds nothing
    await demo.seed_demo(db_session, password=PASSWORD)
    again = list(await db_session.scalars(select(Event).where(Event.title.like("Demo %"))))
    assert len(again) == len(events)
