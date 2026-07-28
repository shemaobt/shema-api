"""The generic platform bucket — it belongs to no app.

**Server-side only.** No browser touches this bucket: the API reads the bytes and streams
them. So, unlike `annotation_studio/storage.py` and the oral-collector, there is no signed
URL here, no CORS, no public access — it only has to exist and let the service account read
and write.

The bucket name comes from Settings (`GCS_PLATFORM_BUCKET`), not from a constant nailed into
the module the way `storage/upload.py` and `annotation_studio/constants.py` do it.
"""

from __future__ import annotations

import asyncio

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError

_gcs_client = None


def _client():  # type: ignore[no-untyped-def]
    from google.cloud import storage

    global _gcs_client
    if _gcs_client is None:
        _gcs_client = storage.Client()
    return _gcs_client


def _blob(key: str, settings: Settings):  # type: ignore[no-untyped-def]
    if not settings.gcs_platform_bucket:
        raise ValidationError("GCS_PLATFORM_BUCKET is not configured")
    return _client().bucket(settings.gcs_platform_bucket).blob(key)


class GcsPlatformStore:
    """Reads and writes opaque objects in the platform bucket."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def get(self, key: str) -> bytes | None:
        """The object's bytes, or `None` if it does not exist."""
        return await asyncio.to_thread(self._get_sync, key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        """Write the object (overwrites)."""
        await asyncio.to_thread(self._put_sync, key, data, content_type)

    def _get_sync(self, key: str) -> bytes | None:
        # `exists()` + download costs two GCS round trips; catching `NotFound` would cost
        # one. But `from google.cloud.exceptions import NotFound` imports from a TYPED
        # package (google-cloud-core), which makes mypy "wake up" the `google.cloud`
        # namespace — and then `ignore_missing_imports` in pyproject stops masking the five
        # `from google.cloud import storage` already in the repo, breaking the build in
        # files unrelated to this one. Two round trips is the price of not stepping on that.
        blob = _blob(key, self._settings)
        if not blob.exists():
            return None
        return bytes(blob.download_as_bytes())

    def _put_sync(self, key: str, data: bytes, content_type: str) -> None:
        _blob(key, self._settings).upload_from_string(data, content_type=content_type)
