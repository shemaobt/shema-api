"""What a turn leaves behind when the room never gets to speak it.

Read from the endpoint and then from a second database session, because the fact under
test is durability. Re-reading through the request's own session would only show its
identity map, which is not what survives.
"""

import json
import sys
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.sessions import (
    append_exchange,
    create_session,
)
from app.services.platform.tts import SynthesizedSpeech

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
P = "P03"
FIRST_QUESTION = "Quem aparece nesta parte?"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"
TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"
EXCERPT = "Noemi voltou"


class _SynthesisThatCanBreak:
    """The room's voice, breaking on demand.

    Breaking it is how this file reaches the moment under test — the turn is decided and
    the state is ready, and the team has still heard nothing.
    """

    def __init__(self) -> None:
        self.working = True
        self.spoken: list[str] = []

    async def __call__(self, text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        if not self.working:
            raise RuntimeError("the voice service is down")
        self.spoken.append(text)
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/voice/m/f/{abs(hash(text))}.mp3",
        )
        return entry, False


@pytest.fixture()
async def voice() -> _SynthesisThatCanBreak:
    return _SynthesisThatCanBreak()


@pytest.fixture()
async def reread(test_engine):
    """The session as the next request would load it: a new connection, no identity map."""

    async def _reread(session_id: str) -> IRSession:
        factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as fresh:
            loaded = await fresh.get(IRSession, session_id)
            assert loaded is not None
            return loaded

    return _reread


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, voice: _SynthesisThatCanBreak
):
    """The endpoint as the tablet reaches it, answering with whatever the handlers produce.

    ``raise_app_exceptions=False`` because one of these tests is about the status the app
    still receives: re-raising would leave no response to assert on.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voice)

    async def _heard(audio: bytes, **_: Any) -> Any:
        from app.services.internalization_room.hearing import HeardSpeech

        return HeardSpeech(text=TEAM_ANSWER)

    monkeypatch.setattr(sessions_api, "heard_speech", _heard)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class _AgreeingModels:
    """A Guide that drafts one short line and a Validator that passes it."""

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


@pytest.fixture()
def models_agree(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Guide drafts and the Validator passes it."""
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", _AgreeingModels()
    )


@pytest.fixture()
async def waiting_room(db_session: AsyncSession) -> IRSession:
    """A room that has asked its question and is waiting on the answer."""
    session = await create_session(db_session, language="pt", pericope=P)
    return await append_exchange(
        db_session, session, team_utterance="", guide_response=FIRST_QUESTION
    )


async def _the_team_answers(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
    )


def _guide_lines(session: IRSession) -> list[str]:
    return [
        message.get("text", "")
        for message in (session.messages or [])
        if message.get("role") == "guide"
    ]


async def test_a_turn_the_room_did_speak_is_remembered_whole(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    voice: _SynthesisThatCanBreak,
    models_agree: None,
    reread,
) -> None:
    """The counterweight. A room that speaks and forgets is worse than one that remembers
    too eagerly, so the happy path has to keep what it spoke."""
    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    session = await reread(waiting_room.id)
    assert _guide_lines(session) == [FIRST_QUESTION, GUIDE_LINE]
    assert voice.spoken == [GUIDE_LINE]


async def test_a_room_that_cannot_speak_still_says_so_to_the_tablet(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    voice: _SynthesisThatCanBreak,
    models_agree: None,
) -> None:
    """The fix is about what is kept, not about hiding the failure.

    A silent 200 would leave the app with no line to play and no reason why, which is the
    one outcome worse than the error it already shows.
    """
    voice.working = False

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 500


async def test_a_turn_that_fails_after_the_voice_still_reaches_no_one(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    voice: _SynthesisThatCanBreak,
    models_agree: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Speaking first does not create a turn the team heard but the room forgot.

    A synthesized clip reaches the team only as the handle in this response, so a request
    that fails after synthesis hands the app nothing to play. The clip is left paid for in
    the bucket, where the retry finds it.
    """
    from app.api.internalization_room import sessions as sessions_api

    async def _the_database_goes_away(*_args: Any, **_kwargs: Any) -> IRSession:
        raise RuntimeError("the database went away")

    monkeypatch.setattr(sessions_api.room, "append_exchange", _the_database_goes_away)

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 500
    assert "audio_url" not in answered.text
