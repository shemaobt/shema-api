"""A take the room could not hear is kept as «(inaudible)» on the team's side, then her D line.

Her turn route writes the team's side of every turn, and an empty one as «(inaudible)», so the
voice sees on its next turn that the team spoke and was not heard. It is plain team text, not a
room note: her dossier reads it back as an empty transcript.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services import internalization_room as room
from app.services.internalization_room.sessions import create_session
from tests.device_harness import TABLET_TEAM
from tests.hearing_harness import (
    nothing_settles,
    the_take_lasts,
    the_transcriber_hears_no_words,
)
from tests.release_harness import PREFIX
from tests.room_harness import room_client, the_room_speaks
from tests.text_seam_harness import ScriptedAgent, the_models_answer
from tests.turn_harness import P, the_room_agent_is

D_1 = "Desculpa, não consegui ouvir direito — podem repetir?"


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


async def _an_open_session(
    db_session: AsyncSession, tablet: httpx.AsyncClient, pericope: str = P
) -> IRSession:
    session = await create_session(
        db_session, project_id=TABLET_TEAM, language="pt", pericope=pericope
    )
    opened = await tablet.post(f"{PREFIX}/sessions/{session.id}/turns")
    assert opened.status_code == 200, opened.text
    return session


async def _a_silent_take_of_six_seconds(
    tablet: httpx.AsyncClient, session: IRSession, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    the_transcriber_hears_no_words(monkeypatch)
    the_take_lasts(monkeypatch, 6_000)
    answered = await tablet.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        files={"file": ("silencio.m4a", b"audio", "audio/m4a")},
    )
    assert answered.status_code == 200, answered.text
    reply: dict[str, Any] = answered.json()
    return reply


async def _the_last_two_entries(db_session: AsyncSession, session_id: str) -> list[tuple[str, str]]:
    db_session.expire_all()
    stored = await room.get_session(db_session, session_id)
    return [(message["role"], message["text"]) for message in stored.messages[-2:]]


async def test_a_six_second_take_with_no_words_is_kept_as_inaudible_then_her_first_d_line(
    db_session: AsyncSession,
    tablet: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _an_open_session(db_session, tablet)

    reply = await _a_silent_take_of_six_seconds(tablet, session, monkeypatch)

    assert reply["fixed_line"] == "D0"
    assert await _the_last_two_entries(db_session, session.id) == [
        ("team", "(inaudible)"),
        ("guide", D_1),
    ], "o turno perdido não gravava nada do lado da equipe e o Guia nunca via a falha"
