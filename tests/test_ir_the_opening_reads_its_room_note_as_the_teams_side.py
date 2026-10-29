"""ENG-2016 — the turns route serves the Opening's Room note as the team's side of turn 0.

Every case reads the real turns route, on sessions written by the room's own writer or stored
in the shape that predates notes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.db.models.project import Project
from app.main import app
from app.services.internalization_room.sessions import append_exchange
from app.services.internalization_room.validated_turn import TurnOutcome
from tests.baker import (
    grant_room_app_role,
    make_language,
    make_project,
    make_user,
    open_ir_session,
)

IR = "/api/internalization-room"
P = "P01"


@pytest.fixture()
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    from app.core.database import get_db
    from app.main import app

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
async def consultant(db_session: AsyncSession) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db_session, email="abertura@example.com")
    await grant_room_app_role(db_session, user.id, "consultant")
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


@pytest.fixture()
async def team(db_session: AsyncSession) -> Project:
    language = await make_language(db_session, name="Lang a", code="la")
    return await make_project(db_session, language.id, name="Team a")


@pytest.fixture()
async def session(db_session: AsyncSession, team: Project) -> IRSession:
    return await open_ir_session(db_session, pericope=P, project_id=team.id)


async def _turn(
    db: AsyncSession, session: IRSession, team: str, guide: str, **outcome: Any
) -> IRSession:
    outcome.setdefault("guide_heard", team)
    outcome.setdefault("mother_tongue", False)
    heard = TurnOutcome(speech=guide, transcript=team, **outcome)
    return await append_exchange(
        db, session, team_utterance=team, guide_response=guide, outcome=heard
    )


NOTE = (
    "[A sessão acabou de começar. A equipe abriu a passagem P01 e está à mesa, "
    "pronta para começar. Fale primeiro.]"
)
OPENING = "Vamos ouvir a história de Rute. O que vocês já sabem dela?"
SIX_KEYS = {
    "language",
    "language_probability",
    "take_ms",
    "mother_tongue",
    "interrupted_at_s",
    "guide_heard",
}


async def _opened(db: AsyncSession, session: IRSession) -> IRSession:
    return await append_exchange(
        db, session, team_utterance="", guide_response=OPENING, opening_note=NOTE
    )


async def _read(
    client: httpx.AsyncClient, consultant: dict[str, str], session: IRSession
) -> list[dict[str, Any]]:
    answer = await client.get(f"{IR}/facilitator/sessions/{session.id}/turns", headers=consultant)
    assert answer.status_code == 200, answer.text
    return answer.json()["turns"]


def _the_openings_team_side(words: str) -> dict[str, Any]:
    return {
        "language": None,
        "language_probability": None,
        "take_ms": None,
        "mother_tongue": None,
        "interrupted_at_s": None,
        "guide_heard": words,
        "note_kind": "opening",
    }


async def test_an_opening_that_kept_its_opening_note_reads_that_note_as_the_teams_side_marked_as_the_opening_note(  # noqa: E501
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session = await _opened(db_session, session)

    turns = await _read(client, consultant, session)

    assert turns[0]["team"] == _the_openings_team_side(NOTE)


async def test_an_opening_stored_before_notes_were_kept_reads_a_team_side_with_no_words_still_marked_as_the_opening_note(  # noqa: E501
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session.messages = [
        {"role": "guide", "text": "Abertura antiga.", "at": "2026-09-01T12:00:00+00:00"}
    ]
    await db_session.commit()

    turns = await _read(client, consultant, session)

    assert turns[0]["team"] == _the_openings_team_side("")


async def test_the_turns_after_the_opening_carry_no_opening_note_mark(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session = await _opened(db_session, session)
    session = await _turn(
        db_session, session, "Noemi voltou para Belém com Rute", "E depois disso, o que aconteceu?"
    )

    turns = await _read(client, consultant, session)

    assert set(turns[1]["team"]) == SIX_KEYS
    assert turns[1]["team"]["guide_heard"] == "Noemi voltou para Belém com Rute"


def test_the_api_reference_documents_the_teams_side_with_the_opening_note_mark() -> None:
    served = app.openapi()["components"]["schemas"]["TurnTeamSide"]["properties"]

    assert set(served) == SIX_KEYS | {"note_kind"}
