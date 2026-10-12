"""A row stored in Spanish before shema-api#362 is answered in the room's own language.

`es` left `ROOM_LANGUAGES` in that change, and `create_session` refuses it now, so the only way
to meet one is a tablet that still holds the id of a session opened before. Every place that
tells a model which language the session speaks used to index `LANGUAGE_NAMES` with the
stored value, and a stored `es` was a `KeyError` and a 500 there. The room floors it to the
language it speaks (`floor()`, the setting a fleet held on Portuguese moves), as the voice
already does, and the stored value stays what it was.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.core.config import get_settings
from app.db.models.internalization_room import IRSession
from app.services.internalization_room import (
    back_translation_of,
    background,
    check_the_telling_back,
    verdict_round,
)
from app.services.internalization_room.canon.labels import labelled_elements
from app.services.internalization_room.sessions import create_session, get_session
from app.services.internalization_room.turn import speech
from tests.device_harness import TABLET_TEAM
from tests.hearing_harness import (
    nothing_settles,
    the_take_lasts,
    the_transcriber_hears,
    the_transcriber_hears_no_words,
)
from tests.release_harness import PREFIX
from tests.room_harness import (
    heard_every_part,
    press_terminei,
    rehearsed_in_parts,
    rehearsed_in_parts_of,
    room_client,
    the_analyst_is_scripted,
    the_room_speaks,
)
from tests.text_seam_harness import ScriptedAgent, the_models_answer
from tests.turn_harness import NOTHING_TOLD_BACK, settings, the_room_agent_is, told_stretches

PANORAMA = "OV-Ruth"
PASSAGE = "P03"
TITLED = "P02"
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
    session = await create_session(
        db_session, project_id=TABLET_TEAM, language="pt", pericope=pericope
    )
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

    opened = await tablet.post(f"{PREFIX}/sessions/{session.id}/turns")

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
        files={"file": ("ensaio.m4a", b"audio", "audio/m4a")},
    )

    assert answered.status_code == 200, answered.text
    assert guide.guide_inputs[0].startswith(note), (
        "a nota da língua materna chegava ao Guia na língua do `es` guardado, não na da sala"
    )


async def test_a_take_in_the_floors_language_on_a_row_stored_in_spanish_is_the_teams_answer(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    guide: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _the_floor_is(monkeypatch, "pt")
    the_transcriber_hears(monkeypatch, PORTUGUESE, "pt", 0.99)
    session = await _a_row_stored_in_spanish(db_session, PASSAGE)

    for _ in range(2):
        answered = await tablet.post(
            f"{PREFIX}/sessions/{session.id}/turns",
            files={"file": ("ensaio.m4a", b"audio", "audio/m4a")},
        )
        assert answered.status_code == 200, answered.text

    assert guide.guide_inputs == [PORTUGUESE, PORTUGUESE], (
        "o português de uma sessão guardada em espanhol era lido como língua materna da equipe"
    )


class _Models:
    def __init__(self) -> None:
        self.analyst: list[str] = []
        self.validator: list[str] = []

    async def turn(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        return "Contem de novo, por favor."

    async def reads(self, *, system_prompt: str, **_: Any) -> str:
        self.analyst.append(system_prompt)
        return json.dumps({"findings": []})


@pytest.fixture
def models(monkeypatch: pytest.MonkeyPatch) -> _Models:
    seen = _Models()
    the_room_agent_is(monkeypatch, turn=seen.turn, analyst=seen.reads)
    return seen


def _a_telling_back_on_a_row_stored_in_spanish() -> IRSession:
    return IRSession(id="sessao-es", pericope=PASSAGE, project_id="equipe", language="es")


@pytest.mark.parametrize(("floor", "named"), FLOORS)
async def test_the_analyst_reads_a_telling_back_on_a_row_stored_in_spanish_in_the_rooms_language(
    models: _Models, monkeypatch: pytest.MonkeyPatch, floor: str, named: str
) -> None:
    _the_floor_is(monkeypatch, floor)
    codes = _the_codes_a_turn_was_given(monkeypatch, verdict_round, "analyse_telling_back")
    session = _a_telling_back_on_a_row_stored_in_spanish()

    await check_the_telling_back(
        session,
        state=back_translation_of(session),
        told=told_stretches(),
        takes=[],
        settings=settings(),
    )

    assert named in models.analyst[0], (
        "o analista lia a recontagem de uma sessão guardada em espanhol sem a língua da sala"
    )
    assert codes == [floor], "o código da língua seguia o `es` guardado enquanto o nome era outro"


@pytest.mark.parametrize(("floor", "named"), FLOORS)
async def test_the_verdict_on_a_row_stored_in_spanish_is_judged_in_the_rooms_language(
    models: _Models, monkeypatch: pytest.MonkeyPatch, floor: str, named: str
) -> None:
    _the_floor_is(monkeypatch, floor)
    codes = _the_codes_a_turn_was_given(monkeypatch, verdict_round, "run_verdict_turn")
    session = _a_telling_back_on_a_row_stored_in_spanish()

    await check_the_telling_back(
        session,
        state=back_translation_of(session),
        told=[],
        takes=[],
        settings=settings(),
    )

    assert f"**{named}**" in models.validator[0], (
        "o Validador do veredito de uma sessão guardada em espanhol não lia a língua da sala"
    )
    assert codes == [floor], "o código da língua seguia o `es` guardado enquanto o nome era outro"


@asynccontextmanager
async def _handed(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield db_session


@pytest.mark.parametrize(("floor", "named"), FLOORS)
async def test_the_coverage_of_a_row_stored_in_spanish_is_classified_in_the_rooms_language(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, floor: str, named: str
) -> None:
    _the_floor_is(monkeypatch, floor)
    read: list[str] = []

    async def classifier(*, system_prompt: str, **_: Any) -> str:
        read.append(system_prompt)
        return json.dumps({"decisions": []})

    the_room_agent_is(monkeypatch, classifier=classifier)
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    session = await _a_row_stored_in_spanish(db_session, PASSAGE)

    await background.settle_coverage(
        session_id=session.id,
        turn_id="turno-1",
        team_utterance=PORTUGUESE,
        guide_response="Conte de novo, por favor.",
        pericope_num=PASSAGE,
    )

    assert read
    assert all(named in system for system in read), (
        "o classificador de uma sessão guardada em espanhol não lia a troca na língua da sala"
    )


@pytest.mark.parametrize(("floor", "named"), FLOORS)
async def test_the_reading_ahead_of_a_row_stored_in_spanish_is_read_in_the_rooms_language(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, floor: str, named: str
) -> None:
    _the_floor_is(monkeypatch, floor)
    analyst = the_analyst_is_scripted(monkeypatch)
    codes = _the_codes_a_turn_was_given(monkeypatch, background, "analyse_telling_back")
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    session, _ = await rehearsed_in_parts(db_session, 1)
    session.language = "es"
    await db_session.commit()

    await background.read_ahead(session_id=session.id)

    assert analyst.shown
    assert all(named in system for system in analyst.shown), (
        "a leitura antecipada de uma sessão guardada em espanhol falhava em silêncio"
    )
    assert codes == [floor], "o código da língua seguia o `es` guardado enquanto o nome era outro"


@pytest.mark.parametrize("floor", ["en", "pt"])
async def test_the_note_a_verdict_keeps_on_a_row_stored_in_spanish_is_in_the_rooms_language(
    models: _Models, monkeypatch: pytest.MonkeyPatch, floor: str
) -> None:
    _the_floor_is(monkeypatch, floor)
    session = _a_telling_back_on_a_row_stored_in_spanish()

    verdict = await check_the_telling_back(
        session,
        state=back_translation_of(session),
        told=[],
        takes=[],
        settings=settings(),
    )

    assert verdict.told_back == NOTHING_TOLD_BACK[floor], (
        "o registro do veredito guardava a nota em inglês para uma sessão guardada em espanhol"
    )


def _scene_title(pericope: str, scene: int, language: str) -> str | None:
    for element in labelled_elements(pericope):
        if element.key == f"scene:{scene}":
            return element.label_pt if language == "pt" else element.label_en
    return None


@pytest.mark.parametrize(("floor", "part"), [("en", "part 2"), ("pt", "a parte 2")])
async def test_a_part_is_named_in_the_rooms_language_on_a_row_stored_in_spanish(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, floor: str, part: str
) -> None:
    _the_floor_is(monkeypatch, floor)
    analyst = the_analyst_is_scripted(monkeypatch)
    room = the_room_speaks(monkeypatch)
    session, _ = await rehearsed_in_parts_of(db_session, [3, 4, 2], pericope=TITLED)
    session.language = "es"
    await db_session.commit()
    analyst.readings = [
        {"findings": [{"kind": "addition", "note": "o pedido das noras", "chunk": 5}]}
    ]

    async with room_client(db_session, monkeypatch) as door:
        pressed = await press_terminei(
            door, session.id, report=await heard_every_part(db_session, session.id)
        )

    assert pressed.status_code == 200, pressed.text
    assert f"{part} — {_scene_title(TITLED, 2, floor)}" in room.briefs[-1], (
        "o veredito de uma sessão guardada em espanhol nomeava a parte na língua errada"
    )


@pytest.mark.parametrize(
    ("floor", "line"),
    [
        ("en", "Sorry, I didn't quite catch that — could you say it again?"),
        ("pt", "Desculpa, não consegui ouvir direito — podem repetir?"),
    ],
)
async def test_a_miss_on_a_row_stored_in_spanish_is_kept_in_the_rooms_language(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    floor: str,
    line: str,
) -> None:
    _the_floor_is(monkeypatch, floor)
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, 3_000)
    session_id = (await _a_row_stored_in_spanish(db_session, PASSAGE)).id

    answered = await tablet.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        files={"file": ("ensaio.m4a", b"audio", "audio/m4a")},
    )

    assert answered.status_code == 200, answered.text
    db_session.expire_all()
    kept = (await get_session(db_session, session_id)).messages
    assert [message["text"] for message in kept if message["role"] == "guide"] == [line], (
        "a conversa guardava a fala de um toque perdido na língua do `es` guardado"
    )
