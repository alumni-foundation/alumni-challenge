from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.infrastructure.storage.base import Storage, StorageError
from app.infrastructure.storage.local import LocalDiskStorage
from app.infrastructure.storage.s3 import S3Storage

__all__ = ["LocalDiskStorage", "S3Storage", "Storage", "StorageError", "get_storage"]


@lru_cache
def _build_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalDiskStorage(Path(settings.storage_local_path))
    # Settings validation has already insisted that every one of these is present.
    assert settings.storage_endpoint_url and settings.storage_access_key
    assert settings.storage_secret_key and settings.storage_bucket_name
    return S3Storage(
        endpoint_url=settings.storage_endpoint_url,
        access_key=settings.storage_access_key,
        secret_key=settings.storage_secret_key.get_secret_value(),
        bucket=settings.storage_bucket_name,
    )


def get_storage() -> Storage:
    """
    The one place the storage backend is chosen (STORAGE_BACKEND=local|r2). Used as a FastAPI
    dependency, so tests swap it with app.dependency_overrides. Built once per process.
    """
    return _build_storage()
