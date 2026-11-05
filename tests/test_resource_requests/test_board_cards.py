"""The Painel's cards in one read: ``GET /requests/board`` (OBT-667, RRF-MESA-084).

The Painel read ``GET /requests`` for the spine and then ``GET /requests/{id}`` once per card for
the five answers the card draws — 73 cards, 73 calls on the 29/out bench. The route answers the
same five for every card at once, so what is pinned here is: who reads it (the Painel's own door,
``manage_funds``), that the shape is closed, that the fund keeps ``RequestOut``'s rule, that it
stays two statements however many cards there are, that a missing answer is ``""`` and not a
missing card, and that ``board`` is never taken for a request id.

No test here uses a platform-admin account, for ``test_evaluations.py``'s reason: an admin
passes every guard and a refusal written with one passes for the wrong reason.
"""

from __future__ import annotations

from decimal import Decimal

import pydantic
import pytest
from sqlalchemy import event, select

from app.db.models.resource_request import RRCurrency, RRRequest, RRRequestSections, RRStage
from app.main import app
from app.models.resource_request import BoardCardOut
from app.services.resource_request.list_board_cards import BoardCard
from tests.resource_request_harness import (
    REQUESTS,
    as_admin,
    as_gestor,
    as_mesa,
    as_team,
    create,
    draft,
    give_fund,
)

BOARD = "/api/resource-requests/requests/board"

#: The wire shape of one card — closed, so a column reaching the Painel by accident fails here.
CARD_KEYS = {
    "id",
    "stage",
    "fund_id",
    "reg_name",
    "tpp_name",
    "lang_name",
    "people_name",
    "amount_requested",
    "currency",
}


async def board(client, headers) -> dict[str, dict]:
    res = await client.get(BOARD, headers=headers)
    assert res.status_code == 200, res.text
    return {card["id"]: card for card in res.json()}


# ——— who reads it ———————————————————————————————————————————————————————————————


async def test_the_mesa_and_the_gestor_read_every_card_and_the_team_reads_none(
    db_session, client, rrf_app
) -> None:
    """The Painel's door is ``manage_funds``: the mesa and the Gestor (and the Admin on the
    Gestor's line) read the board; the team, which has no Painel, is refused with 403 and the
    refusal names no request."""
    team = await as_team(db_session, rrf_app)
    created = await create(client, team)

    for headers in (
        await as_mesa(db_session, rrf_app),
        await as_gestor(db_session, rrf_app),
        await as_admin(db_session, rrf_app),
    ):
        assert created["id"] in await board(client, headers)

    refused = await client.get(BOARD, headers=team)
    assert refused.status_code == 403
    assert created["id"] not in refused.text


async def test_without_a_session_the_board_is_401(client) -> None:
    assert (await client.get(BOARD)).status_code == 401


# ——— the shape ———————————————————————————————————————————————————————————————————


async def test_a_card_carries_the_five_answers_the_painel_draws_and_nothing_else(
    db_session, client, rrf_app
) -> None:
    """Name, solicitante, language, people and amount — read off the document the mesa already
    reads by ``GET /requests/{id}`` — plus the column, the currency and the fund; no evaluation."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    sent = draft()
    sent["fields"]["reg_name"] = "Projeto Xerente"
    sent["fields"]["tpp_name"] = "Ana Ponto Focal"
    sent["fields"]["lang_name"] = "Xerente"
    sent["fields"]["people_name"] = "Akwẽ"
    created = await create(client, team, **sent)
    await give_fund(db_session, created["id"])

    card = (await board(client, mesa))[created["id"]]
    own = (await client.get(f"{REQUESTS}/{created['id']}", headers=mesa)).json()

    assert set(card) == CARD_KEYS
    assert card["reg_name"] == own["document"]["fields"]["reg_name"] == "Projeto Xerente"
    assert card["tpp_name"] == own["document"]["fields"]["tpp_name"] == "Ana Ponto Focal"
    assert card["lang_name"] == own["document"]["fields"]["lang_name"] == "Xerente"
    assert card["people_name"] == own["document"]["fields"]["people_name"] == "Akwẽ"
    assert Decimal(card["amount_requested"]) == Decimal(
        own["document"]["fields"]["amount_requested"]
    )
    assert card["currency"] == own["document"]["currency"] == "BRL"
    assert card["stage"] == own["stage"] == "triagem"
    assert card["fund_id"] == own["fund_id"] == "linguas"


def test_the_shape_is_closed() -> None:
    """``extra="forbid"`` is the guard that holds when a later change tries to widen it.

    The payload is valid on its own first, so the extra key is the **only** thing wrong with
    it — a currency outside ``RRCurrency`` would have refused the payload before the key got
    to speak, and the test would stay green with the guard removed (review of #1014)."""
    card = {
        "id": "r",
        "stage": "triagem",
        "reg_name": "",
        "tpp_name": "",
        "lang_name": "",
        "people_name": "",
        "amount_requested": None,
        "currency": "BRL",
    }
    BoardCardOut.model_validate(card)

    with pytest.raises(pydantic.ValidationError, match="total"):
        BoardCardOut.model_validate({**card, "total": 30})


def test_the_fund_is_absent_from_a_caller_who_may_not_read_it() -> None:
    """``RequestOut``'s rule, kept on the shape: the route's guard makes every caller a reader of
    the fund today, so this is proven where the rule lives — a route that reuses the shape for a
    narrower reader gets the absence, not a ``null`` that looks like *no fund*."""
    request = RRRequest(
        id="r",
        stage=RRStage.TRIAGEM,
        currency=RRCurrency.BRL,
        reg_name="A",
        tpp_name="B",
        fund_id="linguas",
    )
    card = BoardCard(request, "Xerente", "Akwẽ")

    with_fund = BoardCardOut.of(card, reads_funds=True).model_dump()
    without = BoardCardOut.of(card, reads_funds=False).model_dump()

    assert with_fund["fund_id"] == "linguas"
    assert "fund_id" not in without
    assert set(without) == CARD_KEYS - {"fund_id"}


async def test_the_mesa_reads_the_fund_on_the_wire(db_session, client, rrf_app) -> None:
    """On the route the key is present for the Painel's readers — ``null`` while nobody assigned
    a fund, which is the honest answer to a different question, and the id once the mesa did."""
    gestor = await as_gestor(db_session, rrf_app)
    unassigned = await create(client, await as_team(db_session, rrf_app, "um@rr.test"))
    assigned = await create(client, await as_team(db_session, rrf_app, "dois@rr.test"))
    await give_fund(db_session, assigned["id"])

    cards = await board(client, gestor)

    assert cards[unassigned["id"]]["fund_id"] is None
    assert cards[assigned["id"]]["fund_id"] == "linguas"


# ——— the sections ————————————————————————————————————————————————————————————————


async def test_an_answer_the_sections_do_not_carry_is_empty_and_the_card_stays(
    db_session, client, rrf_app
) -> None:
    """A document missing ``lang_name`` or ``people_name`` — or missing its sections row
    altogether, the restored-dump case ``document()`` already tolerates — answers ``""`` for the
    chip and keeps the card: the board is never dropped by one request's hole."""
    mesa = await as_mesa(db_session, rrf_app)
    named = draft()
    named["fields"]["lang_name"] = "Xerente"
    named["fields"]["people_name"] = "Akwẽ"
    holed = await create(client, await as_team(db_session, rrf_app, "um@rr.test"), **named)
    rowless = await create(client, await as_team(db_session, rrf_app, "dois@rr.test"), **named)
    whole = await create(client, await as_team(db_session, rrf_app, "tres@rr.test"), **named)

    sections = (
        await db_session.execute(
            select(RRRequestSections).where(RRRequestSections.request_id == holed["id"])
        )
    ).scalar_one()
    content = dict(sections.content)
    fields = dict(content["fields"])
    assert fields.pop("lang_name") == "Xerente"
    fields["people_name"] = None
    content["fields"] = fields
    sections.content = content
    await db_session.execute(
        RRRequestSections.__table__.delete().where(RRRequestSections.request_id == rowless["id"])
    )
    await db_session.commit()

    cards = await board(client, mesa)

    assert set(cards) == {holed["id"], rowless["id"], whole["id"]}
    assert (cards[holed["id"]]["lang_name"], cards[holed["id"]]["people_name"]) == ("", "")
    assert (cards[rowless["id"]]["lang_name"], cards[rowless["id"]]["people_name"]) == ("", "")
    assert cards[rowless["id"]]["reg_name"] == rowless["document"]["fields"]["reg_name"]
    assert (cards[whole["id"]]["lang_name"], cards[whole["id"]]["people_name"]) == (
        "Xerente",
        "Akwẽ",
    )


# ——— the cost ————————————————————————————————————————————————————————————————————


async def test_the_board_is_two_statements_however_many_cards_there_are(
    db_session, client, rrf_app, test_engine
) -> None:
    """What replaced one request per card must not become one statement per card: the
    statements touching the request tables are counted with one card and with five, and the
    sections come in a single ``IN`` rather than a select per request."""
    mesa = await as_mesa(db_session, rrf_app)

    async def request_reads() -> list[str]:
        statements: list[str] = []

        @event.listens_for(test_engine.sync_engine, "before_cursor_execute")
        def _record(conn, cursor, statement, parameters, context, executemany) -> None:
            statements.append(" ".join(statement.split()))

        try:
            await board(client, mesa)
        finally:
            event.remove(test_engine.sync_engine, "before_cursor_execute", _record)
        return [s for s in statements if "rr_request" in s]

    await create(client, await as_team(db_session, rrf_app, "equipe-0@rr.test"))
    one = await request_reads()
    for i in range(1, 5):
        await create(client, await as_team(db_session, rrf_app, f"equipe-{i}@rr.test"))

    five = await request_reads()
    assert len(await board(client, mesa)) == 5
    assert len(five) == len(one) == 2, (one, five)
    assert sum("rr_request_sections" in s for s in five) == 1


# ——— the address ———————————————————————————————————————————————————————————————


def test_board_is_declared_before_the_request_id_route() -> None:
    """``/requests/board`` must be matched before ``/requests/{request_id}``, or the Painel's
    read answers 404 *request "board" not found*; the order is read off the app's own table."""
    paths = [route.path for route in app.routes if hasattr(route, "path")]
    board_at = paths.index("/api/resource-requests/requests/board")
    by_id_at = paths.index("/api/resource-requests/requests/{request_id}")
    assert board_at < by_id_at


async def test_board_is_not_taken_for_a_request_id(db_session, client, rrf_app) -> None:
    mesa = await as_mesa(db_session, rrf_app)

    res = await client.get(BOARD, headers=mesa)

    assert res.status_code == 200, res.text
    assert res.json() == []
