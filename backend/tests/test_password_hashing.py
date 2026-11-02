"""
Password hashing: the Argon2 lane count (a past random 401, see security.py), that request
handlers hash off the event loop, and that only a few hashes run at once.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from argon2 import PasswordHasher
from httpx import AsyncClient
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.identity import security
from app.modules.identity.security import (
    hash_password,
    hash_password_async,
    verify_password,
    verify_password_async,
)
from tests.test_alumni_privacy import PASSWORD, _make_actor


def test_new_hashes_use_one_lane_and_keep_the_memory_and_time_cost() -> None:
    parts = hash_password(PASSWORD).split("$")
    assert parts[1] == "argon2id"
    assert parts[3] == "m=65536,t=3,p=1"


def test_a_hash_made_before_the_change_still_verifies() -> None:
    old = PasswordHasher(parallelism=4).hash(PASSWORD)
    assert "p=4" in old
    assert verify_password(PASSWORD, old)
    assert not verify_password(PASSWORD + "x", old)


def test_a_fresh_hash_always_verifies_and_a_wrong_password_never_does() -> None:
    # A smoke check, not a proof: the four-lane fault hit about one round in forty.
    for _ in range(30):
        stored = hash_password(PASSWORD)
        assert verify_password(PASSWORD, stored)
    assert not verify_password("not-the-password", stored)


# ------------------------------------------------------------- off the event loop, and capped


class _Recorder:
    """Stands in for the Argon2 hasher: remembers which thread did the work."""

    def __init__(self, real: PasswordHasher, delay: float = 0.0) -> None:
        self.real = real
        self.delay = delay
        self.threads: set[int] = set()
        self._lock = threading.Lock()
        self.running = 0
        self.most_at_once = 0

    def _enter(self) -> None:
        with self._lock:
            self.threads.add(threading.get_ident())
            self.running += 1
            self.most_at_once = max(self.most_at_once, self.running)
        if self.delay:
            time.sleep(self.delay)  # a blocking wait, like the real C call

    def _leave(self) -> None:
        with self._lock:
            self.running -= 1

    def hash(self, password: str) -> str:
        self._enter()
        try:
            return self.real.hash(password)
        finally:
            self._leave()

    def verify(self, stored: str, password: str) -> bool:
        self._enter()
        try:
            return self.real.verify(stored, password)
        finally:
            self._leave()


@pytest.mark.asyncio
async def test_sign_up_and_sign_in_hash_on_a_worker_thread_not_the_event_loop(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _Recorder(security._hasher)
    monkeypatch.setattr(security, "_hasher", recorder)
    loop_thread = threading.get_ident()

    actor = await _make_actor(client)  # register (a hash) then login (a verify)
    wrong = await client.post(
        "/api/v1/auth/login", json={"email": "nobody-here@example.com", "password": "Whatever-123"}
    )
    assert wrong.status_code == 401  # an unknown email still does the work, on a worker too
    change = await client.post(
        "/api/v1/auth/me/password",
        json={"current_password": PASSWORD, "new_password": PASSWORD + "-new"},
        headers=actor.headers,
    )
    assert change.status_code in (200, 204), change.text

    assert len(recorder.threads) >= 1
    assert loop_thread not in recorder.threads


@pytest.mark.asyncio
async def test_the_event_loop_keeps_running_while_hashes_are_computed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = hash_password(PASSWORD)  # made up front, before hashing is slowed down
    pool = ThreadPoolExecutor(max_workers=2)
    monkeypatch.setattr(security, "_pool", pool)
    monkeypatch.setattr(security, "_hasher", _Recorder(security._hasher, delay=0.4))
    gaps: list[float] = []
    stop = False

    async def ticker() -> None:
        last = time.perf_counter()
        while not stop:
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    task = asyncio.create_task(ticker())
    await asyncio.gather(*(verify_password_async(PASSWORD, stored) for _ in range(4)))
    stop = True
    await task
    pool.shutdown()
    # Four 0.4 s hashes on two workers take over a second. The loop was never held that long.
    assert max(gaps) < 0.25, max(gaps)


@pytest.mark.asyncio
async def test_twenty_one_simultaneous_hashes_all_finish_and_never_more_than_the_cap_run_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cap = 3
    pool = ThreadPoolExecutor(max_workers=cap)
    recorder = _Recorder(security._hasher, delay=0.05)
    monkeypatch.setattr(security, "_pool", pool)
    monkeypatch.setattr(security, "_hasher", recorder)
    fast: Any = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    recorder.real = fast  # keep the test quick: the point is the queueing, not the cost

    results = await asyncio.gather(
        *(hash_password_async(f"password-{i}") for i in range(21)), return_exceptions=True
    )
    pool.shutdown()

    assert not [r for r in results if isinstance(r, BaseException)]  # the 21st did not fail
    assert len(set(results)) == 21 and all(isinstance(r, str) for r in results)
    assert recorder.most_at_once == cap  # parallel up to the cap, and no further


def test_the_cap_is_a_setting_with_a_small_default_and_sane_limits() -> None:
    base: dict[str, Any] = {
        "_env_file": None,
        "secret_key": "k9Zr2vQp7LmX4wTb8NcY1hGfJdS6aUeV0oIxRtMq3Bn",
        "database_url": "postgresql+asyncpg://u:p@localhost:5432/x",
        "redis_url": "redis://localhost:6379/0",
    }
    assert Settings(**base).password_hash_concurrency == 2
    assert Settings(**base, password_hash_concurrency=4).password_hash_concurrency == 4
    for bad in (0, -1, 17):
        with pytest.raises(ValidationError):
            Settings(**base, password_hash_concurrency=bad)
    assert security._hash_pool()._max_workers == security.settings.password_hash_concurrency
