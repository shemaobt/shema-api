"""No module may name the oral-collector's bucket in its own source.

The bucket holding the oral-collector's audio — and the platform's images, the same
bucket today — was a literal written twice, so a second service built from this image
could not be pointed anywhere: it addressed production by construction. Staging's
database is a branch of production's, so its rows carry production's ids and its object
keys; writing, cleaning or deleting a recording on staging reached production's file.
Here the bucket is an environment variable whose default is production's name, so an
unset variable deploys what it always deployed and staging names its own.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from app.core.config import Settings, get_settings
from app.services.oral_collector import acousteme_service
from app.services.oral_collector.gcs_utils import (
    blob_name_from_url,
    copy_gcs_blob,
    gcs_public_base,
    original_blob_name,
    upload_gcs_blob,
)
from app.services.storage.upload import upload_image
from tests.oral_collector_harness import PRODUCTION_BUCKET, STAGING_BUCKET

APP = Path(__file__).resolve().parent.parent / "app"

#: The one module allowed to name the bucket. Matching on the file name alone would
#: exempt any `config.py` anywhere under `app/`, including one that does not exist yet.
CONFIG = (APP / "core" / "config.py").resolve()

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


def test_the_bucket_defaults_to_the_production_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing variable deploys what has always been deployed."""
    monkeypatch.delenv("GCS_OC_BUCKET", raising=False)

    settings = Settings(database_url=TEST_DATABASE_URL)

    assert settings.gcs_oc_bucket == PRODUCTION_BUCKET


def test_the_env_var_sets_the_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    """What the staging deploy does: set GCS_OC_BUCKET on the Cloud Run service."""
    monkeypatch.setenv("GCS_OC_BUCKET", STAGING_BUCKET)

    settings = Settings(database_url=TEST_DATABASE_URL)

    assert settings.gcs_oc_bucket == STAGING_BUCKET


def test_no_module_hardcodes_the_bucket() -> None:
    offenders = {
        str(path.relative_to(APP))
        for path in APP.rglob("*.py")
        if path.resolve() != CONFIG and PRODUCTION_BUCKET in path.read_text()
    }
    assert not offenders, (
        f"these modules pin the oral-collector's bucket in source: {sorted(offenders)}. "
        f"Read it from Settings instead, so the staging service writes into its own "
        f"bucket rather than into production's files."
    )


GCS_CLIENT = "app.services.oral_collector.gcs_utils.storage.Client"


class _FakeGcsBlob:
    """The calls the bucket's own helpers make on a blob."""

    def __init__(self, bucket_name: str, blob_name: str, uploads: list[tuple[str, str]]) -> None:
        self.bucket_name = bucket_name
        self.blob_name = blob_name
        self.content_encoding: str | None = None
        self._uploads = uploads

    def upload_from_string(self, data: bytes, content_type: str) -> None:
        self._uploads.append((self.bucket_name, self.blob_name))


class _FakeGcsBucket:
    def __init__(
        self,
        name: str,
        uploads: list[tuple[str, str]],
        copies: list[tuple[str, str, str, str]],
    ) -> None:
        self.name = name
        self._uploads = uploads
        self._copies = copies

    def blob(self, blob_name: str) -> _FakeGcsBlob:
        return _FakeGcsBlob(self.name, blob_name, self._uploads)

    def copy_blob(
        self, source_blob: _FakeGcsBlob, destination_bucket: _FakeGcsBucket, new_name: str
    ) -> None:
        self._copies.append((self.name, source_blob.blob_name, destination_bucket.name, new_name))


class _FakeGcsClient:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str]] = []
        self.copies: list[tuple[str, str, str, str]] = []

    def bucket(self, name: str) -> _FakeGcsBucket:
        return _FakeGcsBucket(name, self.uploads, self.copies)


def _point_the_bucket_at(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setattr(get_settings(), "gcs_oc_bucket", name)


def test_the_url_a_confirmed_upload_stores_carries_the_configured_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The prefix `process_upload_fn` writes on the row. No test drives that function today,
    so this pins the accessor the stored URL is built from."""
    _point_the_bucket_at(monkeypatch, STAGING_BUCKET)

    assert gcs_public_base() == f"https://storage.googleapis.com/{STAGING_BUCKET}/"


async def test_the_cleaning_backs_up_and_writes_back_in_the_configured_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A row staging inherited from production names production's bucket in its URL. The
    object name comes from the URL and the bucket from the setting, so the backup and the
    write-back both land in staging's bucket and production's file is never touched.

    The three calls are the cleaning's own, driven here one by one: the cleaning makes them
    inside a closure of an Inngest function, which no case in this suite drives.
    """
    _point_the_bucket_at(monkeypatch, STAGING_BUCKET)
    client = _FakeGcsClient()
    inherited = f"https://storage.googleapis.com/{PRODUCTION_BUCKET}/oral-collector/p/g/r.m4a"

    with patch(GCS_CLIENT, return_value=client):
        blob_name = blob_name_from_url(inherited)
        assert blob_name == "oral-collector/p/g/r.m4a"
        await copy_gcs_blob(blob_name, original_blob_name(blob_name))
        await upload_gcs_blob(blob_name, b"cleaned audio", "application/octet-stream")

    assert client.copies == [
        (
            STAGING_BUCKET,
            "oral-collector/p/g/r.m4a",
            STAGING_BUCKET,
            "oral-collector/p/g/r_original.m4a",
        )
    ]
    assert client.uploads == [(STAGING_BUCKET, "oral-collector/p/g/r.m4a")]


async def test_each_upload_lands_in_the_configured_bucket_and_its_url_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The upload the cutting makes per segment, and the URL the segment row is given.

    Driven directly, one call per segment: the cutting makes them inside a closure of an
    Inngest function, which no case in this suite drives.
    """
    _point_the_bucket_at(monkeypatch, STAGING_BUCKET)
    client = _FakeGcsClient()

    with patch(GCS_CLIENT, return_value=client):
        urls = [
            await upload_gcs_blob(f"oral-collector/p/g/seg-{index}.m4a", b"audio", "audio/mp4")
            for index in range(2)
        ]

    assert [bucket for bucket, _ in client.uploads] == [STAGING_BUCKET, STAGING_BUCKET]
    assert urls == [
        f"https://storage.googleapis.com/{STAGING_BUCKET}/oral-collector/p/g/seg-0.m4a",
        f"https://storage.googleapis.com/{STAGING_BUCKET}/oral-collector/p/g/seg-1.m4a",
    ]


async def test_the_acousteme_artifact_is_stored_in_the_configured_bucket(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The setting is pointed after the module was imported, so a bucket resolved at import
    time would still carry production's name here."""
    _point_the_bucket_at(monkeypatch, STAGING_BUCKET)
    uploaded: list[str] = []

    async def _record_the_bucket(
        bucket: str,
        blob_name: str,
        data: bytes,
        content_type: str,
        *,
        content_encoding: str | None = None,
    ) -> str:
        uploaded.append(bucket)
        return f"gs://{bucket}/{blob_name}"

    monkeypatch.setattr(acousteme_service, "upload_gcs_object", _record_the_bucket)

    await acousteme_service.store_artifact(
        db_session,
        audio_id="audio-1",
        codebook_version="v1",
        stream={
            "duration_sec": 1.0,
            "num_frames": 10,
            "segments": [{"start": 0.0, "end": 1.0, "unit_id": 3}],
        },
    )

    assert uploaded == [STAGING_BUCKET]


async def test_a_platform_image_answers_a_url_under_the_configured_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The platform's images and the oral-collector's audio are one bucket, so one setting."""
    _point_the_bucket_at(monkeypatch, STAGING_BUCKET)
    image = UploadFile(
        file=io.BytesIO(b"an image"),
        filename="icon.png",
        headers=Headers({"content-type": "image/png"}),
    )

    with patch("app.services.storage.upload.storage.Client", return_value=_FakeGcsClient()):
        url = await upload_image(image)

    assert url.startswith(f"https://storage.googleapis.com/{STAGING_BUCKET}/images/")
