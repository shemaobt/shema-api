"""Who writes ``rr_requests.fund_id``, when, and what the writing costs the ledger.

GATE-01 D4 answered that the mesa assigns the fund at triage and that no field enters the
form for it, so the column has an endpoint and the document has nothing — the two halves
this file pins, together with the invariant they exist to make satisfiable: **a request
does not enter ``aprovado`` with ``fund_id IS NULL``**, refused at *both* doors GATE-02 D6
opened, from one owner.

The refusal a Gestor gets here is the client's sentence (*"somente a mesa"*, 28/aug/2026)
and not a restrictive default, which is why it is tested against a real Gestor session
rather than asserted about the capability map alone.

No test uses a platform-admin account — they pass every guard unconditionally — and the
draft builders are ``test_requests``'s own, imported rather than repeated.
"""

from __future__ import annotations

import sys
from decimal import Decimal

from sqlalchemy import select

from app.db.models.resource_request import (
    RRFund,
    RRFundMovement,
    RRMovementKind,
    RRRequest,
    RRRequestFieldHistory,
)
from app.services.resource_request import list_fund_options as options_service
from app.services.resource_request._fund_choices import options_from
from tests.test_resource_requests.test_evaluations import (
    as_gestor,
    endorse,
    give_fund,
    put_evaluation,
)
from tests.test_resource_requests.test_requests import answers, as_mesa, as_team, create

#: The package re-exports the ``assign_fund`` *function* under the name of its own module,
#: so ``from … import assign_fund`` hands back the function and a ``setattr`` on it patches
#: nothing. The module object itself is reached through ``sys.modules``.
assign_fund_service = sys.modules["app.services.resource_request.assign_fund"]

REQUESTS = "/api/resource-requests/requests"
FUNDS = "/api/resource-requests/funds"


async def make_fund(db_session, fund_id: str, name: str) -> RRFund:
    fund = RRFund(id=fund_id, name=name)
    db_session.add(fund)
    await db_session.commit()
    return fund


async def submitted(client, headers, valor: str = "1200.00") -> str:
    created = await create(client, headers, fields={**answers(), "amount_requested": valor})
    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)
    assert res.status_code == 200, res.text
    return created["id"]


async def put_fund(client, headers, request_id: str, fund_id: str):
    return await client.put(
        f"{REQUESTS}/{request_id}/fund", json={"fund_id": fund_id}, headers=headers
    )


async def committed(client, headers, fund_id: str) -> Decimal:
    res = await client.get(FUNDS, headers=headers)
    assert res.status_code == 200, res.text
    return Decimal(next(fund for fund in res.json() if fund["id"] == fund_id)["committed"])


# ——— quem atribui ————————————————————————————————————————————————————————————————


async def test_a_mesa_atribui_o_fundo_e_a_troca_fica_registrada(
    db_session, client, rrf_app
) -> None:
    """Quem atribuiu, quando, e de qual fundo para qual — uma linha por mudança."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await make_fund(db_session, "linguas", "Shema Línguas")
    await make_fund(db_session, "btat", "Shema BTAT")
    card = await submitted(client, team)

    first = await put_fund(client, mesa, card, "linguas")
    second = await put_fund(client, mesa, card, "btat")

    assert first.status_code == 200, first.text
    assert first.json()["previous_fund_id"] is None
    assert second.status_code == 200, second.text
    assert second.json()["previous_fund_id"] == "linguas"
    assert second.json()["fund_id"] == "btat"
    assert second.json()["assigned_at"] is not None

    request = (await db_session.execute(select(RRRequest).where(RRRequest.id == card))).scalar_one()
    await db_session.refresh(request)
    assert request.fund_id == "btat"

    rows = (
        (
            await db_session.execute(
                select(RRRequestFieldHistory)
                .where(RRRequestFieldHistory.request_id == card)
                .order_by(RRRequestFieldHistory.changed_at)
            )
        )
        .scalars()
        .all()
    )
    assert [(row.field_key, row.old_value, row.new_value) for row in rows] == [
        ("fund_id", None, "linguas"),
        ("fund_id", "linguas", "btat"),
    ]
    assert all(row.changed_by is not None for row in rows)


async def test_atribuir_o_mesmo_fundo_de_novo_nao_escreve_nada(db_session, client, rrf_app) -> None:
    """A mesma resposta do quadro para um card já na coluna: pedir o estado em que a
    coisa está não é um pedido ilegal, e não vira linha de histórico."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await make_fund(db_session, "linguas", "Shema Línguas")
    card = await submitted(client, team)

    assert (await put_fund(client, mesa, card, "linguas")).status_code == 200
    again = await put_fund(client, mesa, card, "linguas")

    assert again.status_code == 200, again.text
    assert again.json()["changed"] is False
    assert again.json()["assigned_at"] is None
    rows = (
        (
            await db_session.execute(
                select(RRRequestFieldHistory).where(RRRequestFieldHistory.request_id == card)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


async def test_o_gestor_e_recusado_neste_endpoint(db_session, client, rrf_app) -> None:
    """*"Somente a mesa"* (cliente, 28/ago/2026) — e o Gestor move o quadro e aloca
    dinheiro, então a recusa não é um efeito de ele ter pouca coisa."""
    team = await as_team(db_session, rrf_app)
    gestor = await as_gestor(db_session, rrf_app)
    await make_fund(db_session, "linguas", "Shema Línguas")
    card = await submitted(client, team)

    written = await put_fund(client, gestor, card, "linguas")
    read = await client.get(f"{REQUESTS}/{card}/fund-options", headers=gestor)

    assert written.status_code == 403
    assert read.status_code == 403
    assert (await put_fund(client, team, card, "linguas")).status_code == 403


async def test_um_fundo_fora_da_lista_de_escolha_e_recusado(db_session, client, rrf_app) -> None:
    """Desconhecido e aposentado são o mesmo fato daqui: não está em oferta."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    card = await submitted(client, team)

    res = await put_fund(client, mesa, card, "ora-bridge")

    assert res.status_code == 422, res.text


async def test_um_fundo_que_existe_mas_saiu_da_lista_tambem_e_recusado(
    db_session, client, rrf_app, monkeypatch
) -> None:
    """O par da BE-10 (OBT-471), fechado deste lado: ela aposenta **tirando da lista de
    escolha** e diz na própria PR que o refuso duro é desta issue.

    A aposentadoria em si não existe nesta base — ``retired_at`` chega com aquela branch —
    então o que se prova aqui é a regra que é minha: o que a atribuição consulta é a lista
    de escolha e não a existência da linha, de modo que um fundo que saiu dela é recusado
    ainda estando na tabela, com a mesma resposta decidível de um id desconhecido. No dia
    em que ``choosable_funds`` filtrar ``retired_at IS NULL``, este teste já é sobre um
    fundo aposentado sem mudar uma linha."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await make_fund(db_session, "linguas", "Shema Línguas")
    await make_fund(db_session, "ready", "Ready Vessels")
    card = await submitted(client, team)

    async def sem_o_ready(db):
        return [
            fund
            for fund in (await db.execute(select(RRFund).order_by(RRFund.name))).scalars().all()
            if fund.id != "ready"
        ]

    monkeypatch.setattr(assign_fund_service, "choosable_funds", sem_o_ready)

    recusado = await put_fund(client, mesa, card, "ready")
    aceito = await put_fund(client, mesa, card, "linguas")

    assert recusado.status_code == 422, recusado.text
    assert aceito.status_code == 200, aceito.text


async def test_um_pedido_que_ja_apontava_para_o_fundo_aposentado_segue_valido(
    db_session, client, rrf_app, monkeypatch
) -> None:
    """Aposentar não invalida o que já estava atribuído: o pedido continua legível, o
    seletor continua mostrando o fundo — marcado e não selecionável — e a aprovação
    continua encontrando um fundo para debitar."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await make_fund(db_session, "linguas", "Shema Línguas")
    await make_fund(db_session, "ready", "Ready Vessels")
    card = await submitted(client, team)
    await endorse(db_session, card)
    assert (await put_fund(client, mesa, card, "ready")).status_code == 200

    async def sem_o_ready(db):
        return [
            fund
            for fund in (await db.execute(select(RRFund).order_by(RRFund.name))).scalars().all()
            if fund.id != "ready"
        ]

    monkeypatch.setattr(options_service, "choosable_funds", sem_o_ready)

    res = await client.get(f"{REQUESTS}/{card}/fund-options", headers=mesa)
    decisao = await put_evaluation(client, mesa, card, decision="approved")

    assert res.status_code == 200, res.text
    assert [(o["id"], o["assigned"], o["selectable"], o["retired"]) for o in res.json()] == [
        ("linguas", False, True, False),
        ("ready", True, False, True),
    ]
    assert decisao.status_code == 200, decisao.text
    assert await committed(client, mesa, "ready") == Decimal("1200.00")


# ——— a regra das duas portas —————————————————————————————————————————————————————


async def test_aprovar_sem_fundo_falha_nas_duas_portas(db_session, client, rrf_app) -> None:
    """A GATE-02 D6 abriu duas portas para `aprovado` — a decisão da Parte C e o arrasto
    no quadro — e a regra da BE-11 fecha as duas com a mesma frase, de um dono só."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await make_fund(db_session, "linguas", "Shema Línguas")
    pelo_quadro = await submitted(client, team)
    pela_decisao = await submitted(client, team)
    await endorse(db_session, pelo_quadro)
    await endorse(db_session, pela_decisao)

    arrasto = await client.post(
        f"{REQUESTS}/{pelo_quadro}/move", json={"to": "aprovado"}, headers=mesa
    )
    decisao = await put_evaluation(client, mesa, pela_decisao, decision="approved")

    assert arrasto.status_code == 409, arrasto.text
    assert decisao.status_code == 409, decisao.text
    assert "no fund" in arrasto.json()["detail"]
    assert arrasto.json()["detail"] == decisao.json()["detail"]

    assert (await db_session.execute(select(RRFundMovement))).scalars().all() == []


async def test_com_o_fundo_atribuido_a_aprovacao_passa(db_session, client, rrf_app) -> None:
    """A recusa acima é sobre o estado do pedido, não sobre a aprovação: atribuído o
    fundo pelo endpoint da mesa, a mesma decisão entra e desconta."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await make_fund(db_session, "linguas", "Shema Línguas")
    card = await submitted(client, team)
    await endorse(db_session, card)

    assert (await put_fund(client, mesa, card, "linguas")).status_code == 200
    decisao = await put_evaluation(client, mesa, card, decision="approved")

    assert decisao.status_code == 200, decisao.text
    assert await committed(client, mesa, "linguas") == Decimal("1200.00")


# ——— a troca de um pedido já aprovado ————————————————————————————————————————————


async def test_trocar_o_fundo_de_um_aprovado_move_os_dois_saldos(
    db_session, client, rrf_app
) -> None:
    """Um movimento compensatório no fundo antigo e uma nova dedução no novo, na mesma
    transação: o que um recebe de volta é exatamente o que o outro compromete."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await make_fund(db_session, "linguas", "Shema Línguas")
    await make_fund(db_session, "btat", "Shema BTAT")
    card = await submitted(client, team, valor="5000.00")
    await endorse(db_session, card)
    assert (await put_fund(client, mesa, card, "linguas")).status_code == 200
    assert (await put_evaluation(client, mesa, card, decision="approved")).status_code == 200

    res = await put_fund(client, mesa, card, "btat")

    assert res.status_code == 200, res.text
    assert res.json()["fund_deltas"] == [
        {"fund_id": "linguas", "committed_delta": "-5000.00"},
        {"fund_id": "btat", "committed_delta": "5000.00"},
    ]
    assert len(res.json()["movement_ids"]) == 2

    assert await committed(client, mesa, "linguas") == Decimal("0.00")
    assert await committed(client, mesa, "btat") == Decimal("5000.00")

    kinds = (
        await db_session.execute(
            select(RRFundMovement.kind, RRFundMovement.fund_id).order_by(
                RRFundMovement.created_at, RRFundMovement.id
            )
        )
    ).all()
    assert (RRMovementKind.REVERSAL, "linguas") in kinds
    assert (RRMovementKind.APPROVAL_DEDUCTION, "btat") in kinds


async def test_trocar_o_fundo_de_um_pedido_em_triagem_nao_move_dinheiro(
    db_session, client, rrf_app
) -> None:
    """Só ``aprovado`` compromete fundo — a regra de ouro do protótipo, do outro lado."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await make_fund(db_session, "linguas", "Shema Línguas")
    await make_fund(db_session, "btat", "Shema BTAT")
    card = await submitted(client, team)
    assert (await put_fund(client, mesa, card, "linguas")).status_code == 200

    res = await put_fund(client, mesa, card, "btat")

    assert res.status_code == 200, res.text
    assert res.json()["fund_deltas"] == []
    assert (await db_session.execute(select(RRFundMovement))).scalars().all() == []


# ——— o seletor ———————————————————————————————————————————————————————————————————


async def test_o_seletor_marca_o_fundo_atribuido(db_session, client, rrf_app) -> None:
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await make_fund(db_session, "linguas", "Shema Línguas")
    await make_fund(db_session, "btat", "Shema BTAT")
    card = await submitted(client, team)
    assert (await put_fund(client, mesa, card, "btat")).status_code == 200

    res = await client.get(f"{REQUESTS}/{card}/fund-options", headers=mesa)

    assert res.status_code == 200, res.text
    assert res.json() == [
        {
            "id": "btat",
            "name": "Shema BTAT",
            "assigned": True,
            "selectable": True,
            "retired": False,
        },
        {
            "id": "linguas",
            "name": "Shema Línguas",
            "assigned": False,
            "selectable": True,
            "retired": False,
        },
    ]


def test_um_fundo_aposentado_ja_atribuido_continua_no_seletor() -> None:
    """A BE-10 aposenta tirando da lista de escolha; o seletor deste pedido continua
    mostrando o fundo que ele já usa, marcado e não selecionável — e por último, porque
    não é uma escolha e no meio da lista alguém acaba oferecendo."""
    aposentado = RRFund(id="ready", name="Ready Vessels")
    escolhiveis = [RRFund(id="linguas", name="Shema Línguas")]

    options = options_from(escolhiveis, aposentado)

    assert [(o.id, o.assigned, o.selectable, o.retired) for o in options] == [
        ("linguas", False, True, False),
        ("ready", True, False, True),
    ]


def test_sem_fundo_atribuido_o_seletor_e_so_a_lista_de_escolha() -> None:
    """``fund_id`` nulo é estado legítimo de quem está em triagem, não uma lacuna."""
    options = options_from([RRFund(id="linguas", name="Shema Línguas")], None)

    assert [(o.id, o.assigned, o.retired) for o in options] == [("linguas", False, False)]


# ——— o formulário não cresce ——————————————————————————————————————————————————————


async def test_o_fundo_nao_entra_no_documento_da_solicitacao(db_session, client, rrf_app) -> None:
    """As 45 chaves seguem 45: atribuir o fundo não muda um byte do que a equipe enviou,
    e o documento continua sem dizer de qual fundo o pedido pede."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await make_fund(db_session, "linguas", "Shema Línguas")
    card = await submitted(client, team)
    antes = (await client.get(f"{REQUESTS}/{card}", headers=team)).json()["document"]

    assert (await put_fund(client, mesa, card, "linguas")).status_code == 200

    depois = (await client.get(f"{REQUESTS}/{card}", headers=team)).json()["document"]
    assert depois == antes
    assert "fund_id" not in depois["fields"]
    assert "fund" not in depois


async def test_a_equipe_nao_ve_o_fundo_mudar_no_seu_pedido(db_session, client, rrf_app) -> None:
    """O envelope do pedido também não carrega o fundo — a GATE-03 D4 dá à equipe o seu
    status e nada mais, e a decisão de qual fundo paga é conversa da mesa."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await make_fund(db_session, "linguas", "Shema Línguas")
    card = await submitted(client, team)
    assert (await put_fund(client, mesa, card, "linguas")).status_code == 200

    envelope = (await client.get(f"{REQUESTS}/{card}", headers=team)).json()

    assert "fund_id" not in envelope


async def test_give_fund_e_o_endpoint_escrevem_a_mesma_coluna(db_session, client, rrf_app) -> None:
    """O atalho que os testes da BE-06/BE-08 usavam enquanto esta rota não existia
    escreve exatamente o que ela escreve — menos o registro, que é o que a rota traz."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    atalho = await submitted(client, team)
    rota = await submitted(client, team)
    await give_fund(db_session, atalho, "linguas")

    assert (await put_fund(client, mesa, rota, "linguas")).status_code == 200

    rows = (
        (await db_session.execute(select(RRRequest).where(RRRequest.id.in_([atalho, rota]))))
        .scalars()
        .all()
    )
    assert {row.fund_id for row in rows} == {"linguas"}
