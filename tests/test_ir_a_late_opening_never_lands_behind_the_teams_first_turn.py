"""A late opening is not the session's third line, and it does not vanish either.

The tablet asks for the opening, the Guide's call hangs on the provider, the tablet gives
up and the team taps and speaks; their turn is answered and stored first. When the opening
finally lands it used to be appended behind the team's turn — `[team, guide, guide]` — and,
once the session row learned to refuse a stale write, it took a 409 instead and was never
stored and never remembered, so a resend of its `turn_id` fell through to the re-open path
and was answered with the team turn's speech.

Two independent ``AsyncSession``s stand in for the opening and the team's turn, the way
two concurrent requests would, rather than sharing one identity map that would hide the
lateness entirely.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.sessions import (
    append_exchange,
    append_opening,
    create_session,
    get_session,
    save_comprehension,
)
from app.services.internalization_room.voice_handles import clip_url
from app.services.platform.tts import SynthesizedSpeech
from tests.clip_flight_harness import voiced_through
from tests.release_harness import KEY, PREFIX, P
from tests.room_harness import room_client

OPENING = "Eu sou o Guia. Hoje a historia e a de Rute, que ficou com Noemi."
TEAM_ANSWER = "Noemi voltou para Belem com Rute no tempo da colheita"
TEAM_TURN_LINE = "Vamos ficar nesta cena. O que voces contariam?"
SESSIONS_LOGGER = "app.services.internalization_room.sessions"


@pytest.fixture()
def rival_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def test_an_opening_on_a_session_where_nobody_has_spoken_is_its_first_line(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await create_session(db_session, pericope=P, language="pt")

    landed = await append_opening(db_session, session, guide_response=OPENING)

    assert landed is True
    async with rival_factory() as fresh_db:
        reread = await get_session(fresh_db, session.id)
    assert [message["text"] for message in reread.messages] == [OPENING]


async def test_an_opening_landing_after_the_teams_first_turn_is_dropped_and_logged(
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = await create_session(db_session, pericope=P, language="pt")

    async with rival_factory() as rival_db:
        late_opening = await get_session(rival_db, session.id)

        await save_comprehension(
            db_session, session, ComprehensionState(practiced_scene_ids=["S1"])
        )
        await append_exchange(
            db_session, session, team_utterance=TEAM_ANSWER, guide_response=TEAM_TURN_LINE
        )

        with caplog.at_level(logging.WARNING, logger=SESSIONS_LOGGER):
            landed = await append_opening(
                rival_db, late_opening, guide_response=OPENING, state=ComprehensionState()
            )

    assert landed is False
    async with rival_factory() as fresh_db:
        reread = await get_session(fresh_db, session.id)
    assert [message["text"] for message in reread.messages] == [TEAM_ANSWER, TEAM_TURN_LINE], (
        "a abertura atrasada era apendada atrás do turno da equipe, ou levava 409 e sumia"
    )
    assert reread.comprehension["practiced_scene_ids"] == ["S1"], (
        "o estado lido antes de o Guia pensar não pode escrever por cima do da equipe"
    )
    assert session.id in caplog.text and "opening" in caplog.text, (
        "descartada em silêncio, nada dizia que a abertura chegou tarde"
    )


class _TeamSpeaksWhileTheGuideThinks:
    """A Guide whose one call is long enough for the team to take a whole turn."""

    def __init__(self, rival_factory: async_sessionmaker[AsyncSession], session_id: str) -> None:
        self.rival_factory = rival_factory
        self.session_id = session_id

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return '{"verdict": "pass", "issues": []}'
        async with self.rival_factory() as rival_db:
            team = await get_session(rival_db, self.session_id)
            await append_exchange(
                rival_db, team, team_utterance=TEAM_ANSWER, guide_response=TEAM_TURN_LINE
            )
        return OPENING


class _RecordingVoice:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    async def __call__(self, text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        self.spoken.append(text)
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=self.key_of(text),
        )
        return entry, False

    @staticmethod
    def key_of(text: str) -> str:
        return f"tts/voice/{len(text)}.mp3"


@pytest.fixture()
async def client(db_session, monkeypatch):
    async with room_client(db_session, monkeypatch) as c:
        yield c


async def _ask_for_the_opening(client, session_id: str):
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        data={"turn_id": "abertura"},
    )


async def test_a_tablet_asking_for_the_opening_again_hears_the_opening_not_the_teams_turn(
    client, db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await create_session(db_session, pericope=P, language="pt")
    voice = _RecordingVoice()
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voice)
    monkeypatch.setattr(
        sessions_api.room,
        "facilitator_speech_to_come",
        voiced_through(voice, _RecordingVoice.key_of),
    )
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"],
        "call_agent",
        _TeamSpeaksWhileTheGuideThinks(rival_factory, session.id),
    )

    late = await _ask_for_the_opening(client, session.id)
    assert late.status_code == 200, late.text[:300]
    assert late.json()["audio_url"] == clip_url(_RecordingVoice.key_of(OPENING))

    again = await _ask_for_the_opening(client, session.id)
    assert again.status_code == 200, again.text[:300]
    assert again.json()["audio_url"] == late.json()["audio_url"], (
        "o reenvio da abertura era respondido pelo _say_it_again com a fala do turno da equipe"
    )
    assert TEAM_TURN_LINE not in voice.spoken

    async with rival_factory() as fresh_db:
        reread = await get_session(fresh_db, session.id)
    assert [message["text"] for message in reread.messages] == [TEAM_ANSWER, TEAM_TURN_LINE]
