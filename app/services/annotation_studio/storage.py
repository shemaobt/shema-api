"""GCS storage adapter for annotation-studio.

Mirrors the oral-collector signed-URL pattern (``recording_service``): a cached
``storage.Client`` plus cached ADC credentials refreshed on demand, used to mint
v4 signed PUT/GET URLs and to read/write bundle bytes. Keys are the logical
keys from ``naming.py``, used verbatim as object names in the dedicated bucket.
"""

from __future__ import annotations

import contextlib

import google.auth
import google.auth.transport.requests

from app.models.annotation_studio import PresignedUpload
from app.services.annotation_studio.constants import (
    GCS_AS_BUCKET,
    GCS_AS_PROJECT,
    SIGNED_GET_EXPIRY_SECONDS,
    SIGNED_PUT_EXPIRY_SECONDS,
)

_gcs_client = None
_signing_credentials = None


def _get_gcs_client():  # type: ignore[no-untyped-def]
    from google.cloud import storage

    global _gcs_client
    if _gcs_client is None:
        _gcs_client = storage.Client(project=GCS_AS_PROJECT)
    return _gcs_client


def _get_signing_info() -> tuple[str, str]:
    global _signing_credentials
    if _signing_credentials is None:
        _signing_credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    if not _signing_credentials.valid:
        _signing_credentials.refresh(google.auth.transport.requests.Request())
    creds = _signing_credentials
    return creds.service_account_email, creds.token  # type: ignore[attr-defined]


def _blob(key: str):  # type: ignore[no-untyped-def]
    client = _get_gcs_client()
    bucket = client.bucket(GCS_AS_BUCKET)
    return bucket.blob(key)


def presign_put(
    key: str, content_type: str, ttl_s: int = SIGNED_PUT_EXPIRY_SECONDS
) -> PresignedUpload:
    """Mint a v4 signed PUT URL the browser uploads the recording to directly."""
    from datetime import timedelta

    sa_email, access_token = _get_signing_info()
    url = _blob(key).generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=ttl_s),
        method="PUT",
        content_type=content_type,
        service_account_email=sa_email,
        access_token=access_token,
    )
    return PresignedUpload(
        url=url,
        method="PUT",
        storage_key=key,
        required_headers={"Content-Type": content_type},
        expires_in=ttl_s,
    )


def presign_get(key: str, ttl_s: int = SIGNED_GET_EXPIRY_SECONDS) -> str:
    """Mint a v4 signed GET URL for client-side playback / Tier C clip fetch."""
    from datetime import timedelta

    sa_email, access_token = _get_signing_info()
    return _blob(key).generate_signed_url(  # type: ignore[no-any-return]
        version="v4",
        expiration=timedelta(seconds=ttl_s),
        method="GET",
        service_account_email=sa_email,
        access_token=access_token,
    )


def get_bytes(key: str) -> bytes:
    return _blob(key).download_as_bytes()  # type: ignore[no-any-return]


def put_object(key: str, data: bytes, content_type: str) -> int:
    blob = _blob(key)
    blob.upload_from_string(data, content_type=content_type)
    return len(data)


def exists(key: str) -> bool:
    return _blob(key).exists()  # type: ignore[no-any-return]


def object_size(key: str) -> int | None:
    """The stored object's size in bytes, or ``None`` if it can't be determined.

    Fails open (returns ``None``) so a transient metadata error never blocks a
    legitimate upload from completing.
    """
    blob = _blob(key)
    with contextlib.suppress(Exception):
        blob.reload()
        return blob.size  # type: ignore[no-any-return]
    return None


def delete(key: str) -> None:
    # Deleting a never-uploaded key (status still pending) is not an error.
    with contextlib.suppress(Exception):
        _blob(key).delete()
