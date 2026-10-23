import asyncio
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.infrastructure.storage.base import StorageError, validate_key

_NOT_FOUND_CODES = {"404", "NoSuchKey", "NotFound"}


def _code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


class S3Storage:
    """
    Any S3-compatible object store: Cloudflare R2 in production, MinIO on a developer's
    machine. The bucket must be private. Browsers never talk to it: files are read back
    through the API, which decides who may see them, and Cloudflare caches the public ones.

    boto3 is synchronous, so each call runs in a worker thread to keep the event loop free.
    """

    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "auto",
    ) -> None:
        self._bucket = bucket
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=30,
            ),
        )

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        validate_key(key)
        try:
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageError("Could not store the file.") from exc

    async def get(self, key: str) -> bytes:
        validate_key(key)
        try:
            response = await asyncio.to_thread(
                self._client.get_object, Bucket=self._bucket, Key=key
            )
            body: bytes = await asyncio.to_thread(response["Body"].read)
        except ClientError as exc:
            if _code(exc) in _NOT_FOUND_CODES:
                raise StorageError("File not found in storage.") from exc
            raise StorageError("Could not read the file.") from exc
        except BotoCoreError as exc:
            raise StorageError("Could not read the file.") from exc
        return body

    async def delete(self, key: str) -> None:
        validate_key(key)
        try:
            await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise StorageError("Could not delete the file.") from exc

    async def exists(self, key: str) -> bool:
        validate_key(key)
        try:
            await asyncio.to_thread(self._client.head_object, Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if _code(exc) in _NOT_FOUND_CODES:
                return False
            raise StorageError("Could not check the file.") from exc
        except BotoCoreError as exc:
            raise StorageError("Could not check the file.") from exc
        return True

    async def ensure_bucket(self) -> None:
        """Development and tests only: create the bucket if it is missing. Production buckets
        are created by hand, with the right access rules, never by the application."""
        try:
            await asyncio.to_thread(self._client.head_bucket, Bucket=self._bucket)
        except ClientError:
            try:
                await asyncio.to_thread(self._client.create_bucket, Bucket=self._bucket)
            except (ClientError, BotoCoreError) as exc:
                raise StorageError("Could not create the bucket.") from exc
