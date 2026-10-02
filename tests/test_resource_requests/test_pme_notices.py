"""Os avisos do formulário no sino do PME — BE-21 (OBT-541), pelas rotas do próprio formulário.

A decisão da mesa chega a quem iniciou o pedido e a chegada chega ao Admin e ao Gestor, agora
também no app ``shema``, que é o que o sino do PME lê. O aviso leva o nome registrado e a
etapa, e nada da avaliação (GATE-03 D4). Um pedido sem quem o iniciou — o link externo da
OBT-537 — não toca o sino, e o e-mail segue saindo.

Estes testes semeiam o app ``shema``; os da BE-13 (``test_notifications.py``) não o semeiam, e
continuarem verdes é a prova de que a metade do PME não muda nada no formulário sem ele. As
propriedades do lado Shemá — quem recebe por papel, a assinatura, o painel — estão em
``tests/test_shema/test_request_notices.py``.
"""

from __future__ import annotations

import json
from datetime import date
from importlib import import_module

import pytest
from sqlalchemy import select

from app.core.rate_limit import limiter
from app.db.models.auth import User
from app.db.models.notification import Notification
from app.db.models.resource_request import RRRequest, RRStage
from app.db.models.shema_notification import ShemaRequestNotice
from app.services.notifications.create_notification import create_notification
from app.services.notifications.get_shema_app_id import SHEMA_APP_KEY
from app.services.shema import list_notification_panel, region_scope
from tests.baker import make_user
from tests.test_resource_requests.conftest import grant, make_membership
from tests.test_resource_requests.test_evaluations import (
    REQUESTS,
    as_gestor,
    decidable,
    endorse,
    give_fund,
    put_evaluation,
)
from tests.test_resource_requests.test_link_requests import holder
from tests.test_resource_requests.test_requests import as_mesa, as_team, draft

#: As chaves de avaliação, nas duas grafias em que poderiam vazar — a da coluna e a do fio.
EVALUATION_KEYS = {
    "scores",
    "comments",
    "evaluator_id",
    "evaluatorId",
    "attendees",
    "team_note",
    "teamNote",
    "total",
    "decision",
}

#: Exatamente o que uma entrada do painel responde, e nada mais.
ENTRY_KEYS = {
    "id",
    "kind",
    "title",
    "body",
    "urgent",
    "projectId",
    "region",
    "createdAt",
    "isRead",
    "requestName",
    "requestStage",
    # OBT-559: what a project notice says, for the console to word; ``None`` on a request notice.
    "facts",
}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """O link verifica o código numa rota pública com limite por endereço."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
def posted(monkeypatch) -> list[dict[str, str]]:
    """Toda carta que o formulário entrega ao ``send_email``, em ordem."""
    sent: list[dict[str, str]] = []

    async def _record(*, to: str, subject: str, html: str, from_name: str | None = None) -> bool:
        sent.append({"to": to, "subject": subject, "html": html})
        return True

    monkeypatch.setattr("app.services.resource_request._notices.send_email", _record)
    return sent


async def user_of(db_session, email: str) -> User:
    return (await db_session.execute(select(User).where(User.email == email))).scalar_one()


async def pme_notices(db_session, shema_app, user_id: str) -> list[Notification]:
    """As linhas do app ``shema`` de uma pessoa — nunca as do formulário."""
    rows = await db_session.execute(
        select(Notification)
        .where(Notification.user_id == user_id, Notification.app_id == shema_app.id)
        .order_by(Notification.created_at)
    )
    return list(rows.scalars().all())


async def all_pme_notices(db_session, shema_app) -> list[Notification]:
    rows = await db_session.execute(select(Notification).where(Notification.app_id == shema_app.id))
    return list(rows.scalars().all())


async def panel_of(db_session, user: User) -> list[dict]:
    """O painel da pessoa, serializado como o fio o responde."""
    scope = await region_scope(db_session, user, SHEMA_APP_KEY)
    entries = await list_notification_panel(
        db_session, scope, user, app_key=SHEMA_APP_KEY, today=date.today()
    )
    return [entry.model_dump(mode="json", by_alias=True) for entry in entries]


async def pme_admin(db_session, shema_app, email: str = "admin@rr.test") -> User:
    user = await make_user(db_session, email=email)
    await grant(db_session, user, shema_app, "admin")
    return user


async def request_row(db_session, request_id: str) -> RRRequest:
    return (
        await db_session.execute(select(RRRequest).where(RRRequest.id == request_id))
    ).scalar_one()


# ——— a decisão toca o sino de quem iniciou ————————————————————————————————————————


@pytest.mark.parametrize(
    ("decision", "stage"),
    [
        ("approved", RRStage.APROVADO),
        ("conditional", RRStage.CONDICIONAL),
        ("revise", RRStage.REVISAR),
        ("declined", RRStage.RECUSADO),
    ],
)
async def test_a_decisao_toca_o_sino_do_pme_de_quem_iniciou(
    db_session, client, rrf_app, shema_app, posted, decision, stage
) -> None:
    """As quatro decisões, como no formulário, e a etapa que cada uma implica."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await decidable(db_session, client, team)
    await give_fund(db_session, created["id"])

    res = await put_evaluation(client, mesa, created["id"], decision=decision)
    assert res.status_code == 200, res.text

    request = await request_row(db_session, created["id"])
    starter = await user_of(db_session, "equipe@rr.test")
    assert request.started_by == starter.id
    rows = await pme_notices(db_session, shema_app, starter.id)
    assert [row.event_type for row in rows] == ["rr_decision"]

    detail = await db_session.get(ShemaRequestNotice, rows[0].id)
    assert detail is not None
    assert (detail.project_id, detail.stage) == (request.shema_project_id, stage.value)
    assert detail.request_name == request.reg_name.strip()

    [entry] = await panel_of(db_session, starter)
    assert entry["kind"] == "requestDecision"
    assert entry["projectId"] == request.shema_project_id
    assert entry["requestName"] == request.reg_name.strip()
    assert entry["requestStage"] == stage.value


async def test_a_decisao_nao_toca_o_sino_de_mais_ninguem(
    db_session, client, rrf_app, shema_app, posted
) -> None:
    """Nem a mesa que decidiu, nem o Gestor, nem o Admin, nem outro membro do projeto."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await decidable(db_session, client, team)
    request = await request_row(db_session, created["id"])
    await as_gestor(db_session, rrf_app)
    admin = await pme_admin(db_session, shema_app)
    colleague = await make_user(db_session, email="colega@rr.test")
    assert request.shema_project_id is not None
    await make_membership(db_session, colleague, request.shema_project_id)
    before = {row.id for row in await all_pme_notices(db_session, shema_app)}

    res = await put_evaluation(client, mesa, created["id"], decision="declined")
    assert res.status_code == 200, res.text

    new = [row for row in await all_pme_notices(db_session, shema_app) if row.id not in before]
    starter = await user_of(db_session, "equipe@rr.test")
    assert [row.user_id for row in new] == [starter.id]
    for email in ("mesa@rr.test", "gestor@rr.test", "colega@rr.test"):
        other = await user_of(db_session, email)
        assert await pme_notices(db_session, shema_app, other.id) == []
    assert await pme_notices(db_session, shema_app, admin.id) == []


async def test_o_arrasto_manual_nao_toca_o_sino_do_pme(
    db_session, client, rrf_app, shema_app, posted
) -> None:
    """A invariante da BE-13 com o app ``shema`` presente: o gatilho é a Parte C, nunca a coluna."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await decidable(db_session, client, team)
    await give_fund(db_session, created["id"])
    before = len(await all_pme_notices(db_session, shema_app))

    for stage in ("analise", "aprovado", "revisar"):
        res = await client.post(
            f"{REQUESTS}/{created['id']}/move", json={"to": stage}, headers=mesa
        )
        assert res.status_code == 200, res.text

    assert len(await all_pme_notices(db_session, shema_app)) == before


async def test_o_aviso_do_pme_entra_na_transacao_da_decisao_e_da_chegada(
    db_session, client, rrf_app, shema_app, posted, monkeypatch
) -> None:
    """A metade do PME é encenada com ``commit=False``, como a do formulário: um aviso que
    commitasse sozinho sobreviveria a uma gravação que falhou depois dele."""
    calls: list[bool] = []

    async def _spy(*args: object, **kwargs: object):
        calls.append(bool(kwargs.get("commit", True)))
        return await create_notification(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        import_module("app.services.shema._request_notices"), "create_notification", _spy
    )

    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await pme_admin(db_session, shema_app)
    created = await decidable(db_session, client, team)
    assert calls == [False]

    assert (await put_evaluation(client, mesa, created["id"], decision="revise")).status_code == 200
    assert calls == [False, False]


# ——— a chegada toca o sino do Admin e do Gestor ————————————————————————————————————


async def test_a_chegada_toca_o_sino_do_admin_e_do_gestor(
    db_session, client, rrf_app, shema_app, posted
) -> None:
    """O Admin pela concessão no ``shema``, o Gestor pela do formulário — e a mesa, que é
    avisada no formulário, não é avisada no PME."""
    admin = await pme_admin(db_session, shema_app)
    await as_gestor(db_session, rrf_app)
    await as_mesa(db_session, rrf_app)
    team = await as_team(db_session, rrf_app)

    created = await decidable(db_session, client, team)

    request = await request_row(db_session, created["id"])
    gestor = await user_of(db_session, "gestor@rr.test")
    for person in (admin, gestor):
        rows = await pme_notices(db_session, shema_app, person.id)
        assert [row.event_type for row in rows] == ["rr_request_submitted"]
        detail = await db_session.get(ShemaRequestNotice, rows[0].id)
        assert detail is not None
        assert (detail.project_id, detail.stage) == (request.shema_project_id, "triagem")
        [entry] = await panel_of(db_session, person)
        assert entry["kind"] == "requestArrival"
        assert entry["requestStage"] == "triagem"

    for email in ("mesa@rr.test", "equipe@rr.test"):
        nobody = await user_of(db_session, email)
        assert await pme_notices(db_session, shema_app, nobody.id) == []


# ——— o link externo: sem sino, e o e-mail continua ————————————————————————————————


async def test_um_pedido_de_link_nao_toca_o_sino_e_o_email_sai(
    db_session, client, rrf_app, shema_app, posted
) -> None:
    """O pedido pelo link do Admin (OBT-537), de ponta a ponta: sem conta e sem projeto, ele
    não toca o sino do PME nem na chegada nem na decisão — e as cartas saem como antes: a
    chegada para o Gestor e o recibo para o link; a decisão para o endereço do link."""
    await pme_admin(db_session, shema_app, email="admin-pme@rr.test")
    await as_gestor(db_session, rrf_app)
    _issuer, _link, headers = await holder(db_session, client, email="equipe@fora.org")
    started = (await client.post(REQUESTS, json=draft(), headers=headers)).json()

    submitted = await client.post(f"{REQUESTS}/{started['id']}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    request = await request_row(db_session, started["id"])
    assert (request.started_by, request.shema_project_id) == (None, None)
    assert await all_pme_notices(db_session, shema_app) == []
    assert {"gestor@rr.test", "equipe@fora.org"} <= {letter["to"] for letter in posted}

    await endorse(db_session, started["id"])
    await give_fund(db_session, started["id"])
    posted.clear()
    res = await put_evaluation(
        client, await as_mesa(db_session, rrf_app), started["id"], decision="approved"
    )

    assert res.status_code == 200, res.text
    assert await all_pme_notices(db_session, shema_app) == []
    assert [letter["to"] for letter in posted] == ["equipe@fora.org"]


async def test_um_pedido_sem_quem_iniciou_nao_toca_o_sino_mesmo_fora_do_link(
    db_session, client, rrf_app, shema_app, posted
) -> None:
    """A regra lê as colunas, não a origem: um pedido sem ``started_by`` — o seed deixa assim —
    não toca o sino na decisão, e a carta do formulário sai para ``created_by`` como hoje."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await pme_admin(db_session, shema_app)
    created = await decidable(db_session, client, team)
    request = await request_row(db_session, created["id"])
    request.started_by = None
    await db_session.commit()
    before = len(await all_pme_notices(db_session, shema_app))
    posted.clear()

    res = await put_evaluation(client, mesa, created["id"], decision="revise")
    assert res.status_code == 200, res.text

    assert len(await all_pme_notices(db_session, shema_app)) == before
    assert [letter["to"] for letter in posted] == ["equipe@rr.test"]


# ——— o teto da GATE-03 D4 ———————————————————————————————————————————————————————————


async def test_nenhum_campo_da_avaliacao_chega_ao_sino_do_pme(
    db_session, client, rrf_app, shema_app, posted
) -> None:
    """A caixa da DoD, provada no payload: um ``revise`` com recado, comentário, notas e ata
    marcados, e nada disso — nem quem avaliou — no aviso de quem iniciou."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    evaluator = await user_of(db_session, "mesa@rr.test")
    created = await decidable(db_session, client, team)

    res = await put_evaluation(
        client,
        mesa,
        created["id"],
        decision="revise",
        comments="COMENTARIO-SIGILOSO-DA-MESA",
        team_note="RECADO-DA-MESA-PARA-A-EQUIPE",
        attendees=[evaluator.id],
    )
    assert res.status_code == 200, res.text

    starter = await user_of(db_session, "equipe@rr.test")
    [row] = await pme_notices(db_session, shema_app, starter.id)
    assert row.actor_id is None
    detail = await db_session.get(ShemaRequestNotice, row.id)
    assert detail is not None
    assert set(ShemaRequestNotice.__table__.columns.keys()) == {
        "notification_id",
        "project_id",
        "request_name",
        "stage",
    }

    [entry] = await panel_of(db_session, starter)
    assert set(entry) == ENTRY_KEYS
    assert entry["facts"] is None
    assert not EVALUATION_KEYS & set(entry)

    stored = " ".join([row.title, row.body, detail.request_name, detail.stage])
    wire = json.dumps(entry)
    for secret in ("COMENTARIO-SIGILOSO-DA-MESA", "RECADO-DA-MESA-PARA-A-EQUIPE", evaluator.id):
        assert secret not in stored
        assert secret not in wire

    # O recado continua chegando à equipe — pelo formulário, que é o canal dele (BE-13).
    assert "RECADO-DA-MESA-PARA-A-EQUIPE" in posted[-1]["html"]


async def test_o_ponteiro_para_a_ficha_so_vai_a_quem_alcanca_o_projeto(
    db_session, client, rrf_app, shema_app, posted
) -> None:
    """O id de um projeto é o slug da exportação, ``<língua>-<lugar>``; quem não alcança o
    projeto não aprende que ele existe (§6.1). O Gestor e o Admin não alcançam região: a
    chegada lhes diz o nome e a etapa, e não para onde ela aponta."""
    admin = await pme_admin(db_session, shema_app)
    await as_gestor(db_session, rrf_app)
    team = await as_team(db_session, rrf_app)
    await decidable(db_session, client, team)

    for person in (admin, await user_of(db_session, "gestor@rr.test")):
        [entry] = await panel_of(db_session, person)
        assert entry["kind"] == "requestArrival"
        assert entry["projectId"] is None
        assert entry["requestName"] is not None
