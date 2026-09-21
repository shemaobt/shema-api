"""The images the console uploads: app icons, avatars and the rest.

They live in the oral-collector's bucket, and always have — one bucket, not two — so the
name comes from the same setting (`GCS_OC_BUCKET`) rather than from a constant nailed
into this module. Splitting them would invent a distinction that does not exist:
[ADR 0029](../../../docs/adr/0029-the-oral-collectors-bucket-is-a-setting.md).
"""

import asyncio
import uuid
from typing import Any

from fastapi import UploadFile
from google.api_core.exceptions import Forbidden, GoogleAPIError, Unauthorized
from google.auth.exceptions import GoogleAuthError
from google.cloud import storage

from app.core.config import get_settings
from app.core.exceptions import StorageUnavailableError, UpstreamServiceError

GCS_PROJECT = "gen-lang-client-0886209230"

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/svg+xml"}
MAX_FILE_SIZE = 5 * 1024 * 1024

CREDENTIALS_UNREADABLE = (
    "Image storage is unavailable. The server could not load Google Cloud credentials; "
    "check the service account credentials for this deployment."
)
CREDENTIALS_REFUSED = (
    "Image storage is unavailable. Google Cloud Storage refused this deployment's "
    "credentials; check the service account's access to the uploads bucket."
)


async def upload_image(file: UploadFile, folder: str = "images") -> str:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"Unsupported file type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise ValueError("File size exceeds 5 MB limit")

    ext = _extension_for(file.content_type)
    blob_name = f"{folder}/{uuid.uuid4().hex}{ext}"
    bucket_name = get_settings().gcs_oc_bucket

    def _connect() -> Any:
        return storage.Client(project=GCS_PROJECT)

    def _upload(client: Any) -> None:
        blob = client.bucket(bucket_name).blob(blob_name)
        blob.upload_from_string(contents, content_type=file.content_type)

    # Building the client is what resolves this deployment's credentials, so an OSError
    # there is an unreadable key file — ours to fix, and the only thing that earns a message
    # naming the service account. Past that point only GCS refusing the credentials still
    # points here: an OSError is the network and a GoogleAPIError is the provider answering
    # badly, and both are the provider failing, which is 502/UPSTREAM_ERROR and not 503.
    try:
        client = await asyncio.to_thread(_connect)
    except (GoogleAuthError, OSError) as e:
        raise StorageUnavailableError(CREDENTIALS_UNREADABLE) from e

    try:
        await asyncio.to_thread(_upload, client)
    except (GoogleAuthError, Forbidden, Unauthorized) as e:
        raise StorageUnavailableError(CREDENTIALS_REFUSED) from e
    except (GoogleAPIError, OSError) as e:
        raise UpstreamServiceError("Google Cloud Storage could not store the image.") from e
    return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"


def _extension_for(content_type: str | None) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
    }
    return mapping.get(content_type or "", ".bin")
