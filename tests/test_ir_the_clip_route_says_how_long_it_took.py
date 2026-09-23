"""How long the clip route spent at the door and at the bucket, and whether it voiced the clip.

The gate and the bucket are each stubbed to take a known time, so the two numbers in the line
can only have come from the route's own clock.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import re
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.voice_handles import to_handle
from app.services.platform.tts import SynthesizedSpeech

PREFIX = "/api/internalization-room"
VOICED_HERE = "tts/RoomVoice/eleven_turbo_v2_5/mp3_44100_128/aaa111/voiced-here.mp3"
VOICED_ELSEWHERE = "tts/RoomVoice/eleven_turbo_v2_5/mp3_44100_128/bbb222/voiced-elsewhere.mp3"
NEVER_STORED = "tts/RoomVoice/eleven_turbo_v2_5/mp3_44100_128/ccc333/never-stored.mp3"
CLIP = b"x" * 1234
AUTH_MS = 100
BUCKET_MS = 100

synthesis = importlib.import_module(
    "app.services.internalization_room.synthesize_facilitator_speech"
)


class _SlowBucket:
    async def get(self, key: str) -> bytes | None:
        await asyncio.sleep(BUCKET_MS / 1000)
        return None if key == NEVER_STORED else CLIP


async def _slow_gate(db: AsyncSession, credential: str) -> Any:
    await asyncio.sleep(AUTH_MS / 1000)
    return SimpleNamespace(project_id=None)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import _deps, router
    from app.api.internalization_room import voice as voice_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_voice_id", "RoomVoice", raising=False)
    monkeypatch.setattr(_deps, "authenticate_device", _slow_gate)
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: _SlowBucket())

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _fetch(client: httpx.AsyncClient, key: str) -> httpx.Response:
    return await client.get(
        f"{PREFIX}/voice/{to_handle(key)}", headers={"X-Device-Credential": "tablet"}
    )


def _voice_get_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if "[voice-get]" in r.getMessage()]


async def test_a_clip_fetch_says_how_long_the_gate_and_the_bucket_each_took(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        fetched = await _fetch(client, VOICED_ELSEWHERE)

    assert fetched.status_code == 200, fetched.text
    lines = _voice_get_lines(caplog)
    assert len(lines) == 1, "a leitura do clipe nunca tinha sido cronometrada"
    spent = {name: int(ms) for name, ms in re.findall(r" (\w+)=(\d+)ms", lines[0])}
    assert spent["auth"] >= AUTH_MS, "a autenticação do tablet não era medida"
    assert spent["gcs"] >= BUCKET_MS
    assert spent["auth"] < AUTH_MS + BUCKET_MS, "o tempo do bucket caía na conta da porta"
    assert spent["gcs"] < AUTH_MS + BUCKET_MS, "o tempo da porta caía na conta do bucket"
    assert " bytes=1234 " in lines[0]
    assert lines[0].endswith(" same_instance=no")


async def test_a_clip_this_instance_voiced_is_told_apart_from_one_voiced_elsewhere(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def _voiced(text: str, **_: Any) -> SynthesizedSpeech:
        return SynthesizedSpeech(
            audio=CLIP, mime_type="audio/mpeg", etag="e", cached=False, key=VOICED_HERE
        )

    monkeypatch.setattr(synthesis, "platform_speech", _voiced)
    await synthesis.synthesize_facilitator_speech("Vamos ouvir de novo.", language="pt")

    with caplog.at_level(logging.INFO):
        await _fetch(client, VOICED_HERE)
        await _fetch(client, VOICED_ELSEWHERE)

    here, elsewhere = _voice_get_lines(caplog)
    assert here.endswith(" same_instance=yes"), (
        "ninguém sabia quantos clipes um cache em memória desta instância teria servido"
    )
    assert elsewhere.endswith(" same_instance=no")


async def test_an_instance_up_for_months_remembers_only_its_latest_clips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _voiced(text: str, **_: Any) -> SynthesizedSpeech:
        return SynthesizedSpeech(
            audio=CLIP, mime_type="audio/mpeg", etag="e", cached=False, key=f"tts/v/{text}.mp3"
        )

    monkeypatch.setattr(synthesis, "platform_speech", _voiced)
    monkeypatch.setattr(synthesis, "_VOICED_HERE", synthesis.OrderedDict())
    monkeypatch.setattr(synthesis, "_VOICED_HERE_KEPT", 2)

    for line in ("primeira", "segunda", "primeira", "terceira"):
        await synthesis.synthesize_facilitator_speech(line, language="pt")

    assert not synthesis.voiced_here("tts/v/segunda.mp3"), "o registro crescia sem limite"
    assert synthesis.voiced_here("tts/v/primeira.mp3"), "a fala repetida era a primeira a sair"
    assert synthesis.voiced_here("tts/v/terceira.mp3")


async def test_a_clip_the_bucket_does_not_hold_still_says_how_long_the_miss_took(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        fetched = await _fetch(client, NEVER_STORED)

    assert fetched.status_code == 404
    lines = _voice_get_lines(caplog)
    assert len(lines) == 1, "o clipe que o bucket não tinha sumia do cronômetro"
    missed = re.search(r" gcs=(\d+)ms bytes=0 same_instance=no$", lines[0])
    assert missed is not None and int(missed.group(1)) >= BUCKET_MS
