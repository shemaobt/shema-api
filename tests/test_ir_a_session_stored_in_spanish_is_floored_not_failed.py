"""A row stored in Spanish before shema-api#362 is answered in the room's own language.

`es` left `ROOM_LANGUAGES` in that change, and `create_session` refuses it now, so the only way
to meet one is a tablet that still holds the id of a session opened before. Every place that
tells a model which language the session speaks used to index `LANGUAGE_NAMES` with the
stored value, and a stored `es` was a `KeyError` and a 500 there. The room floors it to the
language it speaks (`floor()`, the setting a fleet held on Portuguese moves), as the voice
already does, and the stored value stays what it was.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.core.config import get_settings
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.sessions import create_session
from app.services.internalization_room.turn import speech
from tests.hearing_harness import nothing_settles, the_transcriber_hears
from tests.release_harness import KEY, PREFIX
from tests.room_harness import room_client, the_room_speaks
from tests.text_seam_harness import ScriptedAgent, the_models_answer
from tests.turn_harness import the_room_agent_is

PANORAMA = "OV-Ruth"
PASSAGE = "P03"
PORTUGUESE = "Noemi voltou para Belém com Rute no tempo da colheita"

FLOORS = [("en", "English"), ("pt", "Brazilian Portuguese")]


@pytest.fixture
def guide(monkeypatch: pytest.MonkeyPatch) -> ScriptedAgent:
    return the_models_answer(monkeypatch)


@pytest.fixture
async def tablet(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, guide: ScriptedAgent
) -> AsyncIterator[httpx.AsyncClient]:
    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=guide)
    nothing_settles(monkeypatch)
    async with room_client(db_session, monkeypatch) as client:
        yield client


def _the_floor_is(monkeypatch: pytest.MonkeyPatch, language: str) -> None:
    monkeypatch.setattr(
        get_settings(), "internalization_room_default_language", language, raising=False
    )


async def _a_row_stored_in_spanish(db_session: AsyncSession, pericope: str) -> IRSession:
    session = await create_session(db_session, language="pt", pericope=pericope)
    session.language = "es"
    await db_session.commit()
    return session


def _the_codes_a_turn_was_given(monkeypatch: pytest.MonkeyPatch, door: Any, name: str) -> list[str]:
    seen: list[str] = []
    real = getattr(door, name)

    async def spy(**kwargs: Any) -> Any:
        seen.append(kwargs["language_code"])
        return await real(**kwargs)

    monkeypatch.setattr(door, name, spy)
    return seen


@pytest.mark.parametrize(("floor", "named"), FLOORS)
async def test_a_panorama_turn_on_a_row_stored_in_spanish_is_told_the_rooms_language(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
    floor: str,
    named: str,
) -> None:
    _the_floor_is(monkeypatch, floor)
    codes = _the_codes_a_turn_was_given(monkeypatch, sessions_api.room, "run_panorama_turn")
    session = await _a_row_stored_in_spanish(db_session, PANORAMA)

    opened = await tablet.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY})

    assert opened.status_code == 200, opened.text
    assert f"**{named}**" in guide.guide_systems[0], (
        "o Guia da panorama de uma sessão guardada em espanhol não era avisado da língua da sala"
    )
    assert codes == [floor], "o código da língua seguia o `es` guardado enquanto o nome era outro"


@pytest.mark.parametrize(("floor", "named"), FLOORS)
async def test_a_passage_turn_on_a_row_stored_in_spanish_is_told_the_rooms_language(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
    floor: str,
    named: str,
) -> None:
    _the_floor_is(monkeypatch, floor)
    codes = _the_codes_a_turn_was_given(monkeypatch, speech, "run_turn")
    the_transcriber_hears(monkeypatch, PORTUGUESE, floor, 0.99)
    session = await _a_row_stored_in_spanish(db_session, PASSAGE)

    answered = await tablet.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("ensaio.m4a", b"audio", "audio/m4a")},
    )

    assert answered.status_code == 200, answered.text
    assert f"**{named}**" in guide.guide_systems[0], (
        "o Guia de uma passagem guardada em espanhol não era avisado da língua da sala"
    )
    assert codes == [floor], "o código da língua seguia o `es` guardado enquanto o nome era outro"


@pytest.mark.parametrize(
    ("floor", "note"),
    [
        ("en", "[The team spoke in their own language"),
        ("pt", "[A equipe falou na língua materna"),
    ],
)
async def test_a_mother_tongue_take_on_a_row_stored_in_spanish_reaches_the_guide_as_the_floors_note(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
    floor: str,
    note: str,
) -> None:
    _the_floor_is(monkeypatch, floor)
    the_transcriber_hears(monkeypatch, "koeti yoko vitukeovo", "ter", 0.9)
    session = await _a_row_stored_in_spanish(db_session, PASSAGE)

    answered = await tablet.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("ensaio.m4a", b"audio", "audio/m4a")},
    )

    assert answered.status_code == 200, answered.text
    assert guide.guide_inputs[0].startswith(note), (
        "a nota da língua materna chegava ao Guia na língua do `es` guardado, não na da sala"
    )
