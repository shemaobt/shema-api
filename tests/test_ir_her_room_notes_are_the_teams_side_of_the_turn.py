from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import internalization_room as room
from app.services.internalization_room.sessions import create_session
from tests.device_harness import TABLET_TEAM
from tests.hearing_harness import nothing_settles, the_take_lasts, the_transcriber_hears
from tests.opening_harness import NOTE_PT_P03
from tests.release_harness import PREFIX
from tests.room_harness import room_client, the_room_speaks
from tests.turn_harness import P, the_room_agent_is

GUIDE_LINE = "Que bom que vocês ensaiaram. Me contem em português."
NOTE_PT_45 = (
    "[A equipe falou na língua materna por cerca de 45 segundos; sem transcrição — nenhuma "
    "palavra chegou até você.]"
)


class Listening:
    def __init__(self) -> None:
        self.guide_inputs: list[str] = []
        self.validator_systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator_systems.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide_inputs.append(user_content)
        return GUIDE_LINE


@pytest.fixture
def models(monkeypatch: pytest.MonkeyPatch) -> Listening:
    the_room_speaks(monkeypatch)
    listening = Listening()
    the_room_agent_is(monkeypatch, turn=listening)
    nothing_settles(monkeypatch)
    return listening


@pytest.fixture
async def tablet(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, models: Listening
) -> AsyncIterator[httpx.AsyncClient]:
    async with room_client(db_session, monkeypatch) as client:
        yield client


async def test_a_45_second_take_in_another_language_is_her_note_on_the_teams_side_not_the_rooms(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    models: Listening,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await create_session(db_session, project_id=TABLET_TEAM, language="pt", pericope=P)
    session_id = session.id
    opened = await tablet.post(f"{PREFIX}/sessions/{session_id}/turns")
    assert opened.status_code == 200, opened.text
    models.guide_inputs.clear()
    models.validator_systems.clear()
    the_transcriber_hears(monkeypatch, "koeti yoko vitukeovo enepone itukovo", "spa", 0.7)
    the_take_lasts(monkeypatch, 45_000)

    answered = await tablet.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        files={"file": ("ensaio.m4a", b"audio", "audio/m4a")},
    )

    assert answered.status_code == 200, answered.text
    assert models.guide_inputs == [NOTE_PT_45]
    assert f"passage.\n\n{NOTE_PT_45}" in models.validator_systems[0], (
        "o Validador não recebia a nota dela como o que a equipe acabou de dizer"
    )
    db_session.expire_all()
    stored = await room.get_session(db_session, session_id)
    assert [(m["role"], m["text"], m.get("room_note", False)) for m in stored.messages] == [
        ("team", NOTE_PT_P03, False),
        ("guide", GUIDE_LINE, False),
        ("team", NOTE_PT_45, True),
        ("guide", GUIDE_LINE, False),
    ], "a nota da língua materna ficava como uma entrada da sala, fora do lado da equipe"
