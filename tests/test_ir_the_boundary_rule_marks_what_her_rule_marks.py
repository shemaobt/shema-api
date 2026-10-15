"""ENG-1351 — the boundary rule marks the turns her rule marks, read through the Desk's door.

Her rule is `isBoundaryTurn` in `src/observe/dossier.ts` at 18fa7c4, and the lines below are
hers from `src/observe/dossierTest.ts` or are written from one pattern of her twelve each.
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
from app.services.internalization_room.sessions import append_exchange
from app.services.internalization_room.validated_turn import TurnOutcome
from tests.baker import grant_room_app_role, make_language, make_project, make_user, open_ir_session

IR = "/api/internalization-room"
P = "P01"
OPENING = "Olá! Vamos começar pela primeira parte."


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
async def session(db_session: AsyncSession) -> IRSession:
    language = await make_language(db_session, name="Lang a", code="la")
    team: Project = await make_project(db_session, language.id, name="Team a")
    return await open_ir_session(db_session, pericope=P, project_id=team.id)


async def _says(
    db: AsyncSession, session: IRSession, guide: str, team: str = "Uma pergunta.", **outcome: Any
) -> IRSession:
    outcome.setdefault("guide_heard", team)
    outcome.setdefault("mother_tongue", False)
    heard = TurnOutcome(speech=guide, transcript=team, **outcome)
    return await append_exchange(
        db, session, team_utterance=team, guide_response=guide, outcome=heard
    )


async def _marked(client: httpx.AsyncClient, headers: dict[str, str], session_id: str) -> list[int]:
    answer = await client.get(
        f"{IR}/facilitator/sessions/{session_id}/boundary-turns", headers=headers
    )
    assert answer.status_code == 200, answer.text
    return [turn["number"] for turn in answer.json()["turns"]]


MARKED = [
    pytest.param("Levem isso para o facilitador.", id="1-para-o-facilitador"),
    pytest.param("Só o facilitador humano sabe isso.", id="2-facilitador-humano"),
    pytest.param("Perguntem à sua consultora.", id="3-sua-consultora"),
    pytest.param("Bring that to your human facilitator.", id="4-your-human-facilitator"),
    pytest.param("Ask your consultant about that.", id="5-your-consultant"),
    pytest.param("A passagem não conta por que veio a fome.", id="6-passagem-nao-conta"),
    pytest.param("O narrador não nos diz isso.", id="7-nao-nos-diz-isso"),
    pytest.param("Isso a história não conta.", id="8-isso-a-historia-nao-conta"),
    pytest.param("A passagem fica em silêncio sobre isso.", id="9-passagem-fica-em-silencio"),
    pytest.param("Aqui não temos como saber.", id="10-nao-temos-como-saber"),
    pytest.param("The story is quiet about that.", id="11-story-is-quiet"),
    pytest.param("That detail doesn't tell us who he was.", id="12-doesnt-tell-us"),
    pytest.param("That's exactly the kind to bring to your facilitator.", id="hers-english"),
    pytest.param("The passage doesn't tell us that.", id="hers-passage-doesnt-tell-us"),
    pytest.param(
        "Essa é uma pergunta boa para levar ao facilitador de vocês.", id="hers-portuguese"
    ),
    pytest.param("Perguntem ao seu facilitador.", id="hers-seu-facilitador"),
    pytest.param("Isso é para o facilitador humano da equipe.", id="hers-facilitador-humano"),
    pytest.param(
        "Como Facilitador Digital não sei; levem isso ao facilitador de vocês.",
        id="hers-self-name-and-a-real-hand-off",
    ),
]

NOT_MARKED = [
    pytest.param(
        "Elimeleque saiu de Belém com a mulher e os dois filhos.", id="hers-an-ordinary-line"
    ),
    pytest.param(
        "Como Facilitador Digital, eu só sigo este documento.", id="hers-the-self-name-alone"
    ),
    pytest.param("Um bom facilitador escuta primeiro.", id="hers-the-bare-word"),
    pytest.param("Eu sou o seu Facilitador Digital. O que vem depois?", id="seu-self-name"),
    pytest.param("Sou a sua Facilitadora Digital e vou ouvir vocês.", id="sua-self-name"),
    pytest.param("I am your Digital Facilitator.", id="your-self-name"),
]


@pytest.mark.parametrize("guide", MARKED)
async def test_a_line_her_rule_hands_to_the_facilitator_or_names_the_silence_of_is_marked(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
    guide: str,
) -> None:
    session = await append_exchange(db_session, session, team_utterance="", guide_response=OPENING)
    session = await _says(db_session, session, guide)

    assert await _marked(client, consultant, session.id) == [1]


@pytest.mark.parametrize("guide", NOT_MARKED)
async def test_a_line_that_only_names_the_guide_or_tells_the_passage_is_not_marked(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
    guide: str,
) -> None:
    session = await append_exchange(db_session, session, team_utterance="", guide_response=OPENING)
    session = await _says(db_session, session, guide)

    assert await _marked(client, consultant, session.id) == []


@pytest.mark.parametrize(
    "opening",
    [
        pytest.param(
            "Olá! Eu sou o Facilitador Digital. Hoje vamos olhar Rute 1:1-5 juntos.",
            id="hers-portuguese-introduction",
        ),
        pytest.param(
            "Hello! I am the Digital Facilitator. Today we look at Ruth 1:1-5 together.",
            id="hers-english-introduction",
        ),
        pytest.param(
            "Se surgir dúvida, levem ao facilitador de vocês.", id="hers-a-hand-off-in-the-opening"
        ),
    ],
)
async def test_the_opening_is_never_marked_on_its_words_alone(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
    opening: str,
) -> None:
    session = await append_exchange(db_session, session, team_utterance="", guide_response=opening)

    assert await _marked(client, consultant, session.id) == []


async def test_a_fail_safe_is_marked_whatever_it_says_and_the_opening_that_fell_to_one_too(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    fell = TurnOutcome(
        speech="Desculpa, podem repetir?", transcript="", used_fail_safe=True, fixed_line="A1"
    )
    session = await append_exchange(
        db_session,
        session,
        team_utterance="",
        guide_response="Desculpa, podem repetir?",
        outcome=fell,
    )
    session = await _says(
        db_session, session, "Vamos com calma.", used_fail_safe=True, fixed_line="A1"
    )

    assert await _marked(client, consultant, session.id) == [0, 1]


async def test_a_turn_on_the_mother_tongue_is_not_marked_for_the_team_having_spoken_it(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    note = (
        "[A equipe falou na língua materna por cerca de 40 segundos; sem transcrição — "
        "nenhuma palavra chegou até você.]"
    )
    session = await append_exchange(db_session, session, team_utterance="", guide_response=OPENING)
    session = await _says(
        db_session,
        session,
        "Que bom que ensaiaram entre vocês. Me contem em português o que disseram.",
        team="",
        guide_heard=note,
        mother_tongue=True,
        room_note=note,
    )

    assert await _marked(client, consultant, session.id) == []
