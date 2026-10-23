from pathlib import Path

from app.core.config import get_settings
from app.infrastructure.storage.base import Storage, StorageError
from app.infrastructure.storage.local import LocalDiskStorage

__all__ = ["LocalDiskStorage", "Storage", "StorageError", "get_storage"]


def get_storage() -> Storage:
    """
    The one place the storage backend is chosen. Used as a FastAPI dependency, so tests
    swap it with app.dependency_overrides.
    """
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalDiskStorage(Path(settings.storage_local_path))
    raise StorageError("The R2 storage adapter has not been built yet.")
