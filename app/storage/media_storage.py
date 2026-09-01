"""MediaStorage port + adapters (docs/spec/05 storage adapter, 09 object storage).

Domain/business code depends ONLY on the ``MediaStorage`` abstract port. Production
uses ``S3CompatibleMediaStorage`` (Railway S3-compatible bucket; boto3 imported
lazily). Dev/test use ``InMemoryMediaStorage`` so tests never touch the network.

Provider migration (R2/S3/MinIO) changes only adapter configuration, never callers.
"""

from __future__ import annotations

import io
from abc import ABC, abstractmethod
from typing import BinaryIO

from app.config import get_settings


class MediaStorage(ABC):
    """Object-storage port. Keys are server-generated (never client filenames)."""

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> None:
        """Write bytes to ``key`` (private prefix). Immutable media: no overwrite semantics."""

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Return the object bytes. Raises KeyError if missing."""

    @abstractmethod
    def open_stream(self, key: str) -> BinaryIO:
        """Return a binary stream of the object (for StreamingResponse)."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete the object (no-op if absent)."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def create_download_url(self, key: str, ttl: int = 300) -> str | None:
        """Short-lived presigned GET URL, or None if the backend cannot presign."""

    @abstractmethod
    def create_upload_url(
        self, key: str, content_type: str, max_bytes: int, ttl: int = 300
    ) -> str | None:
        """Short-lived presigned PUT URL with constraints, or None if unsupported."""


class InMemoryMediaStorage(MediaStorage):
    """Process-local fake for dev/test. No network. Bytes live in a dict."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._objects[key] = (bytes(data), content_type)

    def get(self, key: str) -> bytes:
        try:
            return self._objects[key][0]
        except KeyError as exc:
            raise KeyError(f"media object not found: {key}") from exc

    def open_stream(self, key: str) -> BinaryIO:
        return io.BytesIO(self.get(key))

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    def exists(self, key: str) -> bool:
        return key in self._objects

    def create_download_url(self, key: str, ttl: int = 300) -> str | None:
        # The fake cannot presign; callers fall back to streaming through the app.
        return None

    def create_upload_url(
        self, key: str, content_type: str, max_bytes: int, ttl: int = 300
    ) -> str | None:
        return None


class S3CompatibleMediaStorage(MediaStorage):
    """Production adapter for the Railway S3-compatible bucket (boto3, imported lazily).

    Least-privilege creds (put/get on the app prefix); private bucket, no public list.
    """

    def __init__(
        self,
        *,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        region: str,
        endpoint: str,
    ) -> None:
        self._bucket = bucket
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._region = region
        self._endpoint = endpoint
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3  # lazy: tests using the fake never import boto3/network

            self._client = boto3.client(
                "s3",
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                region_name=self._region or None,
                endpoint_url=self._endpoint or None,
            )
        return self._client

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._get_client().put_object(
            Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
        )

    def get(self, key: str) -> bytes:
        obj = self._get_client().get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read()

    def open_stream(self, key: str) -> BinaryIO:
        obj = self._get_client().get_object(Bucket=self._bucket, Key=key)
        return obj["Body"]

    def delete(self, key: str) -> None:
        self._get_client().delete_object(Bucket=self._bucket, Key=key)

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._get_client().head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    def create_download_url(self, key: str, ttl: int = 300) -> str | None:
        return self._get_client().generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=ttl
        )

    def create_upload_url(
        self, key: str, content_type: str, max_bytes: int, ttl: int = 300
    ) -> str | None:
        return self._get_client().generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=ttl,
        )


_storage: MediaStorage | None = None


def get_media_storage() -> MediaStorage:
    """Return the process media-storage singleton.

    Uses ``S3CompatibleMediaStorage`` only when a bucket + endpoint are configured;
    otherwise the in-memory fake (dev/test — no network).
    """
    global _storage
    if _storage is not None:
        return _storage
    settings = get_settings()
    if settings.media_storage_configured:
        _storage = S3CompatibleMediaStorage(
            bucket=settings.media_bucket,
            access_key_id=settings.media_access_key_id,
            secret_access_key=settings.media_secret_access_key,
            region=settings.media_region,
            endpoint=settings.media_endpoint,
        )
    else:
        _storage = InMemoryMediaStorage()
    return _storage


def set_media_storage(storage: MediaStorage | None) -> None:
    """Override the singleton (tests). Pass None to reset."""
    global _storage
    _storage = storage
