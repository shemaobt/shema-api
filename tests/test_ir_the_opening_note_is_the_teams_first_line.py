from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import create_session, get_session
from tests.device_harness import TABLET_TEAM
from tests.opening_harness import GUIDE_OPENING, NOTE_PT_P01, a_scripted_room, ask_for_the_opening
from tests.release_harness import PREFIX
from tests.room_harness import room_client
from tests.tablet_turn_harness import the_turn_is_scripted


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


async def test_the_voice_hears_her_note_as_the_teams_turn_before_its_own_opening(
    db_session: AsyncSession, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    conversations: list[Any] = []

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Noemi voltou para Belém")

    async def model(*, system_prompt: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        conversations.append(kwargs.get("conversation"))
        return GUIDE_OPENING

    the_turn_is_scripted(monkeypatch, heard=heard, model=model)
    session = await create_session(
        db_session, project_id=TABLET_TEAM, pericope="P01", language="pt"
    )
    await ask_for_the_opening(client, session.id)

    spoken = await client.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        data={"turn_id": "fala"},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )

    assert spoken.status_code == 200, spoken.text[:300]
    assert conversations[0] == []
    assert conversations[1] == [
        {"role": "user", "text": NOTE_PT_P01},
        {"role": "assistant", "text": GUIDE_OPENING},
    ], "a segunda fala da equipe chegava à voz sem a nota que a fez abrir"
