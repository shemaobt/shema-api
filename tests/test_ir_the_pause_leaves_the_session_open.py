"""However many turns run out of redrafts in a row, the session stays in progress.

Three validation failures in a row used to be the assessor's ladder ending the interview
and calling somebody, then later a ladder that spoke category E on the third and stayed
there. Her code never counts a run at all: an exhausted turn always speaks the same line,
the fourth of the A family, named by the attempt it gave up on — and the session behind it
is still in progress, because the call for a person is the tablet's, on its own triggers,
never the server's.
"""

import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.db.models.internalization_room import IRSessionStatus
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import create_session, get_session
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import KEY, PREFIX, P
from tests.room_harness import room_client

REFUSED = json.dumps({"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]})


async def _refusing_models(*, system_prompt: str, **_: Any) -> str:
    if "corrected_response" in system_prompt:
        return REFUSED
    return "Rute casou com Malom."


async def _heard(*_: Any, **__: Any) -> HeardSpeech:
    return HeardSpeech(text="a fome chegou")


async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    entry = SynthesizedSpeech(
        audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/voice/t.mp3"
    )
    return entry, False


async def _noop_settle(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(db_session, monkeypatch):
    monkeypatch.setattr(sessions_api, "heard_speech", _heard)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", _noop_settle)
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", _refusing_models
    )
    async with room_client(db_session, monkeypatch) as c:
        yield c


async def test_three_exhausted_turns_in_a_row_all_speak_the_fourth_a_line_not_a_pause(
    client, db_session: AsyncSession
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    spoken = []
    for _ in range(3):
        answered = await client.post(
            f"{PREFIX}/sessions/{session.id}/turns",
            headers={"X-Room-Key": KEY},
            files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
        )
        assert answered.status_code == 200, answered.text[:300]
        spoken.append(answered.json()["fixed_line"])

    assert spoken == ["A3", "A3", "A3"], (
        "a escada dava A0, A1 e a pausa; agora toda tentativa esgotada dá a mesma linha, a "
        "quarta de A, nomeada pela tentativa em que desistiu"
    )
    assert (await get_session(db_session, session.id)).status is IRSessionStatus.IN_PROGRESS, (
        "a rota marcava NEEDS_PERSON na linha E e o círculo parava até um facilitador vir"
    )
