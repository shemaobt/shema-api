"""A sensitive project's cards name nothing to whoever reads the project redacted — OBT-688.

A-02 of INT-12's adversarial pass (6/nov/2026): ``GET /projects/{id}/requests`` handed the OBT Lab
the A0 and the starter of every request of a sensitive project, while the PME's ficha of the same
project gave it ``languageName: "africa"``. The A0 is the team's own text and in practice names
the language; the starter is a person. **Daniel's decision, 6/nov/2026: redact, do not refuse.**

The matrix is the Rastro's (``adv-A01-matriz-papel-rota.json``), role by role: the OBT Lab reads
the cards with the PME's generic name and no starter; the coordination of the region, the Resource
Circle (OBT-571), the mesa, the Gestor, the Admin, the platform admin and a member of the project
read them whole; a coordinator of another region and an account with nothing still get the 404.
A project that is not sensitive changes nothing, and the two card lists of the form
(``/requests``, ``/requests/cards``) keep their own door, which the OBT Lab does not pass.
"""

from __future__ import annotations

import pytest

from app.db.models.resource_request import RRDecision
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from app.services.shema import set_region_scope
from tests.baker import make_user
from tests.resource_request_harness import (
    REQUESTS,
    decide,
    draft,
    form_role,
    member,
    pme_role,
    project_cards,
)
from tests.test_resource_requests.conftest import auth_header, grant

SAIDI = "saidi"
GENERIC = "Projeto sensível — África"
AFRICA = [ShemaRegionKey.AFRICA]
#: What a redacted card still says — everything of the journey and the instance but the two names.
JOURNEY = {
    "id",
    "request_type",
    "amount_requested",
    "currency",
    "stage",
    "created_at",
    "submitted_at",
    "endorsed",
    "decision",
    "open",
    "can_edit",
    "revision_of_id",
}


@pytest.fixture()
async def saidi(db_session) -> ShemaProject:
    """A project whose place is withheld, in Africa."""
    row = ShemaProject(
        id=SAIDI,
        language_name="Árabe Saídi",
        region_key=ShemaRegionKey.AFRICA,
        sensitive_country=True,
    )
    db_session.add(row)
    await db_session.commit()
    return row


async def two_cards(client, db_session, project_id: str = SAIDI):
    """A submitted, approved request and an open instance beside it, both by Ana, a member."""
    _ana, ana_h = await member(db_session, f"ana@{project_id}.test", project_id)
    sent = (
        await client.post(REQUESTS, json=named("Saídi — Novo Testamento"), headers=ana_h)
    ).json()
    await client.post(f"{REQUESTS}/{sent['id']}/submit", headers=ana_h)
    await decide(db_session, sent["id"], RRDecision.APPROVED)
    opened = (await client.post(REQUESTS, json=named("Saídi — fase 2"), headers=ana_h)).json()
    return sent, opened


def named(reg_name: str) -> dict[str, object]:
    payload = draft()
    payload["fields"]["reg_name"] = reg_name  # type: ignore[index]
    return payload


async def cards(client, headers, project_id: str = SAIDI) -> dict[str, dict]:
    res = await client.get(project_cards(project_id), headers=headers)
    assert res.status_code == 200, res.text
    return {card["id"]: card for card in res.json()}


def names_whole(by_id: dict[str, dict], sent: dict, opened: dict) -> None:
    assert by_id[sent["id"]]["reg_name"] == "Saídi — Novo Testamento"
    assert by_id[opened["id"]]["reg_name"] == "Saídi — fase 2"
    assert by_id[opened["id"]]["started_by_name"] == "Ana"
    assert by_id[sent["id"]]["started_by_name"] is None, "a submitted request names nobody"


# ——— the reader of the region ———————————————————————————————————————————————————


async def test_the_obt_lab_reads_the_journey_with_the_generic_name_and_no_starter(
    db_session, client, rrf_app, shema_app, saidi
) -> None:
    """**The DoD.** The reader the PME hands ``readAs: "other"`` gets every card — the stage,
    the decision, the amount, whether an instance is open — with the A0 the PME prints for the
    project and nobody named as its starter."""
    sent, opened = await two_cards(client, db_session)
    obtlab = await pme_role(db_session, shema_app, "obtlab@rr.test", "obtLab", AFRICA)
    coord = await pme_role(db_session, shema_app, "coord@rr.test", "coordinator", AFRICA)

    redacted = await cards(client, obtlab)
    whole = await cards(client, coord)

    assert set(redacted) == {sent["id"], opened["id"]}
    for card in redacted.values():
        assert card["reg_name"] == GENERIC
        assert card["started_by_name"] is None
        assert "Saídi" not in str(card) and "Ana" not in str(card)
    for id_, card in redacted.items():
        assert {k: card[k] for k in JOURNEY} == {k: whole[id_][k] for k in JOURNEY}
    assert redacted[sent["id"]]["decision"] == "approved"
    assert redacted[opened["id"]]["open"] is True


async def test_the_generic_name_is_the_public_name_when_coordination_registered_one(
    db_session, client, rrf_app, shema_app, saidi
) -> None:
    """The same name the ficha shows that reader (OBT-560): the public name over the region."""
    saidi.public_language_name = "Projeto Nilo"
    await db_session.commit()
    await two_cards(client, db_session)
    obtlab = await pme_role(db_session, shema_app, "obtlab@rr.test", "obtLab", AFRICA)

    by_id = await cards(client, obtlab)

    assert {card["reg_name"] for card in by_id.values()} == {"Projeto Nilo"}


async def test_a_project_that_is_not_sensitive_changes_nothing(
    db_session, client, rrf_app, shema_app
) -> None:
    db_session.add(
        ShemaProject(id="makua", language_name="Makua", region_key=ShemaRegionKey.AFRICA)
    )
    await db_session.commit()
    sent, opened = await two_cards(client, db_session, "makua")
    obtlab = await pme_role(db_session, shema_app, "obtlab@rr.test", "obtLab", AFRICA)

    names_whole(await cards(client, obtlab, "makua"), sent, opened)


# ——— the readers of the truth ——————————————————————————————————————————————————————


@pytest.mark.parametrize("role", ["coordinator", "resourceCircle"])
async def test_a_pme_reader_of_the_truth_in_the_region_reads_the_names(
    db_session, client, rrf_app, shema_app, saidi, role: str
) -> None:
    """``coordination`` and, since OBT-571, ``trusted`` — the PME's own two readers of the
    truth, decided by ``Readership.reader_of`` and not by this module."""
    sent, opened = await two_cards(client, db_session)
    headers = await pme_role(db_session, shema_app, f"{role}@rr.test", role, AFRICA)

    names_whole(await cards(client, headers), sent, opened)


@pytest.mark.parametrize("role", ["mesa", "gestor", "admin"])
async def test_the_board_roles_read_the_names(
    db_session, client, rrf_app, shema_app, saidi, role: str
) -> None:
    """They read the whole request through ``GET /requests/{id}`` already (OBT-571, OBT-568)."""
    sent, opened = await two_cards(client, db_session)
    headers = await form_role(db_session, rrf_app, f"{role}@rr.test", role)

    names_whole(await cards(client, headers), sent, opened)


async def test_the_platform_admin_reads_the_names(
    db_session, client, rrf_app, shema_app, saidi
) -> None:
    sent, opened = await two_cards(client, db_session)
    plataforma = await make_user(db_session, email="plataforma@rr.test", is_platform_admin=True)

    names_whole(await cards(client, await auth_header(db_session, plataforma)), sent, opened)


async def test_a_member_of_the_project_reads_the_names(
    db_session, client, rrf_app, shema_app, saidi
) -> None:
    """The team's own project: a teammate reads what Ana typed and who is filling it in."""
    sent, opened = await two_cards(client, db_session)
    _bia, bia_h = await member(db_session, "bia@rr.test", SAIDI)

    names_whole(await cards(client, bia_h), sent, opened)


async def test_a_member_who_is_also_the_obt_lab_of_the_region_reads_the_names(
    db_session, client, rrf_app, shema_app, saidi
) -> None:
    """Reaching the project by the region does not take away what the membership gives."""
    sent, opened = await two_cards(client, db_session)
    bia, bia_h = await member(db_session, "bia@rr.test", SAIDI)
    await grant(db_session, bia, shema_app, "obtLab")
    await set_region_scope(db_session, bia.id, AFRICA)

    names_whole(await cards(client, bia_h), sent, opened)


# ——— what did not move ———————————————————————————————————————————————————————————


async def test_a_coordinator_of_another_region_still_gets_404(
    db_session, client, rrf_app, shema_app, saidi
) -> None:
    await two_cards(client, db_session)
    sul = await pme_role(
        db_session, shema_app, "sul@rr.test", "coordinator", [ShemaRegionKey.SOUTH_AMERICA]
    )

    assert (await client.get(project_cards(SAIDI), headers=sul)).status_code == 404


async def test_an_account_with_nothing_still_gets_404(
    db_session, client, rrf_app, shema_app, saidi
) -> None:
    await two_cards(client, db_session)
    nobody = await make_user(db_session, email="ninguem@rr.test")

    res = await client.get(project_cards(SAIDI), headers=await auth_header(db_session, nobody))

    assert res.status_code == 404


async def test_the_forms_own_card_lists_keep_their_door(
    db_session, client, rrf_app, shema_app, saidi
) -> None:
    """``/requests`` and ``/requests/cards`` are the team's lists behind the module's door: the
    OBT Lab holds no role in the form and is refused, as the Rastro measured."""
    await two_cards(client, db_session)
    obtlab = await pme_role(db_session, shema_app, "obtlab@rr.test", "obtLab", AFRICA)

    assert (await client.get(REQUESTS, headers=obtlab)).status_code == 403
    assert (await client.get(f"{REQUESTS}/cards", headers=obtlab)).status_code == 403
