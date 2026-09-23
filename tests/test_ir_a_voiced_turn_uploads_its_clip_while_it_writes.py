from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room import llm, usage
from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import (
    append_exchange,
    comprehension_of,
    create_session,
    save_comprehension,
)
from app.services.internalization_room.voice_handles import from_handle
from app.services.platform import tts

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
P = "P03"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam uns aos outros sobre ela?"


class _Models:
    async def create(self, **kwargs: Any) -> SimpleNamespace:
        system = "".join(block["text"] for block in kwargs["system"])
        validating = "corrected_response" in system
        text = json.dumps({"verdict": "pass", "issues": []}) if validating else GUIDE_LINE
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            stop_reason="end_turn",
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=10,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
                cache_creation=None,
            ),
        )


class _Elevenlabs:
    async def post(self, *_: Any, **__: Any) -> SimpleNamespace:
        return SimpleNamespace(status_code=200, content=b"mp3", text="")


class _BucketThatWaitsForTheWrite:
    def __init__(self) -> None:
        self.uploading = asyncio.Event()
        self.written = asyncio.Event()
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.uploading.set()
        await asyncio.wait_for(self.written.wait(), timeout=1)
        await asyncio.sleep(0.05)
        self.objects[key] = data


async def _hearing(audio: bytes, **_: Any) -> HeardSpeech:
    return HeardSpeech(text="Noemi voltou para Belém com Rute no tempo da colheita")


async def _settles_nothing(**_: Any) -> None:
    return None


@pytest.fixture(autouse=True)
def _forget_which_rung_answered():
    llm._SETTLED.clear()
    usage.forget_sessions()
    yield
    llm._SETTLED.clear()
    usage.forget_sessions()


@pytest.fixture()
def bucket() -> _BucketThatWaitsForTheWrite:
    return _BucketThatWaitsForTheWrite()


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _BucketThatWaitsForTheWrite
):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-fake", raising=False)
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    monkeypatch.setattr(sessions_api, "heard_speech", _hearing)
    monkeypatch.setattr(sessions_api, "settle_coverage", _settles_nothing)
    monkeypatch.setattr(
        llm.anthropic, "AsyncAnthropic", lambda **_: SimpleNamespace(messages=_Models())
    )
    monkeypatch.setattr(tts, "_make_client", _Elevenlabs)
    monkeypatch.setattr(tts, "_default_store", lambda _: bucket)

    appended = sessions_api.room.append_exchange

    async def _append_then_say_so(*args: Any, **kwargs: Any) -> IRSession:
        session = await appended(*args, **kwargs)
        await asyncio.wait_for(bucket.uploading.wait(), timeout=1)
        bucket.written.set()
        return session

    monkeypatch.setattr(sessions_api.room, "append_exchange", _append_then_say_so)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture()
async def waiting_room(db_session: AsyncSession) -> IRSession:
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="Quem aparece nesta parte?"
    )
    state = comprehension_of(session)
    state.active_probe = ActiveProbe(id="probe-1", purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT)
    return await save_comprehension(db_session, session, state)


async def test_the_clip_uploads_while_the_turn_is_written_and_lands_before_the_answer(
    client: httpx.AsyncClient, waiting_room: IRSession, bucket: _BucketThatWaitsForTheWrite
) -> None:
    from app.core.config import get_settings

    answered = await client.post(
        f"{PREFIX}/sessions/{waiting_room.id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("answer.m4a", b"sixteen bytes!!!", "audio/m4a")},
    )

    assert answered.status_code == 200, (
        "a escrita no banco terminava inteira antes de o upload começar, e a resposta "
        "esperava as duas coisas uma atrás da outra"
    )
    handle = answered.json()["audio_url"].rsplit("/", 1)[-1]
    key = from_handle(handle, settings=get_settings())
    assert key in bucket.objects, (
        "o upload do clipe ao GCS esperava inteiro antes da escrita no banco começar, e a "
        "resposta só saía depois das duas coisas, uma atrás da outra"
    )


WHOLE = "O todo da passagem.\n\nA cena e o convite."
FIRST = "O todo da passagem."
SECOND = "A cena e o convite."


class _ElevenlabsThatRefusesTheWholeLine:
    def __init__(self) -> None:
        self.first_voiced = asyncio.Event()
        self.whole_refused = asyncio.Event()

    async def post(self, *_: Any, json: dict[str, Any], **__: Any) -> SimpleNamespace:
        if json["text"] == FIRST:
            self.first_voiced.set()
            return SimpleNamespace(status_code=200, content=b"o todo", text="")
        if json["text"] == SECOND:
            await asyncio.wait_for(self.whole_refused.wait(), timeout=1)
            await asyncio.sleep(0.05)
            return SimpleNamespace(status_code=200, content=b"a cena", text="")
        await asyncio.wait_for(self.first_voiced.wait(), timeout=1)
        self.whole_refused.set()
        return SimpleNamespace(status_code=503, content=b"", text="busy")


class _Bucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


async def test_a_movement_already_voiced_reaches_the_bucket_even_when_the_whole_line_fails(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.internalization_room import sessions as sessions_api
    from app.services.internalization_room.run_turn import TurnOutcome

    async def _opening(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech=WHOLE, transcript="", movements=[FIRST, SECOND])

    elevenlabs = _ElevenlabsThatRefusesTheWholeLine()
    store = _Bucket()
    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _opening)
    monkeypatch.setattr(tts, "_make_client", lambda: elevenlabs)
    monkeypatch.setattr(tts, "_default_store", lambda _: store)
    session = await create_session(db_session, language="pt", pericope="OV")

    refused = await client.post(
        f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}
    )

    assert refused.status_code == 502
    assert b"o todo" in store.objects.values(), (
        "a fala inteira falhava depois de o movimento ter sido sintetizado, e o clipe já "
        "pago à ElevenLabs nunca chegava ao bucket"
    )
    assert b"a cena" in store.objects.values(), (
        "um movimento ainda em síntese quando a fala inteira falhou terminava depois, pago, "
        "e ninguém mais o subia"
    )
