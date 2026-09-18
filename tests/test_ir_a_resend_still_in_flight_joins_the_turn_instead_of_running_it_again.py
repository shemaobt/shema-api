"""A resend of a turn still in flight joins that turn; it does not run the fan-out again.

The tablet asks for the opening, the Guide's call hangs on the provider, the tablet's own
wait expires and it sends the same `turn_id` again while the first request is still
running. The row that answers a resend is only written once the first request has
finished, so the second used to find nothing, ask the Guide a second time, synthesize a
second time, and either append the opening twice or lose the row's version race.

Two clients over two independent ``AsyncSession``s stand in for the two requests, the way
`test_room_device_credential_collection_api` drives its two racing collections: one shared
session would serialise them and hide the overlap entirely.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.sessions import create_session, get_session
from app.services.internalization_room.voice_handles import clip_url
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import KEY, PREFIX, P
from tests.room_harness import room_client

OPENING = "Eu sou o Guia. Hoje a historia e a de Rute, que ficou com Noemi."
VOICED_AS = "tts/voice/abertura.mp3"


class _GuideStillThinking:
    """A Guide that parks on its first call until the case lets it answer, and counts."""

    def __init__(self) -> None:
        self.asked = 0
        self.thinking = asyncio.Event()
        self.answer = asyncio.Event()

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return '{"verdict": "pass", "issues": []}'
        self.asked += 1
        self.thinking.set()
        await self.answer.wait()
        return OPENING


class _CountingVoice:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        self.calls += 1
        entry = SynthesizedSpeech(
            audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key=VOICED_AS
        )
        return entry, False


@pytest.fixture()
def rival_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def _ask_for_the_opening(client, session_id: str):
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        data={"turn_id": "abertura"},
    )


async def test_two_concurrent_posts_of_one_turn_id_ask_the_guide_once_and_answer_alike(
    db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await create_session(db_session, pericope=P, language="pt")
    guide = _GuideStillThinking()
    voice = _CountingVoice()
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", guide
    )
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voice)

    async with (
        rival_factory() as one,
        rival_factory() as two,
        room_client(one, monkeypatch) as first_tablet,
        room_client(two, monkeypatch) as resending_tablet,
    ):
        first = asyncio.create_task(_ask_for_the_opening(first_tablet, session.id))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        second = asyncio.create_task(_ask_for_the_opening(resending_tablet, session.id))
        await asyncio.wait({second}, timeout=0.2)
        assert guide.asked == 1, "o Guia foi chamado duas vezes para um só turn_id"
        guide.answer.set()
        landed, resent = await asyncio.gather(first, second)

    assert landed.status_code == 200, landed.text[:300]
    assert resent.status_code == 200, resent.text[:300]
    assert resent.json() == landed.json(), "o reenvio tem de ouvir a resposta do turno em voo"
    assert voice.calls == 1, "a fala foi sintetizada duas vezes para um só turn_id"

    async with rival_factory() as fresh_db:
        reread = await get_session(fresh_db, session.id)
    assert [message["text"] for message in reread.messages] == [OPENING], (
        "a sessão gravou a mesma abertura duas vezes"
    )


async def test_the_tablet_that_gave_up_does_not_take_the_turn_away_from_the_one_resending(
    db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first request is cancelled mid-Guide, and with it the session it was given.

    Whether the deployed server cancels a handler when its client hangs up is the server's
    business and has changed across releases; the turn in flight must not depend on it.
    """
    session = await create_session(db_session, pericope=P, language="pt")
    guide = _GuideStillThinking()
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", guide
    )
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _CountingVoice())

    async with room_client(db_session, monkeypatch, per_request=rival_factory) as tablet:
        first = asyncio.create_task(_ask_for_the_opening(tablet, session.id))
        await asyncio.wait_for(guide.thinking.wait(), timeout=5)
        second = asyncio.create_task(_ask_for_the_opening(tablet, session.id))
        await asyncio.wait({second}, timeout=0.2)
        first.cancel()
        await asyncio.wait({first})
        guide.answer.set()
        resent = await second

    assert first.cancelled()
    assert resent.status_code == 200, resent.text[:300]
    assert resent.json()["audio_url"] == clip_url(VOICED_AS)

    async with rival_factory() as fresh_db:
        reread = await get_session(fresh_db, session.id)
    assert [message["text"] for message in reread.messages] == [OPENING], (
        "o turno em voo escrevia pela sessão do request que desistiu, já fechada"
    )
