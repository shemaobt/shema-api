import json
import sys
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import (
    append_exchange,
    apply_coverage,
    create_session,
)
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import KEY, PREFIX
from tests.room_harness import room_client

P = "P03"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"


async def _models(*, system_prompt: str, **_: Any) -> str:
    if "corrected_response" in system_prompt:
        return json.dumps({"verdict": "pass", "issues": []})
    return GUIDE_LINE


async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    entry = SynthesizedSpeech(
        audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/voice/m/f/1.mp3"
    )
    return entry, False


async def _heard(audio: bytes, **_: Any) -> HeardSpeech:
    return HeardSpeech(text="Noemi voltou para Belém com Rute")


async def _settled_later(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    from app.api.internalization_room import sessions as sessions_api

    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", _models
    )
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(sessions_api, "heard_speech", _heard)
    monkeypatch.setattr(sessions_api, "settle_coverage", _settled_later)
    async with room_client(db_session, monkeypatch) as c:
        yield c


@pytest.fixture()
async def worked_through(db_session: AsyncSession) -> IRSession:
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="Quem aparece nesta parte?"
    )
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    return await apply_coverage(db_session, session.id, whole)


async def test_a_passage_at_the_floor_is_done_though_nobody_reported_a_rehearsal(
    client: httpx.AsyncClient, worked_through: IRSession
) -> None:
    standing = await client.get(
        f"{PREFIX}/sessions/{worked_through.id}", headers={"X-Room-Key": KEY}
    )
    answered = await client.post(
        f"{PREFIX}/sessions/{worked_through.id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
    )

    assert worked_through.status is IRSessionStatus.DONE, (
        "o piso fechado sem relato de ensaio deixava a sessão aberta para sempre"
    )
    assert worked_through.ended_at is not None
    assert standing.json()["done"] is True, "o state pull dizia que a passagem não acabou"
    assert answered.status_code == 200, answered.text
    assert answered.json()["done"] is True, "o turno não pintava o círculo de verde"
