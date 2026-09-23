from __future__ import annotations

from typing import Any

import pytest
from google.api_core.exceptions import PreconditionFailed

from app.core.config import Settings
from app.services.platform import storage
from app.services.platform.storage import GcsPlatformStore


class _Blob:
    def __init__(self, data: bytes | None = None) -> None:
        self.data = data

    def upload_from_string(
        self, data: bytes, content_type: str, if_generation_match: int | None = None
    ) -> None:
        if if_generation_match == 0 and self.data is not None:
            raise PreconditionFailed("the object already exists")
        self.data = data

    def download_as_bytes(self) -> bytes:
        assert self.data is not None
        return self.data


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", gcs_platform_bucket="b")


def _the_bucket_holds(monkeypatch: pytest.MonkeyPatch, blob: _Blob) -> None:
    def _blob(key: str, settings: Any) -> _Blob:
        return blob

    monkeypatch.setattr(storage, "_blob", _blob)


async def test_a_clip_written_first_is_kept_and_the_second_writer_gets_its_bytes_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blob = _Blob(data=b"first rendering")
    _the_bucket_holds(monkeypatch, blob)

    kept = await GcsPlatformStore(_settings()).put_once(
        "tts/v/m/f/a.mp3", b"second rendering", "audio/mpeg"
    )

    assert blob.data == b"first rendering", (
        "o put sobrescrevia: duas instâncias que sintetizam a mesma fala gravavam duas "
        "renderizações, a segunda por cima da que o tablet já tinha começado a tocar"
    )
    assert kept == b"first rendering", "quem perdia a corrida servia os próprios bytes"


async def test_a_clip_nobody_wrote_yet_is_written_and_comes_back_as_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blob = _Blob()
    _the_bucket_holds(monkeypatch, blob)

    kept = await GcsPlatformStore(_settings()).put_once(
        "tts/v/m/f/a.mp3", b"only rendering", "audio/mpeg"
    )

    assert blob.data == b"only rendering"
    assert kept == b"only rendering"
