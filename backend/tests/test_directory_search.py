import random
import string
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.alumni.models import AlumniProfile, ProfileVisibility
from app.modules.identity.models import User, UserStatus
from tests.test_alumni_privacy import Actor, _grant, _make_actor, _make_school

API = "/api/v1"


def _token() -> str:
    """A random letters-only word, so each test finds only its own profiles even when the
    database already holds other data."""
    return "zq" + "".join(random.choices(string.ascii_lowercase, k=10))


async def _profile(client: AsyncClient, actor: Actor, **fields: object) -> str:
    body: dict[str, object] = {"full_name": "Plain Person", "profile_visibility": "members_only"}
    body.update(fields)
    r = await client.post(f"{API}/alumni/profile", json=body, headers=actor.headers)
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _search(client: AsyncClient, viewer: Actor, **params: object) -> Response:
    r = await client.get(f"{API}/alumni/directory", params=params, headers=viewer.headers)
    assert r.status_code == 200, r.text
    return r


def _ids(r: Response) -> list[str]:
    return [p["id"] for p in r.json()]


# ------------------------------------------------------------------ basics


async def test_directory_needs_login(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/alumni/directory?q=anything")).status_code == 401


async def test_search_matches_name_prefixes_and_requires_every_word(client: AsyncClient) -> None:
    tok = _token()
    owner = await _make_actor(client)
    viewer = await _make_actor(client)
    pid = await _profile(client, owner, full_name=f"Wanjiku {tok}")

    assert pid in _ids(await _search(client, viewer, q=tok))
    assert pid in _ids(await _search(client, viewer, q=tok[:5]))  # prefix
    assert pid in _ids(await _search(client, viewer, q=f"WANJ {tok[:4]}"))  # two words, any case
    assert pid not in _ids(await _search(client, viewer, q=f"{tok} nomatchingword"))


async def test_every_searchable_field_finds_the_profile(client: AsyncClient) -> None:
    viewer = await _make_actor(client)
    found: dict[str, tuple[str, str]] = {}
    for field in ("profession", "company", "country", "bio"):
        tok = _token()
        owner = await _make_actor(client)
        pid = await _profile(client, owner, **{field: f"{tok} stuff"})
        found[field] = (tok, pid)
    for field, (tok, pid) in found.items():
        assert pid in _ids(await _search(client, viewer, q=tok)), field


async def test_skills_and_interests_are_searchable_and_follow_changes(
    client: AsyncClient,
) -> None:
    skill, interest, new_skill = _token(), _token(), _token()
    owner = await _make_actor(client)
    viewer = await _make_actor(client)
    pid = await _profile(client, owner)

    await client.put(f"{API}/alumni/profile/skills", json={"names": [skill]}, headers=owner.headers)
    await client.put(
        f"{API}/alumni/profile/interests", json={"names": [interest]}, headers=owner.headers
    )
    assert pid in _ids(await _search(client, viewer, q=skill))
    assert pid in _ids(await _search(client, viewer, q=interest))

    # replacing the skills removes the old one from search and adds the new one
    await client.put(
        f"{API}/alumni/profile/skills", json={"names": [new_skill]}, headers=owner.headers
    )
    assert pid not in _ids(await _search(client, viewer, q=skill))
    assert pid in _ids(await _search(client, viewer, q=new_skill))


async def test_editing_a_profile_updates_search(client: AsyncClient) -> None:
    old, new = _token(), _token()
    owner = await _make_actor(client)
    viewer = await _make_actor(client)
    pid = await _profile(client, owner, bio=f"about {old}")
    assert pid in _ids(await _search(client, viewer, q=old))

    r = await client.patch(
        f"{API}/alumni/profile", json={"bio": f"about {new}"}, headers=owner.headers
    )
    assert r.status_code == 200
    assert pid not in _ids(await _search(client, viewer, q=old))
    assert pid in _ids(await _search(client, viewer, q=new))


async def test_a_row_written_straight_to_the_database_is_searchable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Proves the database trigger does the work, not the application code."""
    tok = _token()
    owner = await _make_actor(client)
    viewer = await _make_actor(client)
    profile = AlumniProfile(
        user_id=owner.user_id,
        full_name=f"Direct {tok}",
        profile_visibility=ProfileVisibility.MEMBERS_ONLY,
    )
    db_session.add(profile)
    await db_session.flush()
    assert str(profile.id) in _ids(await _search(client, viewer, q=tok))


# ----------------------------------------------------------------- privacy


async def test_hidden_profiles_never_appear_in_search_or_the_count(client: AsyncClient) -> None:
    tok = _token()
    viewer = await _make_actor(client)
    visible_owner = await _make_actor(client)
    visible = await _profile(client, visible_owner, full_name=f"Open {tok}")

    hidden: list[str] = []
    for vis in ("private", "connections_only"):
        owner = await _make_actor(client)
        # the search word is in the name, the company and the bio of every hidden profile
        hidden.append(
            await _profile(
                client,
                owner,
                full_name=f"Hidden {tok}",
                company=tok,
                bio=tok,
                profile_visibility=vis,
            )
        )

    r = await _search(client, viewer, q=tok)
    assert _ids(r) == [visible]
    assert r.headers["X-Total-Count"] == "1"
    for pid in hidden:
        assert pid not in _ids(r)


async def test_hidden_profiles_stay_hidden_from_their_own_connections(
    client: AsyncClient,
) -> None:
    tok = _token()
    owner = await _make_actor(client)
    friend = await _make_actor(client)
    pid = await _profile(
        client, owner, full_name=f"Friends {tok}", profile_visibility="connections_only"
    )
    req = await client.post(
        f"{API}/connections", json={"addressee_id": str(owner.user_id)}, headers=friend.headers
    )
    await client.patch(f"{API}/connections/{req.json()['id']}/accept", headers=owner.headers)

    # connected, so they can open the profile directly, but a scan still does not list it
    assert (await client.get(f"{API}/alumni/{pid}", headers=friend.headers)).status_code == 200
    assert pid not in _ids(await _search(client, friend, q=tok))


async def test_suspended_and_deleted_accounts_are_not_discoverable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tok = _token()
    viewer = await _make_actor(client)
    users = []
    pids = []
    for _ in range(2):
        owner = await _make_actor(client)
        users.append(owner.user_id)
        pids.append(await _profile(client, owner, full_name=f"Gone {tok}"))
    assert set(pids) <= set(_ids(await _search(client, viewer, q=tok)))

    for uid, st in zip(users, (UserStatus.SUSPENDED, UserStatus.DELETED), strict=True):
        await db_session.execute(update(User).where(User.id == uid).values(status=st))
    await db_session.flush()
    r = await _search(client, viewer, q=tok)
    assert _ids(r) == []
    assert r.headers["X-Total-Count"] == "0"

    await db_session.execute(
        update(User).where(User.id == users[0]).values(status=UserStatus.ACTIVE)
    )
    await db_session.flush()
    assert _ids(await _search(client, viewer, q=tok)) == [pids[0]]


async def test_the_search_document_is_never_sent_to_clients(client: AsyncClient) -> None:
    tok = _token()
    owner = await _make_actor(client)
    pid = await _profile(client, owner, full_name=f"Leak {tok}")
    listed = (await _search(client, owner, q=tok)).json()[0]
    single = (await client.get(f"{API}/alumni/{pid}", headers=owner.headers)).json()
    mine = (await client.get(f"{API}/alumni/profile/me", headers=owner.headers)).json()
    for body in (listed, single, mine):
        assert "search_vector" not in body


# ----------------------------------------------------------------- ranking


async def test_name_matches_rank_above_bio_matches(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tok = _token()
    viewer = await _make_actor(client)
    in_bio = await _profile(client, await _make_actor(client), bio=f"I like {tok}")
    in_company = await _profile(client, await _make_actor(client), company=tok)
    in_name = await _profile(client, await _make_actor(client), full_name=f"{tok} Smith")

    # Dated so that "newest first" gives exactly the WRONG order (bio, company, name). The
    # only way the name match can come first is real relevance ranking.
    now = datetime.now(UTC)
    for pid, age in ((in_bio, 0), (in_company, 1), (in_name, 2)):
        await db_session.execute(
            update(AlumniProfile)
            .where(AlumniProfile.id == uuid.UUID(pid))
            .values(created_at=now - timedelta(days=age))
        )
    await db_session.flush()

    order = _ids(await _search(client, viewer, q=tok))
    assert order == [in_name, in_company, in_bio]


# ----------------------------------------------------------------- filters


async def test_filters_narrow_results_and_combine_with_search(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tok = _token()
    viewer = await _make_actor(client)
    school = await _make_school(db_session)
    admin = await _make_actor(client)
    await _grant(db_session, admin.user_id, Role.ADMIN, None)

    a_owner, b_owner = await _make_actor(client), await _make_actor(client)
    a = await _profile(
        client,
        a_owner,
        full_name=f"A {tok}",
        country="Kenya",
        graduation_year=2010,
        school_id=str(school.id),
    )
    b = await _profile(
        client, b_owner, full_name=f"B {tok}", country="Uganda", graduation_year=2015
    )
    await client.put(
        f"{API}/alumni/profile/skills", json={"names": ["Rustacean"]}, headers=a_owner.headers
    )
    verified = await client.patch(
        f"{API}/alumni/{a}/verify", json={"verified": True}, headers=admin.headers
    )
    assert verified.status_code == 200, verified.text

    assert set(_ids(await _search(client, viewer, q=tok))) == {a, b}
    assert _ids(await _search(client, viewer, q=tok, country="kenya")) == [a]  # any case
    assert _ids(await _search(client, viewer, q=tok, country="Uganda")) == [b]
    assert _ids(await _search(client, viewer, q=tok, graduation_year=2015)) == [b]
    assert _ids(await _search(client, viewer, q=tok, school_id=str(school.id))) == [a]
    assert _ids(await _search(client, viewer, q=tok, verified="true")) == [a]
    assert _ids(await _search(client, viewer, q=tok, skill="rustacean")) == [a]
    assert _ids(await _search(client, viewer, q=tok, skill="rustacean", country="Uganda")) == []
    # a filter with no search text works too
    assert a in _ids(await _search(client, viewer, school_id=str(school.id)))


async def test_filter_values_are_validated(client: AsyncClient) -> None:
    viewer = await _make_actor(client)
    for params in (
        {"graduation_year": 1800},
        {"school_id": "not-a-uuid"},
        {"limit": 0},
        {"offset": -1},
    ):
        r = await client.get(f"{API}/alumni/directory", params=params, headers=viewer.headers)
        assert r.status_code == 422, params


# -------------------------------------------------------------- pagination


async def test_pagination_pages_do_not_overlap_and_total_is_exact(client: AsyncClient) -> None:
    tok = _token()
    viewer = await _make_actor(client)
    made = [
        await _profile(client, await _make_actor(client), full_name=f"P{i} {tok}") for i in range(5)
    ]

    seen: list[str] = []
    for offset, expected in ((0, 2), (2, 2), (4, 1), (6, 0)):
        r = await _search(client, viewer, q=tok, limit=2, offset=offset)
        assert r.headers["X-Total-Count"] == "5"
        assert len(r.json()) == expected
        seen.extend(_ids(r))
    assert sorted(seen) == sorted(made)
    assert len(set(seen)) == 5


async def test_total_count_stops_at_the_cap_but_results_still_page_normally(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.alumni import directory

    monkeypatch.setattr(directory, "TOTAL_COUNT_CAP", 3)
    tok = _token()
    viewer = await _make_actor(client)
    made = [
        await _profile(client, await _make_actor(client), full_name=f"C{i} {tok}") for i in range(5)
    ]

    first = await _search(client, viewer, q=tok, limit=2, offset=0)
    last = await _search(client, viewer, q=tok, limit=2, offset=4)
    assert first.headers["X-Total-Count"] == "3"  # capped: "3 or more"
    assert len(last.json()) == 1  # but paging still reaches the real end
    assert set(_ids(first)) | set(_ids(last)) <= set(made)


async def test_without_search_text_newest_profiles_come_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    viewer = await _make_actor(client)
    first = await _profile(client, await _make_actor(client), full_name="Older Person")
    second = await _profile(client, await _make_actor(client), full_name="Newer Person")
    # Rows made inside one test share a transaction timestamp, so set real ones.
    now = datetime.now(UTC)
    await db_session.execute(
        update(AlumniProfile)
        .where(AlumniProfile.id == uuid.UUID(first))
        .values(created_at=now - timedelta(days=2))
    )
    await db_session.execute(
        update(AlumniProfile)
        .where(AlumniProfile.id == uuid.UUID(second))
        .values(created_at=now - timedelta(days=1))
    )
    await db_session.flush()

    r = await _search(client, viewer, limit=100)
    assert "X-Total-Count" in r.headers
    ids = _ids(r)
    assert ids.index(second) < ids.index(first)


# -------------------------------------------------------------- bad input


@pytest.mark.parametrize(
    "text",
    [
        "'; DROP TABLE users; --",
        "a & | ! ( ) : * <-> \\ ' \"",
        "john:*:* &&& (((",
        "emoji 🎉 test",
        "ünïcödé wörd",
        "x" * 100,
        " ".join(["ab"] * 33),
    ],
)
async def test_hostile_or_odd_search_text_never_breaks_the_endpoint(
    client: AsyncClient, text: str
) -> None:
    viewer = await _make_actor(client)
    r = await client.get(f"{API}/alumni/directory", params={"q": text}, headers=viewer.headers)
    assert r.status_code == 200, r.text


async def test_search_text_with_no_searchable_words_returns_nothing(client: AsyncClient) -> None:
    viewer = await _make_actor(client)
    await _profile(client, await _make_actor(client), full_name="Someone Visible")
    r = await _search(client, viewer, q="!!! ??? ---")
    assert r.json() == []
    assert r.headers["X-Total-Count"] == "0"


async def test_blank_search_text_acts_like_no_search(client: AsyncClient) -> None:
    viewer = await _make_actor(client)
    pid = await _profile(client, await _make_actor(client), full_name="Blank Query Person")
    assert pid in _ids(await _search(client, viewer, q="   ", limit=100))


async def test_overlong_search_text_is_rejected(client: AsyncClient) -> None:
    viewer = await _make_actor(client)
    r = await client.get(f"{API}/alumni/directory", params={"q": "x" * 101}, headers=viewer.headers)
    assert r.status_code == 422


async def test_accented_names_are_found(client: AsyncClient) -> None:
    tok = _token()
    viewer = await _make_actor(client)
    pid = await _profile(client, await _make_actor(client), full_name=f"Zoë Ngũgĩ {tok}")
    assert pid in _ids(await _search(client, viewer, q="zoë"))
    assert pid in _ids(await _search(client, viewer, q=f"ngũgĩ {tok}"))
