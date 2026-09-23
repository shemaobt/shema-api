"""A live opening now speaks only its two movements, and waits for neither the whole line.

Before this file, `_voice_the_turn` synthesized the whole line and the two movements in
parallel on every two-movement opening, and `audio_url` was always the whole line's clip
even once both movements were ready — the segments were purely additive, and the reply
waited for whichever of the three came back last.
"""

from __future__ import annotations

import asyncio
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

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


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


@pytest.fixture()
def bucket() -> _Bucket:
    return _Bucket()


async def _client(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: _Elevenlabs,
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
        "a linha inteira era sintetizada junto dos dois movimentos, e a resposta esperava "
        "por ela mesmo sem precisar de suas palavras"
    )
    body = opened.json()
    urls = [segment["audio_url"] for segment in body["segments"]]
    assert body["audio_url"] == urls[0], (
        "audio_url continuava sendo a fala inteira mesmo com os dois movimentos prontos"
    )


async def test_the_whole_line_is_cached_in_the_background_so_a_repeat_costs_nothing(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    from app.api.internalization_room import sessions as sessions_api

    elevenlabs = _Elevenlabs(holds=WHOLE)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )
        assert opened.status_code == 200

        pending = list(sessions_api._PENDING_WHOLE_LINE_TASKS)
        assert pending, (
            "a linha inteira só era sintetizada quando alguém pedia, nunca sozinha depois "
            "da abertura já ter respondido"
        )
        elevenlabs.may_proceed.set()
        await asyncio.wait_for(asyncio.gather(*pending), timeout=2)
        assert elevenlabs.calls == [FIRST, SECOND, WHOLE], (
            "a linha inteira não chegou a ser cacheada em segundo plano"
        )

        again = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )

    assert again.status_code == 200
    assert elevenlabs.calls == [FIRST, SECOND, WHOLE], (
        "o diga de novo pagou a ElevenLabs outra vez por uma linha que o segundo plano já "
        "tinha posto no bucket"
    )


async def test_a_background_synthesis_failure_does_not_change_the_turns_answer(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    from app.api.internalization_room import sessions as sessions_api

    elevenlabs = _Elevenlabs(holds=WHOLE, refuses=WHOLE)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )
        assert opened.status_code == 200, (
            "a resposta da abertura dependia de uma síntese que só roda depois, em segundo plano"
        )

        pending = list(sessions_api._PENDING_WHOLE_LINE_TASKS)
        assert pending, "a linha inteira nem chegou a ser agendada em segundo plano"
        elevenlabs.may_proceed.set()
        await asyncio.wait_for(asyncio.gather(*pending), timeout=2)

    body = opened.json()
    urls = [segment["audio_url"] for segment in body["segments"]]
    assert body["audio_url"] == urls[0]
    assert elevenlabs.calls == [FIRST, SECOND, WHOLE]


async def test_a_failed_movement_falls_back_to_the_whole_line_at_once(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    from app.api.internalization_room import sessions as sessions_api

    elevenlabs = _Elevenlabs(refuses=SECOND)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )

    assert opened.status_code == 200
    assert set(elevenlabs.calls[:2]) == {FIRST, SECOND}
    assert elevenlabs.calls[2] == WHOLE, (
        "uma cena recusada não caiu para a fala inteira na hora, como o fallback de hoje"
    )
    body = opened.json()
    assert body["segments"] == [], "o fallback ainda devolvia os movimentos parciais"
    assert body["audio_url"], "a fala inteira deveria ter voltado como o áudio do turno"
    assert not sessions_api._PENDING_WHOLE_LINE_TASKS, (
        "o fallback síncrono não devia agendar outra síntese da mesma fala em segundo plano"
    )


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
