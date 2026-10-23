from collections.abc import Iterator
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.rate_limit import limiter, writes
from app.main import app
from tests.test_alumni_privacy import _make_actor

API = "/api/v1"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _calls(dependant: object) -> Iterator[object]:
    for sub in getattr(dependant, "dependencies", []):
        yield sub.call
        yield from _calls(sub)


def _write_routes() -> list[Any]:
    """Every route that changes something, with the prefix of the router it was included by."""
    found = []
    for included in app.routes:
        if type(included).__name__ != "_IncludedRouter":
            continue
        for route in included.effective_route_contexts():  # type: ignore[attr-defined]
            if WRITE_METHODS & set(route.methods or ()):
                found.append(route)
    return found


def _needs_login(route: Any) -> bool:
    names = {getattr(c, "__name__", "") for c in _calls(route.dependant)}
    return "get_current_user" in names


def _has_own_limit(route: Any) -> bool:
    return any(hasattr(c, "rate_limit_scope") for c in _calls(route.dependant))


def test_every_write_route_is_covered_by_the_app_wide_limit() -> None:
    assert writes.limit_writes in [d.dependency for d in app.router.dependencies]
    assert _write_routes()


def test_every_public_write_route_carries_a_limit_of_its_own() -> None:
    """Anyone on the internet can call these without logging in, so each has its own budget."""
    public = [r for r in _write_routes() if not _needs_login(r)]

    assert public, "expected sign-up, sign-in and password routes"
    missing = [f"{sorted(r.methods or [])} {r.path}" for r in public if not _has_own_limit(r)]
    assert missing == [], f"public write routes without their own rate limit: {missing}"


async def test_anonymous_writes_are_limited_by_address(client: AsyncClient) -> None:
    for _ in range(writes.ANONYMOUS_WRITES_PER_MINUTE):
        r = await client.post(f"{API}/auth/logout", json={"refresh_token": "x"})
        assert r.status_code == 401
    blocked = await client.post(f"{API}/auth/logout", json={"refresh_token": "x"})

    assert blocked.status_code == 429


async def test_signed_in_writes_are_limited_per_account_not_per_address(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(writes, "SIGNED_IN_WRITES_PER_MINUTE", 3)
    busy = await _make_actor(client)
    quiet = await _make_actor(client)
    for _ in range(3):
        await client.put(f"{API}/alumni/profile/skills", json={"names": []}, headers=busy.headers)

    blocked = await client.put(
        f"{API}/alumni/profile/skills", json={"names": []}, headers=busy.headers
    )
    fine = await client.put(
        f"{API}/alumni/profile/skills", json={"names": []}, headers=quiet.headers
    )

    assert blocked.status_code == 429
    assert fine.status_code != 429  # same address, different account


async def test_a_forged_token_gets_the_anonymous_budget(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(writes, "ANONYMOUS_WRITES_PER_MINUTE", 2)
    forged = {"Authorization": "Bearer not.a.real.token"}
    for _ in range(2):
        await client.post(f"{API}/auth/logout", json={"refresh_token": "x"}, headers=forged)

    blocked = await client.post(f"{API}/auth/logout", json={"refresh_token": "x"}, headers=forged)

    assert blocked.status_code == 429


async def test_reads_are_never_counted(client: AsyncClient) -> None:
    for _ in range(writes.ANONYMOUS_WRITES_PER_MINUTE + 5):
        assert (await client.get("/health/live")).status_code == 200


async def test_refresh_and_verify_confirm_have_their_own_limits(client: AsyncClient) -> None:
    refresh = [
        (await client.post(f"{API}/auth/refresh", json={"refresh_token": f"t{i}"})).status_code
        for i in range(writes.ANONYMOUS_WRITES_PER_MINUTE)
    ]
    assert set(refresh) == {401}


# ------------------------------------------------------------ the visitor's real address


class _Req:
    def __init__(self, headers: dict[str, str], host: str = "10.0.0.9") -> None:
        self.headers = headers
        self.client = type("C", (), {"host": host})()


def test_the_proxy_address_is_used_when_no_header_is_trusted() -> None:
    assert limiter.client_ip(_Req({"cf-connecting-ip": "203.0.113.7"})) == "10.0.0.9"  # type: ignore[arg-type]


def test_a_trusted_header_gives_the_real_visitor(monkeypatch: pytest.MonkeyPatch) -> None:
    class _S:
        trusted_client_ip_header = "cf-connecting-ip"

    monkeypatch.setattr(limiter, "get_settings", lambda: _S())

    assert limiter.client_ip(_Req({"cf-connecting-ip": "203.0.113.7"})) == "203.0.113.7"  # type: ignore[arg-type]
    assert limiter.client_ip(_Req({})) == "10.0.0.9"  # type: ignore[arg-type]


def test_the_first_entry_of_a_forwarded_list_is_the_visitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _S:
        trusted_client_ip_header = "x-forwarded-for"

    monkeypatch.setattr(limiter, "get_settings", lambda: _S())

    got = limiter.client_ip(_Req({"x-forwarded-for": "203.0.113.7, 10.1.1.1"}))  # type: ignore[arg-type]
    assert got == "203.0.113.7"
