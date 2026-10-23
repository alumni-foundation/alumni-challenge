import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.infrastructure.storage import LocalDiskStorage, S3Storage, Storage, StorageError
from app.infrastructure.storage import get_storage as real_get_storage
from app.main import app
from tests.test_alumni_privacy import _make_actor
from tests.test_file_upload import API, _encode, _photo, _upload


def _s3_endpoint() -> str | None:
    return os.environ.get("TEST_S3_ENDPOINT_URL")


@pytest.fixture(params=["local", "s3"])
async def storage(request: pytest.FixtureRequest, tmp_path: Path) -> AsyncIterator[Storage]:
    """Every contract test below runs against both backends: local disk, and an S3-compatible
    store (the emulator from docker-compose, or the one CI starts)."""
    if request.param == "local":
        yield LocalDiskStorage(tmp_path / "uploads")
        return
    endpoint = _s3_endpoint()
    if endpoint is None:
        if os.environ.get("CI"):
            pytest.fail("TEST_S3_ENDPOINT_URL must be set in CI so the S3 path is really tested")
        pytest.skip("no S3 emulator configured (TEST_S3_ENDPOINT_URL)")
    s3 = S3Storage(
        endpoint_url=endpoint,
        access_key="test",
        secret_key="test",
        bucket="alumni-test",
    )
    await s3.ensure_bucket()
    yield s3


@pytest.fixture
def prefix() -> str:
    """A folder of its own per test, so tests sharing one bucket cannot see each other."""
    return f"test-{uuid.uuid4().hex}"


async def test_a_stored_file_can_be_read_back_exactly(storage: Storage, prefix: str) -> None:
    key = f"{prefix}/public/logo/abc.png"
    await storage.put(key, b"\x89PNG bytes", content_type="image/png")

    assert await storage.exists(key) is True
    assert await storage.get(key) == b"\x89PNG bytes"


async def test_putting_the_same_key_again_replaces_the_file(storage: Storage, prefix: str) -> None:
    key = f"{prefix}/a/b.bin"
    await storage.put(key, b"one", content_type="application/octet-stream")
    await storage.put(key, b"two", content_type="application/octet-stream")

    assert await storage.get(key) == b"two"


async def test_a_missing_file_does_not_exist_and_cannot_be_read(
    storage: Storage, prefix: str
) -> None:
    key = f"{prefix}/nope/nothing.png"

    assert await storage.exists(key) is False
    with pytest.raises(StorageError):
        await storage.get(key)


async def test_deleting_removes_the_file_and_deleting_twice_is_fine(
    storage: Storage, prefix: str
) -> None:
    key = f"{prefix}/a/b.bin"
    await storage.put(key, b"x", content_type="application/octet-stream")

    await storage.delete(key)
    await storage.delete(key)

    assert await storage.exists(key) is False


async def test_binary_data_survives_unchanged(storage: Storage, prefix: str) -> None:
    key = f"{prefix}/bin/all-bytes.bin"
    data = bytes(range(256)) * 64
    await storage.put(key, data, content_type="application/octet-stream")

    assert await storage.get(key) == data


@pytest.mark.parametrize(
    "key",
    [
        "",
        "../outside.png",
        "a/../../outside.png",
        "a/../b.png",
        "/etc/passwd",
        "\\windows\\system32",
        "a\\..\\b.png",
        "a//b.png",
        "a/./b.png",
        "a/b\x00.png",
    ],
)
async def test_a_key_that_could_leave_the_storage_area_is_refused(
    storage: Storage, key: str
) -> None:
    for operation in (
        storage.put(key, b"x", content_type="image/png"),
        storage.get(key),
        storage.delete(key),
        storage.exists(key),
    ):
        with pytest.raises(StorageError):
            await operation


async def test_a_local_write_leaves_no_temporary_files_behind(tmp_path: Path) -> None:
    local = LocalDiskStorage(tmp_path / "uploads")
    await local.put("a/b.bin", b"x", content_type="application/octet-stream")

    assert [p.name for p in (tmp_path / "uploads" / "a").iterdir()] == ["b.bin"]


async def test_a_local_key_cannot_escape_the_folder_even_by_a_clever_name(
    tmp_path: Path,
) -> None:
    local = LocalDiskStorage(tmp_path / "uploads")

    with pytest.raises(StorageError):
        await local.put("a/../../outside.png", b"x", content_type="image/png")
    assert not (tmp_path / "outside.png").exists()


async def test_a_dead_object_store_is_a_storage_error_not_a_crash() -> None:
    dead = S3Storage(
        endpoint_url="http://127.0.0.1:1", access_key="x", secret_key="x", bucket="nope"
    )

    with pytest.raises(StorageError):
        await dead.get("a/b.png")
    with pytest.raises(StorageError):
        await dead.put("a/b.png", b"x", content_type="image/png")


def test_the_configured_backend_is_local_disk() -> None:
    assert isinstance(real_get_storage(), LocalDiskStorage)


async def test_a_whole_upload_works_through_the_object_store(
    client: AsyncClient, tmp_path: Path
) -> None:
    """The same upload, fetch and delete as with local disk, with the bytes in S3."""
    endpoint = _s3_endpoint()
    if endpoint is None:
        if os.environ.get("CI"):
            pytest.fail("TEST_S3_ENDPOINT_URL must be set in CI")
        pytest.skip("no S3 emulator configured (TEST_S3_ENDPOINT_URL)")
    s3 = S3Storage(
        endpoint_url=endpoint, access_key="test", secret_key="test", bucket="alumni-test"
    )
    await s3.ensure_bucket()
    app.dependency_overrides[real_get_storage] = lambda: s3
    user = await _make_actor(client)

    uploaded = await _upload(client, user, _encode(_photo(), "JPEG"))
    assert uploaded.status_code == 201, uploaded.text
    body: dict[str, Any] = uploaded.json()
    fetched = await client.get(body["url"])
    unsigned = await client.get(f"{API}/files/{body['id']}/content")
    deleted = await client.delete(f"{API}/files/{body['id']}", headers=user.headers)
    after = await client.get(body["url"])

    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/jpeg"
    assert unsigned.status_code == 404
    assert deleted.status_code == 204
    assert after.status_code == 404
