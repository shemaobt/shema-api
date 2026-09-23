"""A live opening now speaks only its two movements, and waits for neither the whole line.

Before this file, `_voice_the_turn` synthesized the whole line and the two movements in
parallel on every two-movement opening, and `audio_url` was always the whole line's clip
even once both movements were ready — the segments were purely additive, and the reply
waited for whichever of the three came back last.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.sessions import create_session
from app.services.platform import tts

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"

WHOLE = "O todo da passagem.\n\nA cena e o convite."
FIRST = "O todo da passagem."
SECOND = "A cena e o convite."


class _Bucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def put_once(self, key: str, data: bytes, content_type: str) -> bytes:
        return self.objects.setdefault(key, data)


class _Elevenlabs:
    """Every call is recorded; a chosen text can be held back or refused on command."""

    def __init__(self, *, holds: str | None = None, refuses: str | None = None) -> None:
        self.calls: list[str] = []
        self._holds = holds
        self._refuses = refuses
        self.may_proceed = asyncio.Event()

    async def post(self, *_: Any, json: dict[str, Any], **__: Any) -> SimpleNamespace:
        text = json["text"]
        if text == self._holds:
            await asyncio.wait_for(self.may_proceed.wait(), timeout=2)
        self.calls.append(text)
        if text == self._refuses:
            return SimpleNamespace(status_code=503, content=b"", text="busy")
        return SimpleNamespace(status_code=200, content=f"audio-for-{text}".encode(), text="")


class _ElevenlabsWhereAMovementWaitsForTheWholeLine:
    """Each movement answers once the whole line has been asked for, or gives up waiting.

    Whether the whole line was under way by then is written down per movement, so a
    fallback that asks for it only after both movements came back reads as two falses
    rather than as a race the test happened to win.
    """

    def __init__(self, *, refuses: str) -> None:
        self.calls: list[str] = []
        self.whole_under_way: dict[str, bool] = {}
        self._refuses = refuses
        self._whole_started = asyncio.Event()

    async def post(self, *_: Any, json: dict[str, Any], **__: Any) -> SimpleNamespace:
        text = json["text"]
        self.calls.append(text)
        if text == WHOLE:
            self._whole_started.set()
        else:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._whole_started.wait(), timeout=0.5)
            self.whole_under_way[text] = self._whole_started.is_set()
        if text == self._refuses:
            return SimpleNamespace(status_code=503, content=b"", text="busy")
        return SimpleNamespace(status_code=200, content=f"audio-for-{text}".encode(), text="")


@pytest.fixture()
def bucket() -> _Bucket:
    return _Bucket()


@pytest.fixture(autouse=True)
async def _no_whole_line_outlives_its_test() -> AsyncIterator[None]:
    from app.services.internalization_room import clip_flight

    yield
    left = set(clip_flight._IN_FLIGHT.values())
    for task in left:
        task.cancel()
    if left:
        await asyncio.wait(left)
    clip_flight.forget_flights()


async def _client(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: _Elevenlabs | _ElevenlabsWhereAMovementWaitsForTheWholeLine,
    bucket: _Bucket,
) -> httpx.AsyncClient:
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    monkeypatch.setattr(tts, "_make_client", lambda: elevenlabs)
    monkeypatch.setattr(tts, "_default_store", lambda _: bucket)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _opens_in_two_movements(
    monkeypatch: pytest.MonkeyPatch, *, movements: list[str] | None = None
) -> None:
    from app.api.internalization_room import sessions as sessions_api
    from app.services.internalization_room.run_turn import TurnOutcome

    chosen = [FIRST, SECOND] if movements is None else movements

    async def _opening(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech=WHOLE, transcript="", movements=chosen)

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _opening)


async def test_a_live_opening_synthesizes_only_its_two_movements(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    elevenlabs = _Elevenlabs(holds=WHOLE)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )

    assert opened.status_code == 200
    assert elevenlabs.calls == [FIRST, SECOND], (
        "a resposta esperava pela linha inteira mesmo sem precisar de suas palavras"
    )
    body = opened.json()
    urls = [segment["audio_url"] for segment in body["segments"]]
    assert body["audio_url"] == urls[0], (
        "audio_url continuava sendo a fala inteira mesmo com os dois movimentos prontos"
    )


async def test_the_whole_line_is_voiced_in_the_background_so_a_repeat_costs_nothing(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    elevenlabs = _Elevenlabs(holds=WHOLE)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )
        assert opened.status_code == 200
        elevenlabs.may_proceed.set()
        again = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )

    assert again.status_code == 200
    assert elevenlabs.calls == [FIRST, SECOND, WHOLE], (
        "o diga de novo pagou a ElevenLabs outra vez por uma linha que já estava sendo feita"
    )


async def test_a_background_synthesis_failure_does_not_change_the_turns_answer(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    bucket: _Bucket,
    caplog: pytest.LogCaptureFixture,
) -> None:
    elevenlabs = _Elevenlabs(holds=WHOLE, refuses=WHOLE)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    with caplog.at_level(logging.WARNING, logger="app.services.internalization_room.clip_flight"):
        async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
            opened = await asyncio.wait_for(
                client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
                timeout=2,
            )
            assert opened.status_code == 200, (
                "a resposta da abertura dependia de uma síntese que roda em segundo plano"
            )
            elevenlabs.may_proceed.set()
            for _ in range(20):
                if WHOLE in elevenlabs.calls:
                    break
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.01)

    body = opened.json()
    urls = [segment["audio_url"] for segment in body["segments"]]
    assert body["audio_url"] == urls[0]
    assert elevenlabs.calls == [FIRST, SECOND, WHOLE]
    assert "a clip could not be voiced: UpstreamServiceError" in caplog.text, (
        "a falha da linha inteira que ninguém esperava sumiu sem deixar rastro no log"
    )


async def test_a_movement_that_cannot_be_voiced_falls_back_to_the_whole_line(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    elevenlabs = _Elevenlabs(refuses=SECOND)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )
        heard = await client.get(opened.json()["audio_url"], headers={"X-Room-Key": KEY})

    assert opened.status_code == 200
    assert elevenlabs.calls.count(WHOLE) == 1, "a fala inteira foi sintetizada mais de uma vez"
    body = opened.json()
    assert body["segments"] == [], "o fallback ainda devolvia os movimentos parciais"
    assert heard.content == f"audio-for-{WHOLE}".encode(), (
        "a fala inteira deveria ter voltado como o áudio do turno"
    )


async def test_a_refused_movement_finds_the_whole_line_already_under_way(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    elevenlabs = _ElevenlabsWhereAMovementWaitsForTheWholeLine(refuses=SECOND)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )

    assert opened.status_code == 200
    assert elevenlabs.whole_under_way[FIRST] and elevenlabs.whole_under_way[SECOND], (
        "a fala inteira só começava depois de os dois movimentos voltarem, e uma cena "
        "recusada pagava os movimentos e a fala inteira em série"
    )
    assert elevenlabs.calls.count(WHOLE) == 1, (
        "a mesma abertura sintetizou a fala inteira mais de uma vez"
    )
    assert opened.json()["segments"] == []


def _clip_behind(audio_url: str, bucket: _Bucket) -> bytes | None:
    from app.core.config import get_settings
    from app.services.internalization_room.voice_handles import from_handle

    key = from_handle(audio_url.rsplit("/", 1)[-1], settings=get_settings())
    return bucket.objects.get(key) if key else None


async def test_a_turn_without_movements_still_speaks_only_the_whole_line(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    elevenlabs = _Elevenlabs()
    _opens_in_two_movements(monkeypatch, movements=[])
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )

    assert opened.status_code == 200
    assert elevenlabs.calls == [WHOLE], (
        "um turno sem movimentos passou a sintetizar mais do que a fala inteira"
    )
    assert opened.json()["segments"] == []
