from __future__ import annotations

from typing import Any

import pytest
from google.api_core.exceptions import Forbidden, NotFound

from app.core.config import Settings
from app.services.platform import storage
from app.services.platform.storage import GcsPlatformStore


class _Blob:
    def __init__(self, *, data: bytes = b"", error: Exception | None = None) -> None:
        self.data = data
        self.error = error
        self.asked: list[str] = []

    def exists(self) -> bool:
        self.asked.append("exists")
        return not isinstance(self.error, NotFound)

    def download_as_bytes(self) -> bytes:
        self.asked.append("download")
        if self.error is not None:
            raise self.error
        return self.data


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", gcs_platform_bucket="b")


def _the_bucket_holds(monkeypatch: pytest.MonkeyPatch, blob: _Blob) -> None:
    def _blob(key: str, settings: Any) -> _Blob:
        return blob

    monkeypatch.setattr(storage, "_blob", _blob)


async def test_a_clip_the_bucket_holds_comes_back_in_one_trip_not_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blob = _Blob(data=b"mp3")
    _the_bucket_holds(monkeypatch, blob)

    audio = await GcsPlatformStore(_settings()).get("tts/v/m/f/a.mp3")

    assert audio == b"mp3"
    assert blob.asked == ["download"], (
        "cada leitura de clipe perguntava ao GCS se o objeto existia e só depois o baixava: "
        "duas idas ao bucket por clipe entregue ao tablet"
    )


async def test_a_clip_the_bucket_does_not_hold_is_none_after_a_single_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blob = _Blob(error=NotFound("no such object"))
    _the_bucket_holds(monkeypatch, blob)

    audio = await GcsPlatformStore(_settings()).get("tts/v/m/f/a.mp3")

    assert audio is None
    assert blob.asked == ["download"]


async def test_a_bucket_that_refuses_the_read_is_an_error_not_a_missing_clip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _the_bucket_holds(monkeypatch, _Blob(error=Forbidden("no permission")))

    with pytest.raises(Forbidden):
        await GcsPlatformStore(_settings()).get("tts/v/m/f/a.mp3")
