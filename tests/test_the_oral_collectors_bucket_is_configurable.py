"""The oral-collector's bucket as a setting: the setting itself, and the paths that read it.

The bucket holding the oral-collector's audio — and the images the console uploads, the
same bucket today — was a literal written twice, so a service built from this image could
not be pointed anywhere: it addressed production by construction. Staging's database is a
branch of production's, so its rows carry production's ids and its object keys; writing,
cleaning or deleting a recording on staging reached production's own file.

The cases here are the setting (its default, the environment variable, and that no module
under `app/` names the bucket but `config.py`), the two deploys that decide what each
service runs with, and the paths with no test module of their own: the prefix a confirmed
upload stores, the copy and the upload the cleaning and the cutting make, the acousteme
artefact and the console's images. The signed uploads, the deletion and the reader live
with the recording service's cases, and the verification with the upload processing's.
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


def _deploy_env_vars(workflow: str) -> dict[str, str]:
    """The plain variables a deploy workflow tells its Cloud Run service to run with.

    They travel in one token of the `gcloud run deploy` command. Its separator is a comma
    unless the value opens with `^SEP^`, which is gcloud's own way of naming another one —
    a workflow whose `CORS_ORIGINS` is itself a comma-separated list has to. Both forms are
    read here rather than one being assumed, because the two deploys do not have to agree
    and a wrong guess would read the whole line as a single variable and quietly pass.
    Reading the token rather than the whole command is what makes this a statement about
    the service's environment and not about a string appearing somewhere in a shell script.
    """
    import yaml

    path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / workflow
    steps = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]["deploy"]["steps"]
    deploy_step = next(step for step in steps if step["name"] == "Deploy Backend")
    token = next(
        word for word in deploy_step["run"].split() if word.startswith("--update-env-vars=")
    )
    body = token.split("=", 1)[1].strip('"')
    if body.startswith("^"):
        separator, _, body = body[1:].partition("^")
    else:
        separator = ","
    return dict(pair.split("=", 1) for pair in body.split(separator))


def test_the_staging_deploy_names_its_own_bucket() -> None:
    """Nothing else points the staging service anywhere: this line is the whole mechanism."""
    staging = _deploy_env_vars("deploy-staging.yml")

    assert staging.get("GCS_OC_BUCKET") == "tripod-image-uploads-staging"


def test_the_production_deploy_names_no_bucket_and_so_runs_the_default() -> None:
    """Production keeps deploying what it always deployed, and by the shortest route.

    Naming it there would be a second place to keep in step with the default, and a wrong
    value in either would repoint production in silence.
    """
    assert "GCS_OC_BUCKET" not in _deploy_env_vars("deploy.yml")


def test_the_url_a_confirmed_upload_stores_carries_the_configured_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The prefix `process_upload_fn` writes on the row. No test drives that function today,
    so this pins the accessor the stored URL is built from."""
    _point_the_bucket_at(monkeypatch, STAGING_BUCKET)

    assert gcs_public_base() == f"https://storage.googleapis.com/{STAGING_BUCKET}/"


async def test_copy_gcs_blob_acts_in_the_configured_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The backup the cleaning takes before it writes over the original.

    The URL is one staging inherited from production, so it names production's bucket. The
    object name is the URL's and the bucket is the setting's: source and destination are
    both staging's, and production's file is never touched. `clean_recording_fn` makes this
    call inside a closure of an Inngest function, which no case in this suite drives, so it
    is driven here directly.
    """
    _point_the_bucket_at(monkeypatch, STAGING_BUCKET)
    client = _FakeGcsClient()
    inherited = f"https://storage.googleapis.com/{PRODUCTION_BUCKET}/oral-collector/p/g/r.m4a"

    with patch(GCS_CLIENT, return_value=client):
        blob_name = blob_name_from_url(inherited)
        assert blob_name == "oral-collector/p/g/r.m4a"
        await copy_gcs_blob(blob_name, original_blob_name(blob_name))

    assert client.copies == [
        (
            STAGING_BUCKET,
            "oral-collector/p/g/r.m4a",
            STAGING_BUCKET,
            "oral-collector/p/g/r_original.m4a",
        )
    ]


async def test_upload_gcs_blob_acts_in_the_configured_bucket_and_says_so_in_its_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The write-back the cleaning makes, and the upload the cutting makes per segment.

    The URL it answers with is the one the row is given, so the bucket reaches the database
    through it. Both `clean_recording_fn` and `split_recording_fn` make this call inside a
    closure of an Inngest function, which no case in this suite drives, so it is driven
    here directly.
    """
    _point_the_bucket_at(monkeypatch, STAGING_BUCKET)
    client = _FakeGcsClient()

    with patch(GCS_CLIENT, return_value=client):
        url = await upload_gcs_blob("oral-collector/p/g/seg-0.m4a", b"audio", "audio/mp4")

    assert client.uploads == [(STAGING_BUCKET, "oral-collector/p/g/seg-0.m4a")]
    assert url == f"https://storage.googleapis.com/{STAGING_BUCKET}/oral-collector/p/g/seg-0.m4a"


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
