"""GATE-03 D5/D6 through the real routes: who is told, when, on which channel — and who
is deliberately told nothing.

The whole file turns on one asymmetry. **A decision implies a column; a column never
implies a decision.** GATE-02 D6 made the two coincide in time — saving a decision moves
the card — which is exactly where the distinction is easiest to lose, so the negative test
is written first among the equals here: a mesa member dragging a card notifies nobody.

The other rule under it is temporal rather than logical: the in-app notice lands inside
the same transaction as the decision, and the e-mail leaves after that transaction has
committed. That is what makes a provider outage unable to revert a decision, and it is
proved by forcing one.

E-mails are captured at ``_notices.send_email`` — the name that module resolves — rather
than at the provider, because what is under test is which letters this module hands over,
not how BE-12 delivers them (``tests/test_email_infra.py`` owns that half).
"""

from __future__ import annotations

from importlib import import_module

import pytest
from sqlalchemy import select

from app.api.resource_requests._deps import APP_KEY
from app.db.models.notification import Notification
from app.db.models.resource_request import RRDecision, RRRequest, RRStage
from app.services.notifications.create_notification import create_notification
from app.services.notifications.get_rr_app_id import RR_APP_KEY
from app.services.resource_request.notify_decision import DECISION_COPY
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant
from tests.test_resource_requests.test_evaluations import (
    REQUESTS,
    as_gestor,
    give_fund,
    put_evaluation,
    submitted_request,
)
from tests.test_resource_requests.test_requests import as_mesa, as_team


@pytest.fixture()
def posted(monkeypatch) -> list[dict[str, str]]:
    """Every letter this module hands to ``send_email``, in order."""
    sent: list[dict[str, str]] = []

    async def _record(*, to: str, subject: str, html: str, from_name: str | None = None) -> bool:
        sent.append({"to": to, "subject": subject, "html": html})
        return True

    monkeypatch.setattr("app.services.resource_request._notices.send_email", _record)
    return sent


async def notices(db_session, user_id: str) -> list[Notification]:
    rows = await db_session.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at)
    )
    return list(rows.scalars().all())


async def user_id_of(db_session, email: str) -> str:
    from app.db.models.auth import User

    return (await db_session.execute(select(User.id).where(User.email == email))).scalar_one()


# ——— a decisão avisa, e o arrasto não ————————————————————————————————————————————


@pytest.mark.parametrize(
    ("decision", "stage"),
    [
        ("approved", RRStage.APROVADO),
        ("conditional", RRStage.CONDICIONAL),
        ("revise", RRStage.REVISAR),
        ("declined", RRStage.RECUSADO),
    ],
)
async def test_as_quatro_decisoes_avisam_a_equipe_nos_dois_canais(
    db_session, client, rrf_app, posted, decision, stage
) -> None:
    """*"As quatro decisões"* — o cliente, 28/ago/2026. Avisar só o aprovado seria avisar
    exatamente quem não precisa fazer mais nada."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    await give_fund(db_session, created["id"])
    posted.clear()

    res = await put_evaluation(client, mesa, created["id"], decision=decision)
    assert res.status_code == 200, res.text

    author = await user_id_of(db_session, "equipe@rr.test")
    rows = await notices(db_session, author)
    assert [row.event_type for row in rows] == ["rr_decision"]
    assert rows[0].app_id == await _rr_app_id(db_session)
    assert rows[0].actor_id == await user_id_of(db_session, "mesa@rr.test")
    assert [letter["to"] for letter in posted] == ["equipe@rr.test"]
    assert posted[0]["subject"] == rows[0].title

    request = (
        await db_session.execute(select(RRRequest).where(RRRequest.id == created["id"]))
    ).scalar_one()
    assert request.stage is stage


async def test_o_arrasto_manual_de_um_cartao_nao_avisa_ninguem(
    db_session, client, rrf_app, posted
) -> None:
    """O teste negativo que a DoD pede. A mesa pode arrastar um cartão que ninguém
    avaliou — e um cartão arrastado à mão não é uma decisão."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    await give_fund(db_session, created["id"])
    author = await user_id_of(db_session, "equipe@rr.test")
    before = len(await notices(db_session, author))
    posted.clear()

    for stage in ("analise", "aprovado", "revisar"):
        res = await client.post(
            f"{REQUESTS}/{created['id']}/move", json={"to": stage}, headers=mesa
        )
        assert res.status_code == 200, res.text

    assert len(await notices(db_session, author)) == before
    assert posted == []


async def test_regravar_a_mesma_decisao_nao_reavisa(db_session, client, rrf_app, posted) -> None:
    """Notas, comentários e a ata continuam editáveis; a decisão já foi dada uma vez."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    assert (
        await put_evaluation(client, mesa, created["id"], decision="declined")
    ).status_code == 200
    posted.clear()

    again = await put_evaluation(
        client, mesa, created["id"], decision="declined", comments="revisto"
    )

    assert again.status_code == 200, again.text
    author = await user_id_of(db_session, "equipe@rr.test")
    assert len(await notices(db_session, author)) == 1
    assert posted == []


# ——— a nota da mesa ——————————————————————————————————————————————————————————————


@pytest.mark.parametrize("decision", ["revise", "conditional"])
async def test_revisar_e_condicional_carregam_a_team_note(
    db_session, client, rrf_app, posted, decision
) -> None:
    """A única coisa que a mesa escreve e a equipe lê (GATE-03 D4). ``comments`` e a ata
    não saem da mesa, e este teste é onde isso é afirmado nos dois canais."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    posted.clear()

    res = await put_evaluation(
        client,
        mesa,
        created["id"],
        decision=decision,
        team_note="Refaçam o item 7 do orçamento.",
        comments="conversa interna da mesa",
    )
    assert res.status_code == 200, res.text

    author = await user_id_of(db_session, "equipe@rr.test")
    body = (await notices(db_session, author))[0].body
    assert "Refaçam o item 7 do orçamento." in body
    assert "conversa interna da mesa" not in body
    assert "Refaçam o item 7 do orçamento." in posted[0]["html"]
    assert "conversa interna da mesa" not in posted[0]["html"]


@pytest.mark.parametrize("note", [None, "", "   "])
async def test_uma_team_note_vazia_nao_vira_aviso_vazio(
    db_session, client, rrf_app, posted, note
) -> None:
    """Um corpo que termina num título sem nada embaixo lê-se como uma mesa que esqueceu
    de escrever — pior do que um aviso que só diz a decisão."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    posted.clear()

    payload: dict[str, object] = {"decision": "revise"}
    if note is not None:
        payload["team_note"] = note
    res = await put_evaluation(client, mesa, created["id"], **payload)
    assert res.status_code == 200, res.text

    author = await user_id_of(db_session, "equipe@rr.test")
    body = (await notices(db_session, author))[0].body
    assert body.strip() == body
    assert "\n" not in body
    assert "A note from the Resource Circle" not in posted[0]["html"]


async def test_aprovado_e_recusado_nao_carregam_a_nota(db_session, client, rrf_app, posted) -> None:
    """Só as duas decisões em que a equipe tem o que fazer é que carregam a nota."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    posted.clear()

    res = await put_evaluation(
        client, mesa, created["id"], decision="declined", team_note="uma nota qualquer"
    )
    assert res.status_code == 200, res.text

    author = await user_id_of(db_session, "equipe@rr.test")
    assert "uma nota qualquer" not in (await notices(db_session, author))[0].body
    assert "uma nota qualquer" not in posted[0]["html"]


# ——— a chegada ——————————————————————————————————————————————————————————————————


async def test_a_chegada_avisa_a_mesa_e_os_gestores_e_nao_a_equipe(
    db_session, client, rrf_app, posted
) -> None:
    """A outra ponta do laço (GATE-03 D6). O Gestor entra como destinatário e nada mais —
    nenhuma capacidade nova, e a lista sai de quem tem a porta do Painel."""
    team = await as_team(db_session, rrf_app)
    await as_mesa(db_session, rrf_app)
    await as_gestor(db_session, rrf_app)
    posted.clear()

    await submitted_request(client, team)

    for email in ("mesa@rr.test", "gestor@rr.test"):
        rows = await notices(db_session, await user_id_of(db_session, email))
        assert [row.event_type for row in rows] == ["rr_request_submitted"]
    assert sorted(letter["to"] for letter in posted) == ["gestor@rr.test", "mesa@rr.test"]
    assert await notices(db_session, await user_id_of(db_session, "equipe@rr.test")) == []


async def test_um_rascunho_ainda_em_edicao_nao_avisa_a_mesa(
    db_session, client, rrf_app, posted
) -> None:
    """A chegada acontece uma vez, quando o snapshot congela."""
    team = await as_team(db_session, rrf_app)
    await as_mesa(db_session, rrf_app)
    posted.clear()

    from tests.test_resource_requests.test_requests import create

    await create(client, team)

    assert await notices(db_session, await user_id_of(db_session, "mesa@rr.test")) == []
    assert posted == []


async def test_uma_conta_sem_papel_no_quadro_nao_recebe_a_chegada(
    db_session, client, rrf_app, posted
) -> None:
    """``board_watchers`` lê a capacidade de entrada do Painel, não *todo mundo*."""
    team = await as_team(db_session, rrf_app)
    outra = await make_user(db_session, email="outra-equipe@rr.test")
    await grant(db_session, outra, rrf_app, "equipe")
    await auth_header(db_session, outra)
    posted.clear()

    await submitted_request(client, team)

    assert await notices(db_session, outra.id) == []
    assert posted == []


# ——— a transação fecha antes do correio ——————————————————————————————————————————


async def test_uma_falha_de_email_nao_reverte_a_decisao(
    db_session, client, rrf_app, monkeypatch
) -> None:
    """A DoD, literalmente. ``send_email`` já engole uma queda do provedor; aqui a falha é
    forçada acima dele, no caminho inteiro do correio, e a decisão continua de pé."""

    async def _explode(**_kwargs: object) -> bool:
        raise RuntimeError("o provedor caiu")

    monkeypatch.setattr("app.services.resource_request._notices.send_email", _explode)

    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    await give_fund(db_session, created["id"])

    res = await put_evaluation(client, mesa, created["id"], decision="approved")

    assert res.status_code == 200, res.text
    assert res.json()["decision"] == "approved"
    request = (
        await db_session.execute(select(RRRequest).where(RRRequest.id == created["id"]))
    ).scalar_one()
    assert request.stage is RRStage.APROVADO
    author = await user_id_of(db_session, "equipe@rr.test")
    assert len(await notices(db_session, author)) == 1


async def test_o_aviso_in_app_entra_na_transacao_da_decisao(
    db_session, client, rrf_app, posted, monkeypatch
) -> None:
    """O outro lado da reconciliação: ``create_notification`` não pode commitar sozinho no
    meio da transação da decisão. Se ele o fizesse, o aviso sobreviveria a uma decisão que
    falhou depois dele."""
    calls: list[bool] = []

    async def _spy(*args: object, **kwargs: object):
        calls.append(bool(kwargs.get("commit", True)))
        return await create_notification(*args, **kwargs)  # type: ignore[arg-type]

    # The package re-exports ``notify_decision`` under the module's own name, so the
    # dotted-string form of ``setattr`` resolves the function and not the module.
    monkeypatch.setattr(
        import_module("app.services.resource_request.notify_decision"),
        "create_notification",
        _spy,
    )

    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    assert (await put_evaluation(client, mesa, created["id"], decision="revise")).status_code == 200
    assert calls == [False]


# ——— a chave do app ——————————————————————————————————————————————————————————————


def test_a_chave_daqui_e_a_do_modulo() -> None:
    """``get_rr_app_id`` nomeia a chave uma segunda vez, como os dois irmãos dele fazem.
    Isto é o que impede as duas de divergirem em silêncio."""
    assert RR_APP_KEY == APP_KEY


def test_as_quatro_decisoes_tem_copy() -> None:
    """Uma decisão nova sem texto seria um ``KeyError`` no meio da gravação da Parte C."""
    assert set(DECISION_COPY) == set(RRDecision)


async def _rr_app_id(db_session) -> str:
    from app.services.notifications.get_rr_app_id import get_rr_app_id

    return await get_rr_app_id(db_session)
