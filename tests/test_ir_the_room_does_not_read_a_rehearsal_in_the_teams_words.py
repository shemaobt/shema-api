import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import (
    append_exchange,
    create_session,
)
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import KEY, PREFIX
from tests.room_harness import room_client
from tests.turn_harness import the_room_agent_is

P = "P03"
INVITATION = "Agora ensaiem juntos esta cena na língua de vocês. Quando terminarem, digam pronto."


async def _models(*, system_prompt: str, **_: Any) -> str:
    if "corrected_response" in system_prompt:
        return json.dumps({"verdict": "pass", "issues": []})
    return "Que bom. O que vocês contaram no ensaio?"


async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    entry = SynthesizedSpeech(
        audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/voice/m/f/1.mp3"
    )
    return entry, False


async def _settled_later(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    from app.api.internalization_room import sessions as sessions_api

    the_room_agent_is(monkeypatch, turn=_models)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", _settled_later)
    async with room_client(db_session, monkeypatch) as c:
        yield c


@pytest.mark.parametrize("word", ["Pronto.", "Já ensaiamos."])
async def test_the_teams_word_after_an_invitation_changes_nothing_the_room_stored(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    word: str,
) -> None:
    from app.api.internalization_room import sessions as sessions_api

    async def _heard(audio: bytes, **_: Any) -> HeardSpeech:
        return HeardSpeech(text=word)

    monkeypatch.setattr(sessions_api, "heard_speech", _heard)
    session = await create_session(db_session, language="pt", pericope=P)
    session.comprehension = {"practiced_scene_ids": ["S1"], "invited_scene_id": "S2"}
    await db_session.commit()
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response=INVITATION
    )
    stored = dict(session.comprehension or {})

    answered = await client.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
    )
    await db_session.refresh(session)

    assert answered.status_code == 200, answered.text
    assert session.comprehension == stored, (
        "a palavra da equipe depois do convite marcava a cena como ensaiada"
    )
