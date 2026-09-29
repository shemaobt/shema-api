"""The card projection, and who reads a project's requests from the PME — BE-24 (OBT-536).

One shape, ``RequestCardOut``, for two readers: the PME's project page
(``GET /projects/{id}/requests``) and the form's tracking list (``GET /requests/cards``). The
ceiling is GATE-03 D4's — status and nothing else — and it is proven here on the payload.
"""

from __future__ import annotations

import pydantic
import pytest

from app.db.models.resource_request import RRDecision
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from app.models.resource_request import RequestCardOut
from app.services.shema import set_region_scope
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant, make_membership
from tests.test_resource_requests.test_requests import REQUESTS, _decide, draft

PROJECT = "kadiweu"
CARDS = f"{REQUESTS}/cards"
EVALUATION_KEYS = {"scores", "comments", "evaluator_id", "attendees", "team_note", "total"}


def project_cards(project_id: str = PROJECT) -> str:
    return f"/api/resource-requests/projects/{project_id}/requests"


@pytest.fixture()
async def project(db_session) -> ShemaProject:
    row = ShemaProject(id=PROJECT, language_name="Kadiwéu", region_key=ShemaRegionKey.SOUTH_AMERICA)
    db_session.add(row)
    await db_session.commit()
    return row


async def member(db_session, email: str, project_id: str = PROJECT):
    user = await make_user(db_session, email=email, display_name=email.split("@")[0].title())
    await make_membership(db_session, user, project_id)
    return user, await auth_header(db_session, user)


async def pme_role(db_session, shema_app, email: str, role: str, regions=None):
    user = await make_user(db_session, email=email)
    await grant(db_session, user, shema_app, role)
    if regions is not None:
        await set_region_scope(db_session, user.id, regions)
    return await auth_header(db_session, user)


async def form_role(db_session, rrf_app, email: str, role: str):
    user = await make_user(db_session, email=email)
    await grant(db_session, user, rrf_app, role)
    return await auth_header(db_session, user)


async def one_sent_one_open(client, db_session):
    """A submitted, decided request and the project's open instance beside it."""
    ana, ana_h = await member(db_session, "ana@cards.test")
    sent = (await client.post(REQUESTS, json=draft(), headers=ana_h)).json()
    await client.post(f"{REQUESTS}/{sent['id']}/submit", headers=ana_h)
    await _decide(db_session, sent["id"], RRDecision.APPROVED)
    opened = (await client.post(REQUESTS, json=draft(), headers=ana_h)).json()
    return ana, ana_h, sent, opened


# ——— who reads a project's requests ————————————————————————————————————————————————


@pytest.mark.parametrize("role", ["mesa", "gestor"])
async def test_the_board_reads_any_projects_cards(
    db_session, client, rrf_app, shema_app, project, role: str
) -> None:
    await one_sent_one_open(client, db_session)
    headers = await form_role(db_session, rrf_app, f"{role}@cards.test", role)

    res = await client.get(project_cards(), headers=headers)

    assert res.status_code == 200, res.text
    assert len(res.json()) == 2


async def test_the_pme_admin_reads_any_projects_cards(
    db_session, client, rrf_app, shema_app, project
) -> None:
    """The Admin of OBT-522 is one role for two apps; holding it in the PME is enough."""
    await one_sent_one_open(client, db_session)
    headers = await pme_role(db_session, shema_app, "admin@cards.test", "admin")

    res = await client.get(project_cards(), headers=headers)

    assert res.status_code == 200, res.text


@pytest.mark.parametrize(
    ("role", "regions"),
    [
        ("coordinator", [ShemaRegionKey.SOUTH_AMERICA]),
        ("resourceCircle", [ShemaRegionKey.SOUTH_AMERICA]),
        ("globalStrategist", None),
    ],
)
async def test_a_pme_role_whose_scope_reaches_the_project_reads_it(
    db_session, client, rrf_app, shema_app, project, role: str, regions
) -> None:
    """The reader this route exists for holds no role in the form — the module's own door
    would refuse them, which is why the route asks for a session and nothing else."""
    await one_sent_one_open(client, db_session)
    headers = await pme_role(db_session, shema_app, f"{role}@cards.test", role, regions)

    res = await client.get(project_cards(), headers=headers)

    assert res.status_code == 200, res.text
    assert len(res.json()) == 2


async def test_a_member_reads_their_projects_cards(
    db_session, client, rrf_app, shema_app, project
) -> None:
    _ana, _ana_h, sent, opened = await one_sent_one_open(client, db_session)
    _bia, bia_h = await member(db_session, "bia@cards.test")

    res = await client.get(project_cards(), headers=bia_h)

    assert res.status_code == 200, res.text
    assert {card["id"] for card in res.json()} == {sent["id"], opened["id"]}


async def test_a_coordinator_of_another_region_gets_404(
    db_session, client, rrf_app, shema_app, project
) -> None:
    await one_sent_one_open(client, db_session)
    headers = await pme_role(
        db_session, shema_app, "longe@cards.test", "coordinator", [ShemaRegionKey.NORTH_AMERICA]
    )

    res = await client.get(project_cards(), headers=headers)

    assert res.status_code == 404, res.text


async def test_a_member_of_another_project_gets_404(
    db_session, client, rrf_app, shema_app, project
) -> None:
    await one_sent_one_open(client, db_session)
    db_session.add(
        ShemaProject(id="fataluku", language_name="Fataluku", region_key=ShemaRegionKey.OTHER)
    )
    await db_session.commit()
    _caio, caio_h = await member(db_session, "caio@cards.test", "fataluku")

    res = await client.get(project_cards(), headers=caio_h)

    assert res.status_code == 404, res.text


async def test_an_account_with_nothing_gets_404(
    db_session, client, rrf_app, shema_app, project
) -> None:
    await one_sent_one_open(client, db_session)
    nobody = await make_user(db_session, email="ninguem@cards.test")

    res = await client.get(project_cards(), headers=await auth_header(db_session, nobody))

    assert res.status_code == 404, res.text


async def test_a_project_that_does_not_exist_is_the_same_404(
    db_session, client, rrf_app, shema_app, project
) -> None:
    """Missing and out of reach read alike, so a probe learns nothing about which ids exist."""
    headers = await form_role(db_session, rrf_app, "mesa@cards.test", "mesa")

    res = await client.get(project_cards("nao-existe"), headers=headers)

    assert res.status_code == 404, res.text


async def test_no_session_is_refused(client, rrf_app, shema_app, project) -> None:
    assert (await client.get(project_cards())).status_code == 401


# ——— what a card carries ————————————————————————————————————————————————————————


async def test_a_card_is_status_and_nothing_of_the_evaluation(
    db_session, client, rrf_app, shema_app, project
) -> None:
    """The ceiling proven on the payload: the keys are the projection's and no evaluation
    field is among them, decided request included."""
    _ana, _ana_h, sent, _opened = await one_sent_one_open(client, db_session)
    headers = await form_role(db_session, rrf_app, "mesa@cards.test", "mesa")

    cards = {
        card["id"]: card for card in (await client.get(project_cards(), headers=headers)).json()
    }

    decided = cards[sent["id"]]
    assert set(decided) == set(RequestCardOut.model_fields)
    assert not EVALUATION_KEYS & set(decided)
    assert decided["decision"] == "approved"
    assert decided["open"] is False
    assert decided["started_by_name"] is None
    assert decided["reg_name"] == draft()["fields"]["reg_name"]
    assert decided["amount_requested"] == "1200.00"


def test_the_projection_refuses_a_field_of_the_evaluation() -> None:
    """``extra="forbid"`` is the guard that holds when a later change tries to widen it."""
    with pytest.raises(pydantic.ValidationError):
        RequestCardOut.model_validate(
            {
                "id": "x",
                "reg_name": "",
                "request_type": "traducao",
                "amount_requested": None,
                "currency": "BRL",
                "stage": "triagem",
                "created_at": "2026-09-29T00:00:00Z",
                "submitted_at": None,
                "endorsed": False,
                "decision": None,
                "open": True,
                "can_edit": False,
                "started_by_name": None,
                "scores": [5, 5, 5, 5, 5, 5],
            }
        )


async def test_the_open_instance_says_who_is_filling_it_in(
    db_session, client, rrf_app, shema_app, project
) -> None:
    """What the PME's *Solicitar recurso* button needs: *Iniciar* or *em preenchimento por X*,
    and whether this caller is the X."""
    _ana, ana_h, _sent, opened = await one_sent_one_open(client, db_session)
    _bia, bia_h = await member(db_session, "bia@cards.test")

    as_ana = {c["id"]: c for c in (await client.get(project_cards(), headers=ana_h)).json()}
    as_bia = {c["id"]: c for c in (await client.get(project_cards(), headers=bia_h)).json()}

    assert as_ana[opened["id"]]["open"] is True
    assert as_ana[opened["id"]]["started_by_name"] == "Ana"
    assert as_ana[opened["id"]]["can_edit"] is True
    assert as_bia[opened["id"]]["can_edit"] is False
    assert as_bia[opened["id"]]["decision"] is None


async def test_a_cancelled_instance_is_not_a_card(
    db_session, client, rrf_app, shema_app, project
) -> None:
    _ana, ana_h, _sent, opened = await one_sent_one_open(client, db_session)
    await client.post(f"{REQUESTS}/{opened['id']}/cancel", headers=ana_h)

    ids = {c["id"] for c in (await client.get(project_cards(), headers=ana_h)).json()}

    assert opened["id"] not in ids


# ——— one projection, two readers ———————————————————————————————————————————————


async def test_the_tracking_list_serves_the_same_projection(
    db_session, client, rrf_app, shema_app, project
) -> None:
    """``GET /requests/cards`` and the PME's route answer the same card for the same request."""
    _ana, ana_h, sent, opened = await one_sent_one_open(client, db_session)

    listed = {c["id"]: c for c in (await client.get(CARDS, headers=ana_h)).json()}
    for_project = {c["id"]: c for c in (await client.get(project_cards(), headers=ana_h)).json()}

    assert listed.keys() == {sent["id"], opened["id"]}
    assert listed == for_project


async def test_the_tracking_list_keeps_the_forms_scope(
    db_session, client, rrf_app, shema_app, project
) -> None:
    """The cards list is ``list_requests``' rows: another team's request is not among them."""
    await one_sent_one_open(client, db_session)
    db_session.add(
        ShemaProject(id="fataluku", language_name="Fataluku", region_key=ShemaRegionKey.OTHER)
    )
    await db_session.commit()
    _caio, caio_h = await member(db_session, "caio@cards.test", "fataluku")

    res = await client.get(CARDS, headers=caio_h)

    assert res.status_code == 200, res.text
    assert res.json() == []
