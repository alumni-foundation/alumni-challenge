import asyncio
import os
import tempfile
from pathlib import Path

from app.infrastructure.storage.base import StorageError, validate_key


class LocalDiskStorage:
    """
    Files on local disk, for development and tests. Not for production: a container's disk
    is lost on redeploy.

    The content type is accepted to match the interface but not kept: on disk the type is
    recorded in the database, and the file is served with that, never guessed from a name.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        validate_key(key)
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise StorageError("Invalid storage key.")
        return path

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        path = self._path(key)
        await asyncio.to_thread(self._write, path, data)

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temporary file in the same folder, then rename: a reader never sees a
        # half-written file.
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".upload-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise StorageError("File not found in storage.") from exc

    async def delete(self, key: str) -> None:
        path = self._path(key)
        await asyncio.to_thread(path.unlink, missing_ok=True)

    async def exists(self, key: str) -> bool:
        path = self._path(key)
        return await asyncio.to_thread(path.is_file)
