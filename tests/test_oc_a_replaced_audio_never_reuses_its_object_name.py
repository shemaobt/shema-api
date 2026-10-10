"""A replacement goes to an object name the recording never used, and confirm-upload checks it.

The bucket is an in-memory fake that holds bytes by object name and answers what Cloud
Storage answers: size, md5 and crc32c of what it holds, `NotFound` on a missing delete. The
public URL is served through a fake edge that keeps the first bytes it served for a URL, the
way Google's cache keeps `public, max-age=3600` objects: that is the stale read the ticket
measured, and the reason a replacement needs a new name.

The Inngest jobs are run as written, each step executed inline; the assertions read the row
and the bucket, never the steps.
"""

import base64
import hashlib
import inspect
import json
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit

import google_crc32c
import httpx
import inngest
import pytest
from google.api_core.exceptions import Forbidden, NotFound
from google.cloud import storage
from httpx import ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CleaningStatus, OCNotificationEvent, UploadStatus
from app.db.models.notification import Notification
from app.db.models.oc_recording import OC_Recording
from app.services.notifications.get_oc_app_id import OC_APP_KEY
from app.services.oral_collector.gcs_utils import gcs_public_base
from tests.baker import (
    make_app,
    make_language,
    make_oc_recording,
    make_oc_taxonomy,
    make_project,
    make_user,
)
from tests.oral_collector_harness import PRODUCTION_BUCKET, STAGING_BUCKET

pytest.importorskip("app.inngest")

RECORDINGS_PREFIX = "/api/oral-collector/recordings"
CLEANING_API = "https://cleaner.example/clean"
CLEANED_OUTPUT = "https://cleaner.example/out"


def _md5_hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _crc32c(data: bytes) -> str:
    return base64.b64encode(google_crc32c.value(data).to_bytes(4, "big")).decode()


class _Bucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.refuses_deletes = False
        self.reports_no_crc32c = False


class _Blob:
    """Size and checksums are unknown until `reload`, as on a real `bucket.blob(name)`."""

    def __init__(self, bucket_name: str, store: _Bucket, name: str) -> None:
        self._bucket_name = bucket_name
        self._store = store
        self.name = name
        self._loaded: bytes | None = None

    def generate_signed_url(self, **_kwargs: object) -> str:
        return f"https://storage.googleapis.com/{self._bucket_name}/{self.name}?X-Goog-Signature=x"

    def create_resumable_upload_session(self, **_kwargs: object) -> str:
        return (
            f"https://storage.googleapis.com/upload/storage/v1/b/{self._bucket_name}"
            f"/o?uploadType=resumable&name={self.name}"
        )

    def exists(self) -> bool:
        return self.name in self._store.objects

    def reload(self) -> None:
        if not self.exists():
            raise NotFound(self.name)
        self._loaded = self._store.objects[self.name]

    @property
    def size(self) -> int | None:
        return None if self._loaded is None else len(self._loaded)

    @property
    def md5_hash(self) -> str | None:
        if self._loaded is None:
            return None
        return base64.b64encode(hashlib.md5(self._loaded).digest()).decode()

    @property
    def crc32c(self) -> str | None:
        if self._loaded is None or self._store.reports_no_crc32c:
            return None
        return _crc32c(self._loaded)

    def delete(self) -> None:
        if self._store.refuses_deletes:
            raise Forbidden(self.name)
        if self.name not in self._store.objects:
            raise NotFound(self.name)
        del self._store.objects[self.name]

    def upload_from_string(self, data: bytes, content_type: str | None = None) -> None:
        self._store.objects[self.name] = bytes(data)

    def download_as_bytes(self) -> bytes:
        if self.name not in self._store.objects:
            raise NotFound(self.name)
        return self._store.objects[self.name]


class _BucketHandle:
    def __init__(self, name: str, store: _Bucket) -> None:
        self.name = name
        self._store = store

    def blob(self, name: str) -> _Blob:
        return _Blob(self.name, self._store, name)

    def copy_blob(self, source: _Blob, destination: "_BucketHandle", new_name: str) -> None:
        if source.name not in self._store.objects:
            raise NotFound(source.name)
        destination._store.objects[new_name] = self._store.objects[source.name]


class _Client:
    """The configured bucket is the fixture's; any other bucket is a separate, empty one."""

    def __init__(self, store: _Bucket) -> None:
        self._stores = {STAGING_BUCKET: store}

    def bucket(self, name: str) -> _BucketHandle:
        return _BucketHandle(name, self._stores.setdefault(name, _Bucket()))


class _PublicEdge:
    """The public URL, cached the way Cloud Storage's default `max-age=3600` caches it."""

    def __init__(self, store: _Bucket) -> None:
        self._store = store
        self._cached: dict[str, bytes] = {}
        self.cleaned_audio = b""

    def handle(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == CLEANING_API:
            return httpx.Response(200, json={"output_url": CLEANED_OUTPUT})
        if url == CLEANED_OUTPUT:
            return httpx.Response(200, content=self.cleaned_audio)
        if url not in self._cached:
            bucket_name, _, name = urlsplit(url).path.lstrip("/").partition("/")
            if bucket_name != STAGING_BUCKET or name not in self._store.objects:
                return httpx.Response(404)
            self._cached[url] = self._store.objects[name]
        return httpx.Response(200, content=self._cached[url])

    async def play(self, url: str) -> bytes:
        return self.handle(httpx.Request("GET", url)).content


@pytest.fixture()
def bucket(monkeypatch: pytest.MonkeyPatch) -> _Bucket:
    from app.core.config import get_settings
    from app.services.oral_collector import recording_service

    store = _Bucket()
    client = _Client(store)
    monkeypatch.setattr(get_settings(), "gcs_oc_bucket", STAGING_BUCKET)
    monkeypatch.setattr(get_settings(), "cleaning_api_url", CLEANING_API)
    monkeypatch.setattr(recording_service, "_get_gcs_client", lambda: client)
    monkeypatch.setattr(recording_service, "_get_signing_info", lambda: ("signer@test", "token"))
    monkeypatch.setattr(storage, "Client", lambda **_kwargs: client)
    return store


@pytest.fixture()
def edge(bucket: _Bucket, monkeypatch: pytest.MonkeyPatch) -> _PublicEdge:
    public = _PublicEdge(bucket)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(**{"transport": httpx.MockTransport(public.handle), **kwargs}),
    )
    return public


@pytest.fixture()
def sent(monkeypatch: pytest.MonkeyPatch) -> list[inngest.Event]:
    from app.core.inngest_client import inngest_client

    events: list[inngest.Event] = []

    async def _send(event: inngest.Event) -> list[str]:
        events.append(event)
        return ["sent"]

    monkeypatch.setattr(inngest_client, "send", _send)
    return events


@pytest.fixture()
async def client(db_session: AsyncSession, bucket: _Bucket, sent: list[inngest.Event]):
    from fastapi import FastAPI

    from app.api.oral_collector.recordings import recordings_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(recordings_router, prefix=RECORDINGS_PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as c:
        yield c


class _RunsEachStepInline:
    """Each step's output crosses a JSON boundary, as Inngest memoizes it.

    `meanwhile` maps a step id to what the world does just before that step runs.
    """

    def __init__(self, meanwhile: dict[str, Any]) -> None:
        self._meanwhile = meanwhile

    async def run(self, step_id: str, handler: Any, *args: Any) -> Any:
        if step_id in self._meanwhile:
            await self._meanwhile[step_id]()
        result = handler(*args)
        if inspect.isawaitable(result):
            result = await result
        return json.loads(json.dumps(result))


async def _run_job(
    fn: inngest.Function, event: inngest.Event, meanwhile: dict[str, Any] | None = None
) -> Any:
    ctx = SimpleNamespace(event=SimpleNamespace(data=event.data))
    return await fn._handler(ctx, _RunsEachStepInline(meanwhile or {}))  # type: ignore[call-arg]


class _Device:
    """The app: asks for upload URLs, puts the bytes where they point, confirms."""

    def __init__(self, client: httpx.AsyncClient, bucket: _Bucket, headers: dict[str, str]):
        self._client = client
        self._bucket = bucket
        self.headers = headers

    async def upload_url(self, recording_id: str, fmt: str = "m4a") -> str:
        response = await self._client.post(
            f"{RECORDINGS_PREFIX}/upload-url",
            json={"recording_id": recording_id, "format": fmt},
            headers=self.headers,
        )
        assert response.status_code == 200, response.text
        return urlsplit(response.json()["upload_url"]).path.partition(f"/{STAGING_BUCKET}/")[2]

    async def resumable_upload_url(self, recording_id: str, fmt: str = "m4a") -> str:
        response = await self._client.post(
            f"{RECORDINGS_PREFIX}/resumable-upload-url",
            json={"recording_id": recording_id, "format": fmt},
            headers=self.headers,
        )
        assert response.status_code == 200, response.text
        return parse_qs(urlsplit(response.json()["session_uri"]).query)["name"][0]

    def put(self, object_name: str, data: bytes) -> None:
        self._bucket.objects[object_name] = data

    async def confirm(self, recording_id: str, **body: str) -> httpx.Response:
        return await self._client.post(
            f"{RECORDINGS_PREFIX}/{recording_id}/confirm-upload", json=body, headers=self.headers
        )

    async def replace(self, recording_id: str, data: bytes) -> httpx.Response:
        name = await self.upload_url(recording_id)
        self.put(name, data)
        return await self.confirm(recording_id, crc32c=_crc32c(data))


def _tone(seconds: float) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "tone.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"sine=duration={seconds}", str(out)],
            check=True,
        )
        return out.read_bytes()


def _seconds(wav: bytes) -> float:
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "audio.wav"
        audio.write_bytes(wav)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio],
            check=True,
            capture_output=True,
        )
        return float(probe.stdout)


OLD_AUDIO = b"old audio, the six seconds before the cut"
NEW_AUDIO = b"new audio, three seconds"


async def _owner_and_recording(
    db: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient, **recording: Any
) -> tuple[_Device, OC_Recording]:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db)
    lang = await make_language(db)
    project = await make_project(db, lang.id)
    genre, sub = await make_oc_taxonomy(db)
    rec = await make_oc_recording(db, project.id, genre.id, sub.id, user_id=user.id, **recording)
    access, _refresh = await issue_tokens(db, user)
    return _Device(client, bucket, {"Authorization": f"Bearer {access}"}), rec


def _todays_name(rec: OC_Recording, ext: str = ".m4a") -> str:
    return f"oral-collector/{rec.project_id}/{rec.genre_id}/{rec.id}{ext}"


def _url(object_name: str) -> str:
    return f"{gcs_public_base()}{object_name}"


async def _uploaded(
    db: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient, data: bytes = OLD_AUDIO, **kw: Any
) -> tuple[_Device, OC_Recording]:
    """A recording whose audio the server already holds, at today's object name."""
    device, rec = await _owner_and_recording(
        db, bucket, client, file_size_bytes=len(data), upload_status=UploadStatus.VERIFIED, **kw
    )
    name = _todays_name(rec, f".{rec.format}")
    bucket.objects[name] = data
    rec.gcs_url = _url(name)
    await db.commit()
    return device, rec


async def _first_upload(
    db: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient, data: bytes = NEW_AUDIO
) -> tuple[_Device, OC_Recording]:
    return await _owner_and_recording(
        db, bucket, client, file_size_bytes=len(data), upload_status=UploadStatus.LOCAL
    )


async def _row(db: AsyncSession, recording_id: str) -> OC_Recording:
    db.expire_all()
    found = await db.get(OC_Recording, recording_id)
    assert found is not None
    return found


async def test_a_first_upload_is_handed_todays_object_name_and_confirm_upload_publishes_it(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _first_upload(db_session, bucket, client)

    name = await device.upload_url(rec.id)
    device.put(name, NEW_AUDIO)
    response = await device.confirm(rec.id, crc32c=_crc32c(NEW_AUDIO))

    assert name == _todays_name(rec)
    assert response.status_code == 200
    assert response.json()["gcs_url"] == _url(_todays_name(rec))


async def test_a_replacement_through_upload_url_goes_to_a_name_the_recording_never_used(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)
    earlier = [_todays_name(rec)]
    for take in (b"second take", b"third take"):
        rec.file_size_bytes = len(take)
        await db_session.commit()
        response = await device.replace(rec.id, take)
        earlier.append(response.json()["gcs_url"].removeprefix(gcs_public_base()))
    rec.file_size_bytes = len(NEW_AUDIO)
    await db_session.commit()

    name = await device.upload_url(rec.id)
    device.put(name, NEW_AUDIO)
    response = await device.confirm(rec.id, crc32c=_crc32c(NEW_AUDIO))

    assert name not in earlier
    assert response.status_code == 200
    assert response.json()["gcs_url"] == _url(name)


async def test_a_replacement_through_resumable_upload_url_goes_to_a_name_the_recording_never_used(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)
    earlier = [_todays_name(rec)]
    rec.file_size_bytes = len(b"second take")
    await db_session.commit()
    earlier.append(
        (await device.replace(rec.id, b"second take"))
        .json()["gcs_url"]
        .removeprefix(gcs_public_base())
    )
    rec.file_size_bytes = len(NEW_AUDIO)
    await db_session.commit()

    name = await device.resumable_upload_url(rec.id)
    device.put(name, NEW_AUDIO)
    response = await device.confirm(rec.id, crc32c=_crc32c(NEW_AUDIO))

    assert name not in earlier
    assert response.status_code == 200
    assert response.json()["gcs_url"] == _url(name)


async def test_an_upload_url_asked_twice_before_confirm_upload_names_the_same_pending_object(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client, data=NEW_AUDIO)

    first = await device.upload_url(rec.id)
    second = await device.upload_url(rec.id)
    device.put(second, NEW_AUDIO)
    response = await device.confirm(rec.id, crc32c=_crc32c(NEW_AUDIO))

    assert first == second != _todays_name(rec)
    assert response.json()["gcs_url"] == _url(first)


async def test_an_upload_url_asked_in_another_format_before_confirm_upload_gets_a_fresh_name(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client, data=NEW_AUDIO)

    as_m4a = await device.upload_url(rec.id, "m4a")
    as_wav = await device.upload_url(rec.id, "wav")
    device.put(as_wav, NEW_AUDIO)
    response = await device.confirm(rec.id, crc32c=_crc32c(NEW_AUDIO))

    assert as_wav != as_m4a
    assert as_wav.endswith(".wav")
    assert response.json()["gcs_url"] == _url(as_wav)


async def test_a_pending_object_superseded_by_another_format_is_removed_from_the_bucket(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client, data=NEW_AUDIO)
    as_m4a = await device.upload_url(rec.id, "m4a")
    device.put(as_m4a, NEW_AUDIO)

    as_wav = await device.upload_url(rec.id, "wav")

    assert as_m4a not in bucket.objects
    assert set(bucket.objects) == {_todays_name(rec)}
    assert as_wav not in bucket.objects


async def test_confirm_upload_of_the_declared_size_and_crc32c_answers_the_new_url_already_uploaded(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client, data=NEW_AUDIO)
    name = await device.upload_url(rec.id)
    device.put(name, NEW_AUDIO)

    response = await device.confirm(rec.id, crc32c=_crc32c(NEW_AUDIO))

    assert response.status_code == 200
    assert response.json()["gcs_url"] == _url(name)
    assert response.json()["upload_status"] == UploadStatus.UPLOADED
    stored = await _row(db_session, rec.id)
    assert (stored.gcs_url, stored.upload_status) == (_url(name), UploadStatus.UPLOADED)


async def _assert_refused_and_untouched(
    db: AsyncSession,
    bucket: _Bucket,
    rec_id: str,
    response: httpx.Response,
    old_name: str,
    pending: str,
    reason: str,
) -> None:
    assert (response.status_code, response.json()["code"]) == (400, reason)
    stored = await _row(db, rec_id)
    assert stored.gcs_url == _url(old_name)
    assert bucket.objects[old_name] == OLD_AUDIO
    assert stored.upload_status == UploadStatus.VERIFIED
    assert (stored.upload_error, stored.pending_blob_name) == (None, pending)


async def test_confirm_upload_with_no_object_is_refused_and_the_recording_keeps_its_audio(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)
    name = await device.upload_url(rec.id)

    response = await device.confirm(rec.id)

    await _assert_refused_and_untouched(
        db_session, bucket, rec.id, response, _todays_name(rec), name, "UPLOAD_OBJECT_MISSING"
    )


async def test_confirm_upload_with_an_object_of_the_wrong_size_is_refused_and_the_audio_kept(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)
    name = await device.upload_url(rec.id)
    device.put(name, OLD_AUDIO + b" and a truncated tail")

    response = await device.confirm(rec.id)

    await _assert_refused_and_untouched(
        db_session, bucket, rec.id, response, _todays_name(rec), name, "UPLOAD_SIZE_MISMATCH"
    )


async def test_confirm_upload_with_a_crc32c_that_does_not_match_is_refused_and_the_audio_kept(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)
    name = await device.upload_url(rec.id)
    device.put(name, bytes(len(OLD_AUDIO)))

    response = await device.confirm(rec.id, crc32c=_crc32c(OLD_AUDIO))

    await _assert_refused_and_untouched(
        db_session, bucket, rec.id, response, _todays_name(rec), name, "UPLOAD_CHECKSUM_MISMATCH"
    )


async def test_confirm_upload_with_a_crc32c_the_bucket_cannot_report_is_refused_and_the_audio_kept(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)
    name = await device.upload_url(rec.id)
    device.put(name, bytes(len(OLD_AUDIO)))
    bucket.reports_no_crc32c = True

    response = await device.confirm(rec.id, crc32c=_crc32c(bytes(len(OLD_AUDIO))))

    await _assert_refused_and_untouched(
        db_session, bucket, rec.id, response, _todays_name(rec), name, "UPLOAD_CHECKSUM_MISMATCH"
    )


async def test_a_refused_first_upload_answers_its_reason_publishes_nothing_and_stays_uploading(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _first_upload(db_session, bucket, client)
    device.put(await device.upload_url(rec.id), NEW_AUDIO[:5])

    response = await device.confirm(rec.id)

    assert (response.status_code, response.json()["code"]) == (400, "UPLOAD_SIZE_MISMATCH")
    stored = await _row(db_session, rec.id)
    assert (stored.gcs_url, stored.upload_status) == (None, UploadStatus.UPLOADING)


async def test_a_recording_with_published_audio_keeps_its_status_when_it_asks_an_upload_url(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)

    await device.upload_url(rec.id)

    assert (await _row(db_session, rec.id)).upload_status == UploadStatus.VERIFIED


async def test_a_recording_with_published_audio_keeps_its_status_when_it_asks_a_resumable_session(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)

    await device.resumable_upload_url(rec.id)

    assert (await _row(db_session, rec.id)).upload_status == UploadStatus.VERIFIED


async def test_a_first_uploads_upload_url_puts_the_recording_in_uploading(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _first_upload(db_session, bucket, client)

    await device.upload_url(rec.id)

    assert (await _row(db_session, rec.id)).upload_status == UploadStatus.UPLOADING


async def _untouched_for(db: AsyncSession, recording_id: str, age: timedelta) -> None:
    await db.execute(
        text("UPDATE oc_recordings SET updated_at = :when WHERE id = :rid"),
        {"when": datetime.now(UTC) - age - timedelta(days=1), "rid": recording_id},
    )
    await db.commit()


async def test_a_replacement_never_confirmed_is_left_alone_by_the_stalled_upload_sweep(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    from app.services.oral_collector import recording_service

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    device, rec = await _uploaded(db_session, bucket, client)
    device.put(await device.upload_url(rec.id), NEW_AUDIO)
    await _untouched_for(db_session, rec.id, recording_service.STALLED_UPLOAD_DEADLINE)

    await recording_service.fail_stalled_uploads(db_session)

    assert (await _row(db_session, rec.id)).upload_status == UploadStatus.VERIFIED


async def test_a_replacement_never_confirmed_is_never_listed_by_the_purge(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    from app.services.oral_collector import recording_service

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    device, rec = await _uploaded(db_session, bucket, client)
    device.put(await device.upload_url(rec.id), NEW_AUDIO)
    await _untouched_for(db_session, rec.id, recording_service.FAILED_UPLOAD_RETENTION)
    await recording_service.fail_stalled_uploads(db_session)
    await _untouched_for(db_session, rec.id, recording_service.FAILED_UPLOAD_RETENTION)

    assert await recording_service.purge_failed_uploads(db_session) == 0
    assert (await _row(db_session, rec.id)).gcs_url == _url(_todays_name(rec))
    assert bucket.objects[_todays_name(rec)] == OLD_AUDIO


async def test_a_pending_object_naming_the_published_audio_is_never_handed_out(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)
    rec.pending_blob_name = _todays_name(rec)
    await db_session.commit()

    name = await device.upload_url(rec.id)

    assert name != _todays_name(rec)


async def test_confirm_upload_with_an_md5_that_does_not_match_is_refused_and_the_audio_kept(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)
    name = await device.upload_url(rec.id)
    device.put(name, bytes(len(OLD_AUDIO)))

    response = await device.confirm(rec.id, md5_hash=_md5_hex(OLD_AUDIO))

    await _assert_refused_and_untouched(
        db_session, bucket, rec.id, response, _todays_name(rec), name, "UPLOAD_CHECKSUM_MISMATCH"
    )


async def test_confirm_upload_with_the_md5_the_app_computed_publishes_the_object(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _first_upload(db_session, bucket, client)
    name = await device.upload_url(rec.id)
    device.put(name, NEW_AUDIO)

    response = await device.confirm(rec.id, md5_hash=_md5_hex(NEW_AUDIO).upper())

    assert response.status_code == 200
    assert response.json()["gcs_url"] == _url(name)


async def test_confirm_upload_with_no_checksum_sent_publishes_the_object_of_the_declared_size(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _first_upload(db_session, bucket, client)
    name = await device.upload_url(rec.id)
    device.put(name, NEW_AUDIO)

    response = await device.confirm(rec.id)

    assert response.status_code == 200
    assert response.json()["gcs_url"] == _url(name)


async def test_confirm_upload_of_a_recording_with_no_declared_size_checks_only_that_it_exists(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _first_upload(db_session, bucket, client)
    rec.file_size_bytes = 0
    await db_session.commit()
    name = await device.upload_url(rec.id)
    device.put(name, NEW_AUDIO + b" of a length nobody declared")

    response = await device.confirm(rec.id)

    assert response.status_code == 200
    assert response.json()["gcs_url"] == _url(name)


async def test_after_a_confirmed_replacement_the_previous_object_is_gone_from_the_bucket(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client, data=NEW_AUDIO)

    response = await device.replace(rec.id, NEW_AUDIO)

    assert response.status_code == 200
    assert _todays_name(rec) not in bucket.objects
    assert list(bucket.objects) == [response.json()["gcs_url"].removeprefix(gcs_public_base())]


async def test_a_replacement_whose_previous_object_does_not_exist_still_confirms(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client, data=NEW_AUDIO)
    inherited = f"oral-collector/{rec.project_id}/{rec.genre_id}/{rec.id}-from-production.m4a"
    del bucket.objects[_todays_name(rec)]
    rec.gcs_url = f"https://storage.googleapis.com/{PRODUCTION_BUCKET}/{inherited}"
    await db_session.commit()

    name = await device.upload_url(rec.id)
    device.put(name, NEW_AUDIO)
    response = await device.confirm(rec.id, crc32c=_crc32c(NEW_AUDIO))

    assert response.status_code == 200
    assert response.json()["gcs_url"] == _url(name)


async def test_a_previous_object_the_bucket_refuses_to_delete_does_not_fail_the_confirm(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client, data=NEW_AUDIO)
    bucket.refuses_deletes = True

    name = await device.upload_url(rec.id)
    device.put(name, NEW_AUDIO)
    response = await device.confirm(rec.id, crc32c=_crc32c(NEW_AUDIO))

    assert response.status_code == 200
    assert response.json()["gcs_url"] == _url(name)
    assert (await _row(db_session, rec.id)).upload_status == UploadStatus.UPLOADED


async def test_an_upload_started_before_this_deploy_confirms_against_todays_object_name(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _owner_and_recording(
        db_session,
        bucket,
        client,
        file_size_bytes=len(NEW_AUDIO),
        upload_status=UploadStatus.UPLOADING,
    )
    device.put(_todays_name(rec), NEW_AUDIO)

    response = await device.confirm(rec.id, crc32c=_crc32c(NEW_AUDIO))

    assert response.status_code == 200
    assert response.json()["gcs_url"] == _url(_todays_name(rec))


async def test_a_repeated_confirm_upload_of_a_replaced_recording_answers_200_and_keeps_it_uploaded(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client, data=NEW_AUDIO)
    confirmed = await device.replace(rec.id, NEW_AUDIO)

    again = await device.confirm(rec.id, crc32c=_crc32c(NEW_AUDIO))

    assert again.status_code == 200
    assert again.json()["gcs_url"] == confirmed.json()["gcs_url"]
    assert again.json()["upload_status"] == UploadStatus.UPLOADED


async def test_a_repeated_confirm_on_a_cleaned_recording_answers_200_and_keeps_the_cleaned_audio(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient, edge: _PublicEdge
) -> None:
    from app.inngest.audio_cleaning import clean_recording_fn

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    device, rec = await _uploaded(db_session, bucket, client)
    edge.cleaned_audio = b"the same story without the hiss"
    await _run_job(
        clean_recording_fn,
        inngest.Event(
            name="clean",
            data={
                "recording_id": rec.id,
                "user_id": rec.user_id,
                "gcs_url": _url(_todays_name(rec)),
            },
        ),
    )
    cleaned_url = (await _row(db_session, rec.id)).gcs_url

    response = await device.confirm(rec.id, crc32c=_crc32c(OLD_AUDIO))

    assert response.status_code == 200, response.text
    assert response.json()["gcs_url"] == cleaned_url
    stored = await _row(db_session, rec.id)
    assert (stored.gcs_url, stored.cleaning_status) == (cleaned_url, CleaningStatus.CLEANED)
    assert bucket.objects[(cleaned_url or "").removeprefix(gcs_public_base())] == edge.cleaned_audio


async def test_a_repeated_confirm_on_a_verified_recording_keeps_it_verified(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient, sent: list
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)

    response = await device.confirm(rec.id, crc32c=_crc32c(OLD_AUDIO))

    assert (response.status_code, response.json()["upload_status"]) == (200, "verified")
    assert (await _row(db_session, rec.id)).upload_status == UploadStatus.VERIFIED
    assert sent == []


async def test_a_replacement_started_before_this_deploy_is_still_checked_by_confirm_upload(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)
    rec.upload_status = UploadStatus.UPLOADING
    await db_session.commit()
    device.put(_todays_name(rec), OLD_AUDIO[:5])

    response = await device.confirm(rec.id)

    assert (response.status_code, response.json()["code"]) == (400, "UPLOAD_SIZE_MISMATCH")


async def test_a_confirm_whose_event_was_lost_is_sent_again_by_the_retried_confirm_and_verified(
    db_session: AsyncSession,
    bucket: _Bucket,
    client: httpx.AsyncClient,
    sent: list,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.inngest_client import inngest_client
    from app.inngest.upload_processing import process_upload_fn

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    device, rec = await _first_upload(db_session, bucket, client)
    device.put(await device.upload_url(rec.id), NEW_AUDIO)
    reachable = inngest_client.send

    async def _unreachable_once(event: inngest.Event) -> list[str]:
        monkeypatch.setattr(inngest_client, "send", reachable)
        raise ConnectionError("Inngest unreachable")

    monkeypatch.setattr(inngest_client, "send", _unreachable_once)
    with pytest.raises(ConnectionError):
        await device.confirm(rec.id, crc32c=_crc32c(NEW_AUDIO))

    retried = await device.confirm(rec.id, crc32c=_crc32c(NEW_AUDIO))
    assert retried.status_code == 200
    assert len(sent) == 1
    await _run_job(process_upload_fn, sent[-1])

    assert (await _row(db_session, rec.id)).upload_status == UploadStatus.VERIFIED


async def test_an_uploaded_recording_whose_object_is_missing_is_not_marked_verified_by_the_job(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    from app.inngest.upload_processing import process_upload_fn

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    _device, rec = await _owner_and_recording(
        db_session,
        bucket,
        client,
        file_size_bytes=len(NEW_AUDIO),
        upload_status=UploadStatus.UPLOADED,
    )
    rec.gcs_url = _url(_todays_name(rec))
    await db_session.commit()

    await _run_job(process_upload_fn, _queued_by_the_old_confirm(rec, NEW_AUDIO))

    assert (await _row(db_session, rec.id)).upload_status == UploadStatus.UPLOADED
    told = await db_session.execute(
        select(Notification.event_type).where(Notification.user_id == rec.user_id)
    )
    assert list(told.scalars()) == [OCNotificationEvent.UPLOAD_FAILED]


async def test_a_failed_upload_with_a_url_asking_an_upload_url_goes_to_uploading_on_a_fresh_name(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)
    rec.upload_status = UploadStatus.UPLOAD_FAILED
    await db_session.commit()

    name = await device.upload_url(rec.id)

    assert name != _todays_name(rec)
    assert (await _row(db_session, rec.id)).upload_status == UploadStatus.UPLOADING


async def test_after_confirm_upload_the_job_marks_it_verified_and_notifies_keeping_its_url(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient, sent: list
) -> None:
    from app.inngest.upload_processing import process_upload_fn

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    device, rec = await _first_upload(db_session, bucket, client)
    confirmed = await device.replace(rec.id, NEW_AUDIO)

    await _run_job(process_upload_fn, sent[-1])

    stored = await _row(db_session, rec.id)
    assert stored.upload_status == UploadStatus.VERIFIED
    assert stored.gcs_url == confirmed.json()["gcs_url"]
    told = await db_session.execute(
        select(Notification.event_type).where(Notification.user_id == rec.user_id)
    )
    assert list(told.scalars()) == [OCNotificationEvent.UPLOAD_VERIFIED]


def _queued_by_the_old_confirm(rec: OC_Recording, data: bytes) -> inngest.Event:
    return inngest.Event(
        name="oc/recording.upload-confirmed",
        data={
            "recording_id": rec.id,
            "user_id": rec.user_id,
            "expected_blob_path": _todays_name(rec),
            "expected_size_bytes": len(data),
            "expected_md5_hash": None,
            "expected_crc32c": _crc32c(data),
        },
    )


async def _verified_notices(db: AsyncSession, user_id: str | None) -> list[str]:
    told = await db.execute(
        select(Notification.event_type).where(
            Notification.user_id == user_id,
            Notification.event_type == OCNotificationEvent.UPLOAD_VERIFIED,
        )
    )
    return list(told.scalars())


async def test_a_confirm_queued_before_this_deploy_is_checked_and_published_by_the_job(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    from app.inngest.upload_processing import process_upload_fn

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    _device, rec = await _owner_and_recording(
        db_session,
        bucket,
        client,
        file_size_bytes=len(NEW_AUDIO),
        upload_status=UploadStatus.UPLOADING,
    )
    bucket.objects[_todays_name(rec)] = NEW_AUDIO

    await _run_job(process_upload_fn, _queued_by_the_old_confirm(rec, NEW_AUDIO))

    stored = await _row(db_session, rec.id)
    assert (stored.gcs_url, stored.upload_status) == (
        _url(_todays_name(rec)),
        UploadStatus.VERIFIED,
    )
    assert await _verified_notices(db_session, rec.user_id) == [OCNotificationEvent.UPLOAD_VERIFIED]


async def test_a_refused_confirm_queued_before_this_deploy_keeps_its_status_and_the_phone_its_audio(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    from app.inngest.upload_processing import process_upload_fn

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    _device, rec = await _owner_and_recording(
        db_session,
        bucket,
        client,
        file_size_bytes=len(NEW_AUDIO),
        upload_status=UploadStatus.UPLOADING,
    )
    bucket.objects[_todays_name(rec)] = NEW_AUDIO[:5]

    await _run_job(process_upload_fn, _queued_by_the_old_confirm(rec, NEW_AUDIO))

    stored = await _row(db_session, rec.id)
    assert (stored.gcs_url, stored.upload_status) == (None, UploadStatus.UPLOADING)
    told = await db_session.execute(
        select(Notification.event_type).where(Notification.user_id == rec.user_id)
    )
    assert list(told.scalars()) == [OCNotificationEvent.UPLOAD_FAILED]


async def test_a_cleaning_that_finishes_after_a_replacement_leaves_the_new_audio_in_place(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient, edge: _PublicEdge
) -> None:
    from app.inngest.audio_cleaning import clean_recording_fn

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    device, rec = await _uploaded(db_session, bucket, client)
    rec.file_size_bytes = len(NEW_AUDIO)
    await db_session.commit()
    edge.cleaned_audio = b"the old story without the hiss"
    replaced: list[str] = []

    async def _a_replacement_is_confirmed() -> None:
        replaced.append((await device.replace(rec.id, NEW_AUDIO)).json()["gcs_url"])

    await _run_job(
        clean_recording_fn,
        inngest.Event(
            name="clean",
            data={
                "recording_id": rec.id,
                "user_id": rec.user_id,
                "gcs_url": _url(_todays_name(rec)),
            },
        ),
        meanwhile={"repoint-to-cleaned-audio": _a_replacement_is_confirmed},
    )

    stored = await _row(db_session, rec.id)
    new_name = replaced[0].removeprefix(gcs_public_base())
    assert stored.gcs_url == replaced[0]
    assert stored.cleaning_status == CleaningStatus.NONE
    assert bucket.objects[new_name] == NEW_AUDIO
    assert edge.cleaned_audio not in bucket.objects.values()


async def test_the_cleaning_job_writes_under_a_new_name_keeps_the_backup_and_removes_the_previous(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient, edge: _PublicEdge
) -> None:
    from app.inngest.audio_cleaning import clean_recording_fn

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    _device, rec = await _uploaded(db_session, bucket, client)
    previous = _todays_name(rec)
    edge.cleaned_audio = b"the same story without the hiss"

    await _run_job(
        clean_recording_fn,
        inngest.Event(
            name="clean",
            data={"recording_id": rec.id, "user_id": rec.user_id, "gcs_url": _url(previous)},
        ),
    )

    stored = await _row(db_session, rec.id)
    cleaned_name = (stored.gcs_url or "").removeprefix(gcs_public_base())
    assert cleaned_name != previous
    assert bucket.objects[cleaned_name] == edge.cleaned_audio
    assert bucket.objects[previous.removesuffix(".m4a") + "_original.m4a"] == OLD_AUDIO
    assert previous not in bucket.objects
    assert stored.cleaning_status == CleaningStatus.CLEANED


async def test_a_cleaning_of_a_recording_deleted_meanwhile_is_not_retried(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient, edge: _PublicEdge
) -> None:
    from app.inngest.audio_cleaning import clean_recording_fn

    _device, rec = await _uploaded(db_session, bucket, client)
    edge.cleaned_audio = b"the same story without the hiss"

    async def _deleted() -> None:
        await db_session.delete(await _row(db_session, rec.id))
        await db_session.commit()

    with pytest.raises(inngest.NonRetriableError):
        await _run_job(
            clean_recording_fn,
            inngest.Event(
                name="clean",
                data={
                    "recording_id": rec.id,
                    "user_id": rec.user_id,
                    "gcs_url": _url(_todays_name(rec)),
                },
            ),
            meanwhile={"choose-cleaned-name": _deleted},
        )


async def test_a_previous_object_the_bucket_refuses_to_delete_does_not_fail_the_cleaning(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient, edge: _PublicEdge
) -> None:
    from app.inngest.audio_cleaning import clean_recording_fn

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    _device, rec = await _uploaded(db_session, bucket, client)
    bucket.refuses_deletes = True
    edge.cleaned_audio = b"the same story without the hiss"

    await _run_job(
        clean_recording_fn,
        inngest.Event(
            name="clean",
            data={
                "recording_id": rec.id,
                "user_id": rec.user_id,
                "gcs_url": _url(_todays_name(rec)),
            },
        ),
    )

    stored = await _row(db_session, rec.id)
    assert stored.cleaning_status == CleaningStatus.CLEANED
    assert bucket.objects[(stored.gcs_url or "").removeprefix(gcs_public_base())] == (
        edge.cleaned_audio
    )


async def test_the_split_job_of_a_replaced_recording_reads_the_new_audio(
    db_session: AsyncSession,
    bucket: _Bucket,
    client: httpx.AsyncClient,
    edge: _PublicEdge,
    sent: list,
) -> None:
    from app.inngest.audio_splitting import split_recording_fn
    from app.inngest.upload_processing import process_upload_fn
    from app.models.oc_recording import SplitSegment
    from app.services.oral_collector import split_service

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    old, new = _tone(4), _tone(2)
    device, rec = await _uploaded(db_session, bucket, client, data=old, format="wav")
    await edge.play(rec.gcs_url or "")
    rec.file_size_bytes = len(new)
    await db_session.commit()
    name = await device.upload_url(rec.id, "wav")
    device.put(name, new)
    assert (await device.confirm(rec.id, crc32c=_crc32c(new))).status_code == 200
    await _run_job(process_upload_fn, sent[-1])
    recording_id, owner = rec.id, rec.user_id or ""
    db_session.expire_all()

    await split_service.request_split(
        db_session,
        recording_id,
        [SplitSegment(start_seconds=0, end_seconds=4)],
        owner,
    )
    await _run_job(split_recording_fn, sent[-1])

    segments = await db_session.execute(
        select(OC_Recording).where(OC_Recording.split_from_id == recording_id)
    )
    (segment,) = segments.scalars()
    segment_name = (segment.gcs_url or "").removeprefix(gcs_public_base())
    assert _seconds(bucket.objects[segment_name]) == pytest.approx(2, abs=0.1)


async def test_deleting_a_recording_with_a_pending_object_removes_the_pending_object_too(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _first_upload(db_session, bucket, client)
    device.put(await device.upload_url(rec.id), NEW_AUDIO)

    response = await client.delete(f"{RECORDINGS_PREFIX}/{rec.id}", headers=device.headers)

    assert response.status_code == 204
    assert bucket.objects == {}


async def test_deleting_a_recording_with_a_pending_replacement_removes_it_and_the_published_audio(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    device, rec = await _uploaded(db_session, bucket, client)
    device.put(await device.upload_url(rec.id), NEW_AUDIO)

    response = await client.delete(f"{RECORDINGS_PREFIX}/{rec.id}", headers=device.headers)

    assert response.status_code == 204
    assert bucket.objects == {}


async def test_purging_failed_uploads_removes_a_pending_object(
    db_session: AsyncSession, bucket: _Bucket, client: httpx.AsyncClient
) -> None:
    from app.services.oral_collector import recording_service

    await make_app(db_session, app_key=OC_APP_KEY, name="Oral Collector")
    device, rec = await _first_upload(db_session, bucket, client)
    device.put(await device.upload_url(rec.id), NEW_AUDIO)
    await _untouched_for(db_session, rec.id, recording_service.STALLED_UPLOAD_DEADLINE)
    await recording_service.fail_stalled_uploads(db_session)
    await _untouched_for(db_session, rec.id, recording_service.FAILED_UPLOAD_RETENTION)

    assert await recording_service.purge_failed_uploads(db_session) == 1
    assert bucket.objects == {}
