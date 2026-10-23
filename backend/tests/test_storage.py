from pathlib import Path

import pytest

from app.infrastructure.storage import LocalDiskStorage, StorageError, get_storage


@pytest.fixture
def storage(tmp_path: Path) -> LocalDiskStorage:
    return LocalDiskStorage(tmp_path / "uploads")


async def test_a_stored_file_can_be_read_back_exactly(storage: LocalDiskStorage) -> None:
    await storage.put("public/logo/abc.png", b"\x89PNG bytes", content_type="image/png")

    assert await storage.exists("public/logo/abc.png") is True
    assert await storage.get("public/logo/abc.png") == b"\x89PNG bytes"


async def test_putting_the_same_key_again_replaces_the_file(storage: LocalDiskStorage) -> None:
    await storage.put("a/b.bin", b"one", content_type="application/octet-stream")
    await storage.put("a/b.bin", b"two", content_type="application/octet-stream")

    assert await storage.get("a/b.bin") == b"two"


async def test_a_missing_file_does_not_exist_and_cannot_be_read(storage: LocalDiskStorage) -> None:
    assert await storage.exists("nope/nothing.png") is False
    with pytest.raises(StorageError):
        await storage.get("nope/nothing.png")


async def test_deleting_removes_the_file_and_deleting_twice_is_fine(
    storage: LocalDiskStorage,
) -> None:
    await storage.put("a/b.bin", b"x", content_type="application/octet-stream")

    await storage.delete("a/b.bin")
    await storage.delete("a/b.bin")

    assert await storage.exists("a/b.bin") is False


async def test_a_write_leaves_no_temporary_files_behind(
    storage: LocalDiskStorage, tmp_path: Path
) -> None:
    await storage.put("a/b.bin", b"x", content_type="application/octet-stream")

    names = [p.name for p in (tmp_path / "uploads" / "a").iterdir()]
    assert names == ["b.bin"]


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
    storage: LocalDiskStorage, tmp_path: Path, key: str
) -> None:
    for operation in (
        storage.put(key, b"x", content_type="image/png"),
        storage.get(key),
        storage.delete(key),
        storage.exists(key),
    ):
        with pytest.raises(StorageError):
            await operation
    assert not (tmp_path / "outside.png").exists()


def test_the_configured_backend_is_local_disk() -> None:
    assert isinstance(get_storage(), LocalDiskStorage)
