"""The images the console uploads: app icons, avatars and the rest.

They live in the oral-collector's bucket, and always have — one bucket, not two — so the
name comes from the same setting (`GCS_OC_BUCKET`) rather than from a constant nailed
into this module. Splitting them would invent a distinction that does not exist:
[ADR 0029](../../../docs/adr/0029-the-oral-collectors-bucket-is-a-setting.md).
"""

import asyncio
import uuid

from fastapi import UploadFile
from google.cloud import storage

from app.core.config import get_settings

GCS_PROJECT = "gen-lang-client-0886209230"

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/svg+xml"}
MAX_FILE_SIZE = 5 * 1024 * 1024


async def upload_image(file: UploadFile, folder: str = "images") -> str:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"Unsupported file type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise ValueError("File size exceeds 5 MB limit")

    ext = _extension_for(file.content_type)
    blob_name = f"{folder}/{uuid.uuid4().hex}{ext}"
    bucket_name = get_settings().gcs_oc_bucket

    def _blocking() -> None:
        client = storage.Client(project=GCS_PROJECT)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(contents, content_type=file.content_type)

    await asyncio.to_thread(_blocking)
    return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"


def _extension_for(content_type: str | None) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
    }
    return mapping.get(content_type or "", ".bin")
