"""ENG-1304 — the Guide reads the room facts in her order, on one session, at the tablet's door.

Criterion 4: the turn that sends a scene rehearsal to be checked ends its facts with ACCEPTED
READINGS, and the next ordinary turn of the same session carries none.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.llm import CACHE_BREAK
from tests.hard_stretch_harness import a_session
from tests.hearing_harness import nothing_settles, the_transcriber_hears
from tests.room_harness import the_room_speaks
from tests.scene_rehearsal_harness import IR, SAID, a_room, record, recording, translated
from tests.turn_harness import the_room_agent_is

ACCEPTED = "ACCEPTED READINGS FOR THE SCENE THIS TELLING CHECKS"


class Guide:
    def __init__(self) -> None:
        self.systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.systems.append(system_prompt)
        return "Obrigado. Vamos ver essa cena juntos."

    def facts(self, turn: int) -> str:
        return self.systems[turn].partition(CACHE_BREAK)[2]


@pytest.fixture()
async def room(db_session, rival_factory, monkeypatch):
    async with a_room(db_session, rival_factory, monkeypatch) as built:
        yield built


@pytest.fixture()
def guide(monkeypatch: pytest.MonkeyPatch) -> Guide:
    the_room_speaks(monkeypatch)
    nothing_settles(monkeypatch)
    drafting = Guide()
    the_room_agent_is(monkeypatch, turn=drafting)
    return drafting


async def _a_p11_scene_4_rehearsal(room, db_session: AsyncSession) -> tuple[str, str]:
    session_id = await a_session(db_session, pericope="P11")
    opened = await room.client.post(f"{IR}/sessions/{session_id}/turns")
    assert opened.status_code == 200, opened.text
    kept = await record(room, session_id, recording(40, 1), "S4")
    assert kept.status_code == 200, kept.text
    rehearsal_id = str(kept.json()["rehearsal_id"])
    await translated(room, session_id, rehearsal_id, [(0, 20000)])
    return session_id, rehearsal_id


async def test_a_checking_turn_ends_with_the_accepted_readings_and_the_next_ordinary_turn_has_none(
    room, guide, db_session, monkeypatch
) -> None:
    session_id, rehearsal_id = await _a_p11_scene_4_rehearsal(room, db_session)

    checking = await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/send",
        data={"turn_id": str(uuid.uuid4())},
    )
    the_transcriber_hears(monkeypatch, SAID, "pt", 1.0)
    ordinary = await room.client.post(
        f"{IR}/sessions/{session_id}/turns",
        files={"file": ("fala.wav", recording(2, 7), "audio/wav")},
    )

    assert (checking.status_code, ordinary.status_code) == (200, 200), (
        checking.text,
        ordinary.text,
    )
    assert len(guide.systems) == 3, "o Guia não falou na abertura, no «terminei» e no turno comum"
    assert guide.facts(1).split("\n\n")[-1].startswith(ACCEPTED), (
        "o turno que mandou o ensaio para ser conferido não acabava com as leituras aceitas"
    )
    assert guide.facts(1).index("MOMENT:") < guide.facts(1).index(ACCEPTED), (
        "as leituras aceitas vinham antes do momento"
    )
    assert ACCEPTED not in guide.systems[2], (
        "o turno comum seguinte da mesma sessão ainda levava as leituras aceitas do anterior"
    )
