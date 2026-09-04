"""ENG-543 — the inbox names the bead, instead of handing over its identifier.

A card said `being:B3`. A facilitator reads "Noemi". The key is the room's identity for a
bead — coverage is persisted under it and it is unique only inside its passage — and it was
never anything a person was meant to see.

**The key does not travel beside the label.** Measured across the whole of the Desk's `src/`:
`element_key` and `elementKey` appear nowhere. What it has is `elementLabel: string | null`,
rendered straight onto the card. Serving both would put a field on every response that its
only consumer never reads.

**Three languages and not one.** The room negotiates the language it *speaks* — on the
session, and on the wheel that precedes any session — but never the language it *labels* in:
a bead's name is read by a facilitator at the Desk, and the Desk is not the tablet whose
locale the room obeys. `LabelledElement` and the coverage legend both serve `pt`/`en`/`es` as
named fields and let the client choose, and serving a single label here would tie a
facilitator's reading to a team's listening.

The catalogue now holds all fourteen passages, and only four of them — P01, P02, P05, P14 —
are translated. The other ten carry English and two nulls, so **that is the shape most teams
will see**, and it gets a case of its own rather than being left to the pilot's four.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRQuestion, IRQuestionStatus
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

INBOX_URL = "/api/internalization-room/facilitator/questions"

#: A translated passage and a bead in it, written out rather than read from the catalogue the
#: implementation reads. Deriving both from one source would let the two agree while both
#: drifted from what a facilitator sees, and this text **is** what they see.
PILOT = "P01"
PILOT_KEY = "being:B3"
PILOT_PT, PILOT_EN, PILOT_ES = "Noemi", "Naomi", "Noemí"

#: One of the ten. English is filled in and the other two are null for every bead in the
#: passage — the path the pilot's four never take.
UNTRANSLATED = "P06"
UNTRANSLATED_KEY = "being:B13"
UNTRANSLATED_EN = "Boaz"

#: A key of the right shape that the catalogue does not have. It arrives on the wire as a
#: form field and nothing validates it against the canon — by design, since the app is the
#: side that knows which bead the hand went up on — so an app one canon behind sends exactly
#: this.
UNKNOWN_KEY = "being:B99"

A_WHILE = timedelta(minutes=5)
_made = 0


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.internalization_room.questions import router as questions_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(questions_router, prefix="/api/internalization-room")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def a_team(db: AsyncSession, *, name: str):
    global _made
    _made += 1
    language = await make_language(db, name=name, code=f"l{_made % 100:02d}")
    return await make_project(db, language.id, name=name)


async def a_facilitator(db: AsyncSession, *teams, email: str = "facilitadora@example.com"):
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db, email=email)
    for team in teams:
        await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    access, _refresh = await issue_tokens(db, user)
    return user, {"Authorization": f"Bearer {access}"}


async def a_hand(
    db: AsyncSession,
    team,
    *,
    pericope: str,
    element_key: str | None,
    ago: timedelta = A_WHILE,
) -> IRQuestion:
    question = IRQuestion(
        device_id="aparelho",
        session_id="sessao",
        pericope=pericope,
        element_key=element_key,
        audio_key="pergunta.m4a",
        status=IRQuestionStatus.OPEN,
        project_id=team.id,
        created_at=datetime.now(UTC) - ago,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return question


async def read(client, headers) -> dict:
    response = await client.get(INBOX_URL, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def card_of(payload: dict, question_id: str) -> dict:
    found = [c for c in payload["questions"] if c["question_id"] == question_id]
    assert found, f"a pergunta {question_id} nao veio na caixa: {payload}"
    return found[0]


def every_value(card: dict) -> list[str]:
    """Every string the card serves, so a leak cannot hide in a field nobody named."""
    return [str(value) for value in card.values() if value is not None]


@pytest.mark.asyncio
async def test_the_card_names_the_bead_in_the_three_languages(client, db_session):
    """The whole slice, on a passage that has all three."""
    team = await a_team(db_session, name="Equipe do piloto")
    _user, headers = await a_facilitator(db_session, team, email="piloto@example.com")
    hand = await a_hand(db_session, team, pericope=PILOT, element_key=PILOT_KEY)

    card = card_of(await read(client, headers), hand.id)

    assert (card["element_label_pt"], card["element_label_en"], card["element_label_es"]) == (
        PILOT_PT,
        PILOT_EN,
        PILOT_ES,
    ), f"a caixa nao nomeou a conta: {card}"


@pytest.mark.asyncio
async def test_the_raw_key_reaches_no_served_field(client, db_session):
    """The gate against the key coming back, in a new field or in an old one left behind.

    Checked over **every** value the card serves rather than over the field the key used to
    be in: putting it back under another name would be the same defect, and a case naming
    one field would not see it.
    """
    team = await a_team(db_session, name="Equipe sem chave")
    _user, headers = await a_facilitator(db_session, team, email="sem-chave@example.com")
    hand = await a_hand(db_session, team, pericope=PILOT, element_key=PILOT_KEY)

    card = card_of(await read(client, headers), hand.id)

    leaked = [value for value in every_value(card) if PILOT_KEY in value]

    assert leaked == [], f"a chave crua {PILOT_KEY} voltou para o fio: {leaked}"
    assert "element_key" not in card, f"o campo da chave continua servido: {card}"


@pytest.mark.asyncio
async def test_a_passage_outside_the_pilot_serves_english_and_two_nulls(client, db_session):
    """Ten of the fourteen look like this, so this is what most teams will see.

    The pilot's four are complete in all three languages, which means a suite that only ever
    asked about them would be green on a resolver that could not produce a null at all.
    """
    team = await a_team(db_session, name="Equipe das dez")
    _user, headers = await a_facilitator(db_session, team, email="dez@example.com")
    hand = await a_hand(db_session, team, pericope=UNTRANSLATED, element_key=UNTRANSLATED_KEY)

    card = card_of(await read(client, headers), hand.id)

    assert (card["element_label_pt"], card["element_label_en"], card["element_label_es"]) == (
        None,
        UNTRANSLATED_EN,
        None,
    ), f"uma passagem nao traduzida nao saiu com o ingles e dois nulos: {card}"


@pytest.mark.asyncio
async def test_a_key_the_catalogue_does_not_know_costs_the_card_and_not_the_inbox(
    client, db_session
):
    """Where to fail, when the bad value came from outside.

    Failing loudly is right when the defect is ours and silence would bury it. It is wrong
    when the value arrived from another program and the cost lands on somebody else's screen:
    a facilitator with one unreadable card still works, and a facilitator with a broken inbox
    does not.

    The good card sits beside the bad one on purpose. A case with the orphan alone could go
    green on a resolver that gave up on the whole page, which is the failure this is against.
    """
    team = await a_team(db_session, name="Equipe com orfa")
    _user, headers = await a_facilitator(db_session, team, email="orfa@example.com")
    orphan = await a_hand(db_session, team, pericope=PILOT, element_key=UNKNOWN_KEY)
    beside_it = await a_hand(
        db_session, team, pericope=PILOT, element_key=PILOT_KEY, ago=timedelta(minutes=9)
    )

    payload = await read(client, headers)

    orphan_card = card_of(payload, orphan.id)
    good_card = card_of(payload, beside_it.id)

    assert orphan_card["element_label_en"] is None, (
        f"uma chave que o catalogo nao tem nao pode inventar rotulo: {orphan_card}"
    )
    assert good_card["element_label_pt"] == PILOT_PT, (
        f"a chave desconhecida levou o cartao bom junto: {good_card}"
    )


@pytest.mark.asyncio
async def test_a_pericope_the_canon_does_not_have_costs_the_card_and_not_the_inbox(
    client, db_session
):
    """The same rule one level up, and the level that actually raises today.

    An unknown key is a miss in a list. An unknown pericope makes the canon lookup itself
    raise `ValidationError`, so this is the one that takes the whole page down if the
    resolver lets it through — and `pericope` is copied off the session, which is written by
    the room app.
    """
    team = await a_team(db_session, name="Equipe fora do canon")
    _user, headers = await a_facilitator(db_session, team, email="fora@example.com")
    nowhere = await a_hand(db_session, team, pericope="P99", element_key=PILOT_KEY)
    beside_it = await a_hand(
        db_session, team, pericope=PILOT, element_key=PILOT_KEY, ago=timedelta(minutes=9)
    )

    payload = await read(client, headers)

    assert card_of(payload, nowhere.id)["element_label_en"] is None
    assert card_of(payload, beside_it.id)["element_label_pt"] == PILOT_PT, (
        "uma passagem fora do canon levou a caixa inteira"
    )


@pytest.mark.asyncio
async def test_a_hand_raised_on_no_bead_is_named_by_nothing(client, db_session):
    """Every question written before ENG-456, and every app that has not shipped it."""
    team = await a_team(db_session, name="Equipe sem conta")
    _user, headers = await a_facilitator(db_session, team, email="sem-conta@example.com")
    hand = await a_hand(db_session, team, pericope=PILOT, element_key=None)

    card = card_of(await read(client, headers), hand.id)

    assert (card["element_label_pt"], card["element_label_en"], card["element_label_es"]) == (
        None,
        None,
        None,
    ), f"uma pergunta sem conta ganhou rotulo: {card}"
