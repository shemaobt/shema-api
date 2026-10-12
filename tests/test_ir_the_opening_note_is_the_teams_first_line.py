from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.sessions import create_session, get_session
from tests.device_harness import TABLET_TEAM
from tests.opening_harness import GUIDE_OPENING, NOTE_PT_P01, a_scripted_room, ask_for_the_opening
from tests.room_harness import room_client


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    async with room_client(db_session, monkeypatch) as c:
        yield c


async def _the_stored_conversation(db_session: AsyncSession, session_id: str):
    session = await get_session(db_session, session_id)
    await db_session.refresh(session)
    return [(message["role"], message["text"]) for message in session.messages or []]


async def test_a_portuguese_passage_opens_with_her_note_as_the_teams_first_line(
    db_session: AsyncSession, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_scripted_room(monkeypatch)
    session = await create_session(
        db_session, project_id=TABLET_TEAM, pericope="P01", language="pt"
    )

    opened = await ask_for_the_opening(client, session.id)

    assert opened.status_code == 200, opened.text[:300]
    assert await _the_stored_conversation(db_session, session.id) == [
        ("team", NOTE_PT_P01),
        ("guide", GUIDE_OPENING),
    ], "a transcrição abria com a fala da voz e ninguém via por que ela falou primeiro"


async def test_a_portuguese_panorama_opens_with_her_panorama_note_as_the_teams_first_line(
    db_session: AsyncSession, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_scripted_room(monkeypatch)
    session = await create_session(
        db_session, project_id=TABLET_TEAM, pericope="OV-Ruth", language="pt"
    )

    opened = await ask_for_the_opening(client, session.id)

    assert opened.status_code == 200, opened.text[:300]
    assert await _the_stored_conversation(db_session, session.id) == [
        (
            "team",
            "[A sessão acabou de começar. A equipe abriu o Panorama do Livro de Ruth e está à "
            "mesa, pronta para conversar. Fale primeiro.]",
        ),
        ("guide", GUIDE_OPENING),
    ], "o Panorama guardava a nota de uma passagem, 'abriu a passagem OV-Ruth'"


async def test_an_english_passage_stores_her_english_note_not_the_portuguese_one(
    db_session: AsyncSession, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_scripted_room(monkeypatch)
    session = await create_session(
        db_session, project_id=TABLET_TEAM, pericope="P01", language="en"
    )

    opened = await ask_for_the_opening(client, session.id)

    assert opened.status_code == 200, opened.text[:300]
    assert await _the_stored_conversation(db_session, session.id) == [
        (
            "team",
            "[The session has just begun. The team opened passage P01 and is at the table, "
            "ready to begin. Speak first.]",
        ),
        ("guide", GUIDE_OPENING),
    ], "uma sessão em inglês guardava a nota em português"
