import asyncio
import contextlib
from datetime import timedelta

import google.auth
import google.auth.transport.requests
from google.api_core.exceptions import NotFound
from google.cloud import storage

from app.services.oral_collector.constants import GCS_OC_BUCKET, GCS_OC_PROJECT

GCS_PUBLIC_BASE = f"https://storage.googleapis.com/{GCS_OC_BUCKET}/"


async def upload_gcs_blob(blob_name: str, data: bytes, content_type: str) -> str:
    def _blocking() -> str:
        client = storage.Client(project=GCS_OC_PROJECT)
        bucket = client.bucket(GCS_OC_BUCKET)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(data, content_type=content_type)
        return f"{GCS_PUBLIC_BASE}{blob_name}"

    return await asyncio.to_thread(_blocking)


async def upload_gcs_object(
    bucket_name: str,
    blob_name: str,
    data: bytes,
    content_type: str,
    *,
    content_encoding: str | None = None,
) -> str:
    """Upload bytes to an arbitrary bucket, optionally tagging Content-Encoding.

    Tagging ``content_encoding="gzip"`` lets browsers transparently decompress
    the stream on fetch, so callers store the gzipped payload and consumers read
    plain JSON. Returns the ``gs://`` URI.
    """

    def _blocking() -> str:
        client = storage.Client(project=GCS_OC_PROJECT)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        if content_encoding:
            blob.content_encoding = content_encoding
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{bucket_name}/{blob_name}"

    return await asyncio.to_thread(_blocking)


async def generate_signed_download_url(
    bucket_name: str,
    blob_name: str,
    *,
    expiry_minutes: int = 15,
    response_content_type: str | None = None,
) -> str:
    """Mint a short-lived v4 signed GET URL for a private-bucket object.

    Signs with the ambient service account (google.auth.default) the same way
    the recording upload flow does, so no key file is required.
    """

    def _blocking() -> str:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if not creds.valid:
            creds.refresh(google.auth.transport.requests.Request())
        client = storage.Client(project=GCS_OC_PROJECT)
        blob = client.bucket(bucket_name).blob(blob_name)
        signed_url: str = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiry_minutes),
            method="GET",
            response_type=response_content_type,
            service_account_email=creds.service_account_email,  # type: ignore[attr-defined]
            access_token=creds.token,  # type: ignore[attr-defined]
        )
        return signed_url

    return await asyncio.to_thread(_blocking)


async def copy_gcs_blob(source_name: str, dest_name: str) -> None:
    def _blocking() -> None:
        client = storage.Client(project=GCS_OC_PROJECT)
        bucket = client.bucket(GCS_OC_BUCKET)
        source_blob = bucket.blob(source_name)
        bucket.copy_blob(source_blob, bucket, dest_name)

    await asyncio.to_thread(_blocking)


async def delete_gcs_object(bucket_name: str, blob_name: str) -> None:
    """Delete an object from an arbitrary bucket.

    Idempotent: a missing object is a no-op, so deleting a row whose object was already
    gone is not an error — the caller's goal (the object does not exist) is met.
    """

    def _blocking() -> None:
        client = storage.Client(project=GCS_OC_PROJECT)
        # delete() raises NotFound on a missing object; a 404 with the object gone is
        # already the goal, so treat it as success.
        with contextlib.suppress(NotFound):
            client.bucket(bucket_name).blob(blob_name).delete()

    await asyncio.to_thread(_blocking)


async def download_gcs_object(bucket_name: str, blob_name: str) -> bytes:
    """Read an object's bytes from an arbitrary bucket.

    Server-side reads only. A missing object raises ``NotFound`` rather than returning
    ``None``: every caller here reads an object a row already claims exists, so a silent
    empty read would be a bug wearing a valid return value.
    """

    def _blocking() -> bytes:
        client = storage.Client(project=GCS_OC_PROJECT)
        return bytes(client.bucket(bucket_name).blob(blob_name).download_as_bytes())

    return await asyncio.to_thread(_blocking)


def blob_name_from_url(gcs_url: str) -> str | None:
    if not gcs_url.startswith(GCS_PUBLIC_BASE):
        return None
    return gcs_url[len(GCS_PUBLIC_BASE) :]


def original_blob_name(blob_name: str) -> str:
    dot_idx = blob_name.rfind(".")
    if dot_idx == -1:
        return f"{blob_name}_original"
    return f"{blob_name[:dot_idx]}_original{blob_name[dot_idx:]}"


def content_type_for_format(fmt: str) -> str:
    mapping = {
        "m4a": "audio/mp4",
        "aac": "audio/aac",
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "ogg": "audio/ogg",
        "webm": "audio/webm",
    }
    return mapping.get(fmt.lower(), "application/octet-stream")
