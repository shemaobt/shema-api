"""The board through the real route: moves, the golden rule, the trail — FE-15's vectors.

The acceptance tests were written before the endpoint existed:
``src/utils/__tests__/boardTransition.test.ts`` in the frontend states each move and what
it does to the money, and this file ports those vectors against the API — same ten cards
(``fixtures/panel.ts``), same amounts, same expected balances, with the fixture's 480.000
allocation entering as the ``ALLOCATION`` movement it becomes on this side (GATE-01 D6).

**One vector inverts, deliberately.** The frontend approves a fundless card and renders
the hole (*"aprovado sem fundo entra na faixa e em fundo nenhum — e é para a tela
dizer"*); the server refuses it, because OBT-457's own DoD says so — GATE-01 D4 made the
fund the mesa's triage decision, so null is legitimate *before* ``aprovado`` and BE-07
cannot debit a fund it was never told. The rule is BE-11's; this endpoint is where it
fires, as a service refusal and never a DDL CHECK.

The graph across the six columns is total — the record of that decision is
``_transition.py``'s docstring — so the 4xx refusals here are states, not edges: a draft
is not on the board, and nothing enters ``aprovado`` without a fund and an amount.

No test uses a platform-admin account (they pass every guard unconditionally), and the
draft builders are ``test_requests``'s and ``test_evaluations``'s own, imported rather
than repeated.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models.resource_request import (
    RRBoardTransition,
    RRFundMovement,
    RRMovementKind,
    RRRequest,
    RRStage,
)
from tests.baker import make_user
from tests.test_resource_requests.conftest import grant
from tests.test_resource_requests.test_evaluations import (
    as_gestor,
    endorse,
    give_fund,
    put_evaluation,
)
from tests.test_resource_requests.test_requests import answers, as_mesa, as_team, create

REQUESTS = "/api/resource-requests/requests"
FUNDS = "/api/resource-requests/funds"

STAGES = [stage.value for stage in RRStage]


async def move(client, headers, request_id: str, to: str):
    return await client.post(f"{REQUESTS}/{request_id}/move", json={"to": to}, headers=headers)


async def board_card(db_session, client, team, valor: str, fund: str | None) -> str:
    """One submitted, endorsed card worth ``valor``, with its fund assigned the way the
    mesa will. **The endorsement is a precondition of the board, not decoration**: since
    BE-16's rule is enforced (``guard_endorsement``), a card nobody signed leaves
    ``triagem`` only for ``recusado``, so an unendorsed card could not exercise a single
    vector below. The two tests that are *about* the rule build their card without it."""
    created = await create(client, team, fields={**answers(), "amount_requested": valor})
    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=team)
    assert res.status_code == 200, res.text
    await endorse(db_session, created["id"])
    if fund is not None:
        await give_fund(db_session, created["id"], fund)
    return created["id"]


async def allocate(db_session, amount: str = "480000.00") -> None:
    """The fixture's *alocado*, as the ``ALLOCATION`` movement it is on this side."""
    from app.services.resource_request import append_movement

    gestora = await make_user(db_session, email="alocadora@rr.test")
    await append_movement(
        db_session,
        fund_id="linguas",
        kind=RRMovementKind.ALLOCATION,
        amount=Decimal(amount),
        author_id=gestora.id,
        reason="alocação da fixture",
    )
    await db_session.commit()


async def linguas(client, headers) -> dict:
    res = await client.get(FUNDS, headers=headers)
    assert res.status_code == 200, res.text
    return next(fund for fund in res.json() if fund["id"] == "linguas")


#: ``fixtures/panel.ts``'s ten cards: (fixture id, valor, fund, status).
PANEL = [
    (1, "128000.00", "linguas", "aprovado"),
    (2, "74000.00", "linguas", "analise"),
    (3, "38000.00", None, "triagem"),
    (4, "26000.00", "linguas", "condicional"),
    (5, "31000.00", "linguas", "aprovado"),
    (6, "18000.00", None, "triagem"),
    (7, "52000.00", "linguas", "revisar"),
    (8, "96000.00", "linguas", "recusado"),
    (9, "22000.00", "linguas", "analise"),
    (10, "29000.00", None, "triagem"),
]


async def panel(db_session, client, rrf_app) -> tuple[dict[int, str], dict[str, str]]:
    """The frontend's sample board, built through the real endpoints.

    Every non-``triagem`` stage is reached by a move through the route, so the two
    approved cards (1 and 5) enter the board the way they would in production — with
    their deductions written. Baseline after building: committed 159.000, allocated
    480.000, available 321.000, exactly ``fundSummaries(PANEL_REQUESTS)``.
    """
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    ids: dict[int, str] = {}
    for numero, valor, fund, stage in PANEL:
        ids[numero] = await board_card(db_session, client, team, valor, fund)
        if stage != "triagem":
            res = await move(client, mesa, ids[numero], stage)
            assert res.status_code == 200, res.text
    await allocate(db_session)
    return ids, mesa


# ——— who may touch the board ————————————————————————————————————————————————————


async def test_a_team_neither_moves_nor_reads_the_trail(db_session, client, rrf_app) -> None:
    """``move_board`` and ``manage_funds`` both exclude ``equipe`` — even on its own
    request: GATE-03 D4 gives a team its status and nothing else."""
    team = await as_team(db_session, rrf_app)
    card = await board_card(db_session, client, team, "52000.00", "linguas")

    moved = await move(client, team, card, "analise")
    trail = await client.get(f"{REQUESTS}/{card}/transitions", headers=team)

    assert moved.status_code == 403
    assert trail.status_code == 403


async def test_the_gestor_moves_the_board(db_session, client, rrf_app) -> None:
    """GATE-02 D3 — the cell that moved: *"tem acesso a quase tudo em relação aos
    projetos"*. Moving is still not deciding."""
    team = await as_team(db_session, rrf_app)
    gestor = await as_gestor(db_session, rrf_app)
    card = await board_card(db_session, client, team, "52000.00", "linguas")

    res = await move(client, gestor, card, "analise")

    assert res.status_code == 200, res.text
    assert res.json()["stage"] == "analise"


# ——— what the endpoint refuses, and why ——————————————————————————————————————————


async def test_an_unknown_request_is_404(db_session, client, rrf_app) -> None:
    mesa = await as_mesa(db_session, rrf_app)

    res = await move(client, mesa, str(uuid.uuid4()), "analise")

    assert res.status_code == 404


async def test_an_unknown_column_is_refused_with_the_reason(db_session, client, rrf_app) -> None:
    """The six ids are the enum; a seventh column does not exist to be moved to."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    card = await board_card(db_session, client, team, "52000.00", "linguas")

    res = await move(client, mesa, card, "arquivado")

    assert res.status_code == 422


async def test_a_draft_is_not_on_the_board(db_session, client, rrf_app) -> None:
    """A stage on an unsubmitted row is the column's default, not a position the mesa
    gave it — moving one would put a document the mesa never received on the board."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await create(client, team)

    res = await move(client, mesa, created["id"], "analise")

    assert res.status_code == 409
    assert "submitted" in res.json()["detail"]
    assert (await db_session.execute(select(RRBoardTransition))).scalars().all() == []


async def unendorsed_card(db_session, client, team, fund: str | None = "linguas") -> str:
    """``board_card`` minus the one thing these two tests are about."""
    created = await create(client, team, fields={**answers(), "amount_requested": "52000.00"})
    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=team)
    assert res.status_code == 200, res.text
    if fund is not None:
        await give_fund(db_session, created["id"], fund)
    return created["id"]


async def test_um_pedido_sem_endosso_nao_sai_da_triagem(db_session, client, rrf_app) -> None:
    """BE-16's rule, enforced where ``rr_requests``'s docstring assigned it: ``analise``
    and every column past it wait for the base's signature. Stated over destinations, so
    the direct ``triagem -> aprovado`` is refused by the same sentence and not left open —
    which is the hole a per-edge rule would have."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    card = await unendorsed_card(db_session, client, team)

    for destino in ("analise", "aprovado", "condicional", "revisar"):
        res = await move(client, mesa, card, destino)

        assert res.status_code == 409, f"{destino}: {res.text}"
        assert "endorsement" in res.json()["detail"]

    assert (await db_session.execute(select(RRBoardTransition))).scalars().all() == []
    row = (await db_session.execute(select(RRRequest).where(RRRequest.id == card))).scalar_one()
    assert row.stage is RRStage.TRIAGEM
    assert (await db_session.execute(select(RRFundMovement))).scalars().all() == []


async def test_sem_endosso_o_caminho_para_recusado_continua_aberto(
    db_session, client, rrf_app
) -> None:
    """The other half of the same sentence, and the reason it is a destination rule:
    declining stays possible, because a base that does not recognise a project is itself a
    reason to decline. Refusing every exit would trap the card instead of gating it."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    card = await unendorsed_card(db_session, client, team)

    res = await move(client, mesa, card, "recusado")

    assert res.status_code == 200, res.text
    assert res.json()["stage"] == "recusado"


async def test_a_decisao_tambem_espera_o_endosso(db_session, client, rrf_app) -> None:
    """The rule covers both doors GATE-02 D6 opened. A decision moves the card through the
    same ``transition_stage``, so a mesa that cannot drag an unsigned card cannot decide it
    into the same column either — and the pre-check refuses before a scores row is
    written, which is why the guard is pure and runs beside ``guard_stage_entry``."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    card = await unendorsed_card(db_session, client, team)

    res = await put_evaluation(client, mesa, card, decision="approved")

    assert res.status_code == 409, res.text
    assert "endorsement" in res.json()["detail"]
    assert (await db_session.execute(select(RRFundMovement))).scalars().all() == []
    row = (await db_session.execute(select(RRRequest).where(RRRequest.id == card))).scalar_one()
    assert row.stage is RRStage.TRIAGEM


async def test_the_payload_cannot_state_the_mover(db_session, client, rrf_app) -> None:
    """Mover and instant are the server's stamps; a payload that tries is refused."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    card = await board_card(db_session, client, team, "52000.00", "linguas")

    res = await client.post(
        f"{REQUESTS}/{card}/move",
        json={"to": "analise", "moved_by": "alguém"},
        headers=mesa,
    )

    assert res.status_code == 422


async def test_landing_on_the_column_where_it_already_is_writes_nothing(
    db_session, client, rrf_app
) -> None:
    """FE-15's *moved: null*, decidably: not an illegal move, and not an event either."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    card = await board_card(db_session, client, team, "52000.00", "linguas")
    assert (await move(client, mesa, card, "analise")).status_code == 200

    res = await move(client, mesa, card, "analise")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["moved"] is False
    assert body["stage"] == "analise"
    assert body["from_stage"] is None
    assert body["fund_delta"] is None
    assert body["movement_id"] is None
    rows = (await db_session.execute(select(RRBoardTransition))).scalars().all()
    assert len(rows) == 1


async def test_approving_with_no_fund_fails_decidably(db_session, client, rrf_app) -> None:
    """The vector that inverts on the server, by OBT-457's own DoD: the frontend renders
    the fundless approval as a hole for the screen to announce; here BE-07 cannot debit a
    fund it was never told, so the move is refused and nothing is written."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    card = await board_card(db_session, client, team, "18000.00", None)

    res = await move(client, mesa, card, "aprovado")

    assert res.status_code == 409
    assert "fund" in res.json()["detail"]
    request = (await db_session.execute(select(RRRequest).where(RRRequest.id == card))).scalar_one()
    assert request.stage.value == "triagem"
    assert (await db_session.execute(select(RRFundMovement))).scalars().all() == []
    assert (await db_session.execute(select(RRBoardTransition))).scalars().all() == []


# ——— a regra de ouro: os vetores do FE-15 contra a API ———————————————————————————


async def test_aprovar_compromete_exatamente_o_valor_do_pedido(db_session, client, rrf_app) -> None:
    ids, mesa = await panel(db_session, client, rrf_app)

    res = await move(client, mesa, ids[2], "aprovado")

    assert res.status_code == 200, res.text
    delta = res.json()["fund_delta"]
    assert delta["fund_id"] == "linguas"
    assert Decimal(delta["committed_delta"]) == Decimal("74000")
    fund = await linguas(client, mesa)
    assert Decimal(fund["committed"]) == Decimal("233000")
    assert Decimal(fund["available"]) == Decimal("247000")


async def test_tirar_de_aprovado_devolve_ao_fundo(db_session, client, rrf_app) -> None:
    """The restoration is a compensating ``REVERSAL`` copying the deduction's amount —
    un-approving gives back exactly what approving took, whatever the request says now."""
    ids, mesa = await panel(db_session, client, rrf_app)

    res = await move(client, mesa, ids[1], "revisar")

    assert res.status_code == 200, res.text
    assert Decimal(res.json()["fund_delta"]["committed_delta"]) == Decimal("-128000")
    fund = await linguas(client, mesa)
    assert Decimal(fund["available"]) == Decimal("449000")

    reversal = (
        await db_session.execute(
            select(RRFundMovement).where(RRFundMovement.id == res.json()["movement_id"])
        )
    ).scalar_one()
    assert reversal.kind is RRMovementKind.REVERSAL
    assert reversal.reverses_id is not None


async def test_ida_e_volta_deixa_todo_fundo_como_estava(db_session, client, rrf_app) -> None:
    ids, mesa = await panel(db_session, client, rrf_app)

    assert (await move(client, mesa, ids[1], "recusado")).status_code == 200
    assert (await move(client, mesa, ids[1], "aprovado")).status_code == 200

    fund = await linguas(client, mesa)
    assert Decimal(fund["allocated"]) == Decimal("480000")
    assert Decimal(fund["committed"]) == Decimal("159000")
    assert Decimal(fund["available"]) == Decimal("321000")


async def test_sair_de_aprovado_para_condicional_tambem_e_liberacao(
    db_session, client, rrf_app
) -> None:
    """Only ``aprovado`` commits — ``condicional`` is a release like any other exit."""
    ids, mesa = await panel(db_session, client, rrf_app)

    res = await move(client, mesa, ids[1], "condicional")

    assert res.status_code == 200, res.text
    assert Decimal(res.json()["fund_delta"]["committed_delta"]) == Decimal("-128000")


async def test_condicional_nao_compromete_nada_ao_receber(db_session, client, rrf_app) -> None:
    ids, mesa = await panel(db_session, client, rrf_app)

    res = await move(client, mesa, ids[3], "condicional")

    assert res.status_code == 200, res.text
    assert res.json()["fund_delta"] is None
    fund = await linguas(client, mesa)
    assert Decimal(fund["committed"]) == Decimal("159000")
    assert Decimal(fund["available"]) == Decimal("321000")


async def test_mover_entre_colunas_fora_de_aprovado_nao_mexe_em_dinheiro(
    db_session, client, rrf_app
) -> None:
    ids, mesa = await panel(db_session, client, rrf_app)

    res = await move(client, mesa, ids[3], "analise")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["fund_delta"] is None
    assert body["movement_id"] is None
    assert body["moved"] is True
    assert body["stage"] == "analise"
    movements = (await db_session.execute(select(RRFundMovement))).scalars().all()
    assert len(movements) == 3


async def test_o_grafo_e_total(db_session, client, rrf_app) -> None:
    """FE-15's last vector: any column reaches any other. Tightening it would freeze in
    code a decision that is the mesa's — the refusals are states, never edges."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    card = await board_card(db_session, client, team, "52000.00", "linguas")

    for origin in STAGES:
        res = await move(client, mesa, card, origin)
        assert res.status_code == 200, f"{origin}: {res.text}"
        for target in STAGES:
            if target == origin:
                continue
            there = await move(client, mesa, card, target)
            assert there.status_code == 200, f"{origin} -> {target}: {there.text}"
            assert there.json()["stage"] == target
            back = await move(client, mesa, card, origin)
            assert back.status_code == 200, f"{target} -> {origin}: {back.text}"

    fund = await linguas(client, mesa)
    assert Decimal(fund["committed"]) == Decimal("0")


# ——— a decisão e o arrasto convergem —————————————————————————————————————————————


async def test_a_decisao_sobre_um_cartao_ja_arrastado_nao_deduz_duas_vezes(
    db_session, client, rrf_app
) -> None:
    """GATE-02 D6 through the shared path: the mesa dragged the card into ``aprovado``,
    the decision lands on it, and the transition is a no-op — one deduction, one event."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    card = await board_card(db_session, client, team, "52000.00", "linguas")
    assert (await move(client, mesa, card, "aprovado")).status_code == 200

    res = await put_evaluation(client, mesa, card, decision="approved")

    assert res.status_code == 200, res.text
    assert res.json()["decision"] == "approved"
    assert res.json()["evaluated_at"] is not None
    movements = (await db_session.execute(select(RRFundMovement))).scalars().all()
    assert len(movements) == 1
    transitions = (await db_session.execute(select(RRBoardTransition))).scalars().all()
    assert len(transitions) == 1


async def test_desaprovar_pelo_quadro_compensa_a_deducao_da_decisao(
    db_session, client, rrf_app
) -> None:
    """The other direction: BE-06's decision wrote the deduction, the mesa's drag out of
    ``aprovado`` writes the compensating movement — and the trail tells the two moves
    apart by ``evaluation_id``.

    **Rows are identified by what they are, never by their position in a list**, and that
    is not style: ``created_at`` is ``server_default=func.now()``, which on SQLite — where
    this suite runs — compiles to ``CURRENT_TIMESTAMP`` at **second** resolution, so two
    rows written inside one second carry the same instant and ``order_by(created_at, id)``
    tiebreaks on a random uuid4. Written positionally this assertion passed or failed by
    coin flip. On PostgreSQL ``now()`` is microsecond-resolution and the endpoint's
    ordering is exact, which is why the ordering itself is asserted where the moves are
    seconds apart (``test_o_historico_e_consultavel_por_pedido``) and never here.
    """
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    card = await board_card(db_session, client, team, "1200.00", "linguas")
    assert (await put_evaluation(client, mesa, card, decision="approved")).status_code == 200

    res = await move(client, mesa, card, "revisar")

    assert res.status_code == 200, res.text
    assert Decimal(res.json()["fund_delta"]["committed_delta"]) == Decimal("-1200")

    movements = (await db_session.execute(select(RRFundMovement))).scalars().all()
    by_kind = {movement.kind: movement for movement in movements}
    assert set(by_kind) == {RRMovementKind.APPROVAL_DEDUCTION, RRMovementKind.REVERSAL}
    deduction = by_kind[RRMovementKind.APPROVAL_DEDUCTION]
    reversal = by_kind[RRMovementKind.REVERSAL]
    assert reversal.reverses_id == deduction.id
    assert reversal.amount == deduction.amount

    trail = (await db_session.execute(select(RRBoardTransition))).scalars().all()
    by_stage = {row.to_stage: row for row in trail}
    assert len(trail) == 2 and set(by_stage) == {RRStage.APROVADO, RRStage.REVISAR}
    assert by_stage[RRStage.APROVADO].evaluation_id is not None
    assert by_stage[RRStage.APROVADO].movement_id == deduction.id
    assert by_stage[RRStage.REVISAR].evaluation_id is None
    assert by_stage[RRStage.REVISAR].movement_id == reversal.id

    fund = await linguas(client, mesa)
    assert Decimal(fund["committed"]) == Decimal("0")


# ——— o histórico ————————————————————————————————————————————————————————————————


async def test_o_historico_e_consultavel_por_pedido(db_session, client, rrf_app) -> None:
    """*Quem moveu o quê, quando, de onde para onde* — oldest first, with the money
    moves naming their movements and the hand moves carrying no evaluation.

    This is the one test that asserts the **order**, so it is the one that has to earn
    it: the moves are spaced past a second because ``created_at`` is ``CURRENT_TIMESTAMP``
    on SQLite and rows inside one second are indistinguishable to the endpoint's
    ``order_by`` (the sibling test above records the whole mechanism). Spaced, the
    instants really differ and *oldest first* is a claim about the query rather than about
    uuid luck.
    """
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    card = await board_card(db_session, client, team, "52000.00", "linguas")
    for index, stage in enumerate(("analise", "aprovado", "revisar")):
        if index:
            await asyncio.sleep(1.05)
        assert (await move(client, mesa, card, stage)).status_code == 200

    res = await client.get(f"{REQUESTS}/{card}/transitions", headers=mesa)

    assert res.status_code == 200, res.text
    rows = res.json()
    assert [(row["from_stage"], row["to_stage"]) for row in rows] == [
        ("triagem", "analise"),
        ("analise", "aprovado"),
        ("aprovado", "revisar"),
    ]
    assert all(row["moved_by"] is not None for row in rows)
    assert all(row["created_at"] is not None for row in rows)
    assert all(row["evaluation_id"] is None for row in rows)
    assert rows[0]["movement_id"] is None
    assert rows[1]["movement_id"] is not None
    assert rows[2]["movement_id"] is not None


async def test_historico_de_pedido_desconhecido_e_404(db_session, client, rrf_app) -> None:
    mesa = await as_mesa(db_session, rrf_app)

    res = await client.get(f"{REQUESTS}/{uuid.uuid4()}/transitions", headers=mesa)

    assert res.status_code == 404


# ——— a atomicidade, com a falha forçada ——————————————————————————————————————————


class _Boom(RuntimeError):
    pass


async def test_uma_falha_entre_o_razao_e_a_etapa_desfaz_os_dois(
    db_session, client, rrf_app, monkeypatch
) -> None:
    """The corruption this design exists to prevent, forced: the deduction is already
    flushed when the stage event explodes, and neither survives.

    The patch replaces the transition row's constructor, so the failure lands exactly
    between the two writes — after ``append_movement`` flushed the ledger entry, before
    the stage changes. The service never committed, so the rollback discards the pending
    movement with the stage untouched: a deduction cannot outlive its stage change, and
    the stage cannot change without its deduction, because there is one transaction under
    both. In production ``get_db`` rolls back on the same exception this test catches.
    """
    from app.api.resource_requests._deps import APP_KEY
    from app.services.resource_request import _transition
    from app.services.resource_request.move_request import move_request as service_move

    team = await as_team(db_session, rrf_app)
    mesa_user = await make_user(db_session, email="mesa-atomica@rr.test")
    await grant(db_session, mesa_user, rrf_app, "mesa")
    card = await board_card(db_session, client, team, "52000.00", "linguas")

    def explode(**_kwargs: object) -> None:
        raise _Boom("forced between the ledger and the stage")

    monkeypatch.setattr(_transition, "RRBoardTransition", explode)

    with pytest.raises(_Boom):
        await service_move(db_session, card, RRStage.APROVADO, mesa_user, APP_KEY)
    await db_session.rollback()

    request = (await db_session.execute(select(RRRequest).where(RRRequest.id == card))).scalar_one()
    assert request.stage.value == "triagem"
    assert (await db_session.execute(select(RRFundMovement))).scalars().all() == []
    assert (await db_session.execute(select(RRBoardTransition))).scalars().all() == []
