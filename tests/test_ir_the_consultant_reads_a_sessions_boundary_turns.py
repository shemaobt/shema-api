"""ENG-1351 — the consultant reads the turns of a session that the boundary rule marks.

Every case drives the real application through the door the Desk reads by, with the session's
turns written by the writer the room itself uses.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.db.models.project import Project
from app.services.internalization_room.sessions import append_exchange, create_session
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

    user = await make_user(db_session, email="consultora@example.com")
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


async def _opening(db: AsyncSession, session: IRSession, guide: str) -> IRSession:
    return await append_exchange(db, session, team_utterance="", guide_response=guide)


async def _turn(
    db: AsyncSession, session: IRSession, team: str, guide: str, **outcome: Any
) -> IRSession:
    outcome.setdefault("guide_heard", team)
    outcome.setdefault("mother_tongue", False)
    heard = TurnOutcome(speech=guide, transcript=team, **outcome)
    return await append_exchange(
        db, session, team_utterance=team, guide_response=guide, outcome=heard
    )


async def _boundary_turns(
    client: httpx.AsyncClient, headers: dict[str, str], session_id: str
) -> dict[str, Any]:
    answer = await client.get(
        f"{IR}/facilitator/sessions/{session_id}/boundary-turns", headers=headers
    )
    assert answer.status_code == 200, answer.text
    return answer.json()


async def test_a_session_with_no_boundary_turn_reads_an_empty_list_that_is_still_there(
    client: httpx.AsyncClient, consultant: dict[str, str], session: IRSession
) -> None:
    body = await _boundary_turns(client, consultant, session.id)

    assert body == {"session_id": session.id, "count": 0, "turns": []}


async def test_two_marked_turns_among_ordinary_ones_read_as_a_count_of_two_oldest_first(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session = await _opening(db_session, session, "Olá! Vamos começar pela primeira parte.")
    session = await _turn(
        db_session, session, "Foi Deus que mandou a fome?", "Perguntem ao seu facilitador."
    )
    session = await _turn(
        db_session,
        session,
        "Quem saiu de Belém?",
        "Elimeleque saiu de Belém com a mulher e os dois filhos.",
    )
    session = await _turn(
        db_session,
        session,
        "",
        "Desculpa, não consegui ouvir direito. Podem repetir?",
        used_fail_safe=True,
        fixed_line="D1",
    )

    body = await _boundary_turns(client, consultant, session.id)

    assert body["count"] == 2
    assert [turn["number"] for turn in body["turns"]] == [1, 3]


async def test_a_marked_turn_is_listed_with_how_containment_ended_and_the_line_the_guide_voiced(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session = await _opening(
        db_session, session, "Olá! Eu sou o Facilitador Digital. Vamos começar pela primeira parte."
    )
    session = await _turn(
        db_session,
        session,
        "Foi Deus que mandou a fome?",
        "A passagem não conta por que veio a fome. Ela só diz que houve fome na terra.",
        verdict="correct",
    )
    session = await _turn(
        db_session,
        session,
        "",
        "Desculpa, não consegui ouvir direito, podem repetir?",
        used_fail_safe=True,
        fixed_line="D1",
    )
    session = await _turn(
        db_session,
        session,
        "E Rute casou com quem?",
        "Essa é uma pergunta boa para levar ao facilitador de vocês.",
    )

    body = await _boundary_turns(client, consultant, session.id)

    assert [(turn["number"], turn["outcome"], turn["guide"]) for turn in body["turns"]] == [
        (
            1,
            "corrected",
            "A passagem não conta por que veio a fome. Ela só diz que houve fome na terra.",
        ),
        (2, "fail_safe", "Desculpa, não consegui ouvir direito, podem repetir?"),
        (3, "validated", "Essa é uma pergunta boa para levar ao facilitador de vocês."),
    ]


async def test_a_listed_turn_carries_the_team_words_as_the_guide_was_handed_them(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    fail_safe = {"used_fail_safe": True, "fixed_line": "A1"}
    cut = "[A equipe interrompeu a sua fala anterior neste ponto.] Espera — a Noemi ficou?"
    mother_tongue = (
        "[A equipe falou na língua materna por cerca de 40 segundos; sem transcrição — "
        "nenhuma palavra chegou até você.]"
    )
    session = await _opening(db_session, session, "Olá! Vamos começar.")
    session = await _turn(db_session, session, "E Rute casou com quem?", "Um.", **fail_safe)
    session = await _turn(
        db_session, session, "Espera — a Noemi ficou?", "Dois.", guide_heard=cut, **fail_safe
    )
    session = await _turn(
        db_session,
        session,
        "",
        "Três.",
        guide_heard=mother_tongue,
        mother_tongue=True,
        **fail_safe,
    )
    session = await _turn(db_session, session, "", "Quatro.", fixed_line="D1", used_fail_safe=True)

    body = await _boundary_turns(client, consultant, session.id)

    assert [turn["team"] for turn in body["turns"]] == [
        "E Rute casou com quem?",
        cut,
        mother_tongue,
        "",
    ]


async def test_each_listed_turn_is_found_in_the_turns_read_at_its_number_and_no_other_is_marked(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session = await _opening(db_session, session, "Olá! Eu sou o Facilitador Digital.")
    session = await _turn(db_session, session, "Quem saiu?", "Elimeleque saiu de Belém.")
    session = await _turn(
        db_session, session, "Por quê?", "A passagem não conta por que veio a fome."
    )
    session = await _turn(db_session, session, "E depois?", "Eles foram para Moabe.")
    session = await _turn(db_session, session, "", "Podem repetir?", used_fail_safe=True)
    session = await _turn(db_session, session, "Quem sabe?", "Perguntem ao seu facilitador.")

    body = await _boundary_turns(client, consultant, session.id)
    read = await client.get(f"{IR}/facilitator/sessions/{session.id}/turns", headers=consultant)
    turns = read.json()["turns"]

    assert body["count"] == 3
    assert [turns[turn["number"]]["voice"]["text"] for turn in body["turns"]] == [
        turn["guide"] for turn in body["turns"]
    ]
    assert [number for number, turn in enumerate(turns) if turn["voice"]["boundary"]] == [
        turn["number"] for turn in body["turns"]
    ]


async def test_a_telling_back_verdict_and_the_notes_are_never_listed_nor_shift_a_number(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session = await append_exchange(
        db_session,
        session,
        team_utterance="",
        guide_response="Olá! Vamos começar.",
        opening_note="[A equipe abriu a passagem; levem a dúvida ao seu facilitador.]",
    )
    session = await _turn(
        db_session,
        session,
        "Quem saiu?",
        "Elimeleque saiu de Belém.",
        room_note="[A equipe interrompeu a fala; a passagem não conta isso, seu facilitador sabe.]",
    )
    session = await append_exchange(
        db_session,
        session,
        team_utterance="",
        guide_response="A passagem não conta isso. Perguntem ao seu facilitador.",
        told_back="a telling",
    )
    session = await _turn(db_session, session, "Quem sabe?", "Perguntem ao seu facilitador.")

    body = await _boundary_turns(client, consultant, session.id)

    assert body["count"] == 1
    assert [turn["number"] for turn in body["turns"]] == [2]


async def test_a_panorama_reads_its_boundary_turns_like_any_passage_and_one_with_no_turn_reads_none(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    team: Project,
    db_session: AsyncSession,
) -> None:
    panorama = await create_session(db_session, pericope="OV-Ruth", project_id=team.id)
    assert (await _boundary_turns(client, consultant, panorama.id))["count"] == 0

    panorama = await _opening(db_session, panorama, "Olá! Vamos olhar o livro todo.")
    panorama = await _turn(
        db_session, panorama, "E o fim do livro?", "O livro não nos conta isso agora."
    )

    body = await _boundary_turns(client, consultant, panorama.id)

    assert body["count"] == 1
    assert [turn["number"] for turn in body["turns"]] == [1]


KICKOFF = (
    "[A sess\xe3o acabou de come\xe7ar. A equipe abriu a passagem P01 e est\xe1 \xe0 mesa, "
    "pronta para come\xe7ar. Fale primeiro.]"
)


async def _fail_safed_opening(
    db: AsyncSession, session: IRSession, *, opening_note: str
) -> IRSession:
    fell = TurnOutcome(
        speech="Desculpa, podem repetir?", transcript="", used_fail_safe=True, fixed_line="A1"
    )
    return await append_exchange(
        db,
        session,
        team_utterance="",
        guide_response="Desculpa, podem repetir?",
        outcome=fell,
        opening_note=opening_note,
    )


async def test_a_fail_safed_opening_lists_her_kickoff_note_as_the_team_words(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session = await _fail_safed_opening(db_session, session, opening_note=KICKOFF)

    body = await _boundary_turns(client, consultant, session.id)

    assert [(turn["number"], turn["outcome"], turn["team"]) for turn in body["turns"]] == [
        (0, "fail_safe", KICKOFF)
    ]


async def test_a_fail_safed_opening_with_no_stored_kickoff_note_lists_no_team_words(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session = await _fail_safed_opening(db_session, session, opening_note="")

    body = await _boundary_turns(client, consultant, session.id)

    assert [turn["team"] for turn in body["turns"]] == [""]
