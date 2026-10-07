"""OBT-571: the Resource Circle reads everything — sensitive projects included — and edits nothing.

Karina, via Daniel, 6/oct/2026: *"o Resource Circle poderá ver tudo, mesmo os projetos em países
sensíveis, só não podem editar. O coordenador vê e edita. o Administrador vê e editar."* Daniel,
7/oct/2026: the *tudo* includes a team's **health** (his extension), and the **OBT Lab stays
redacted** (his decision; she listed the roles without naming it).

Three things are held here. The Circle, on a withheld project in its own scope, reads what the
coordination reads — the place, the base, the contacts, the reason, the real language name, the
four free-text fields, the needs' descriptions, the history's notes and the health — as a
``trusted`` reader, and is told how many were withheld. The Circle gains no write: every write
route it did not hold answers 403 to an account holding ``resourceCircle`` alone, and the fields
coordination writes are refused on the save. And the OBT Lab reads exactly what it read before.

No account here is an installation admin: they pass every guard, and a refusal asserted with one
would pass for the wrong reason.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
from sqlalchemy import select

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import (
    ShemaHealthLevel,
    ShemaNeedUrgency,
    ShemaRegionKey,
)
from app.db.models.shema_health import ShemaHealthAssessment
from app.db.models.shema_need import ShemaNeed
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user

PROJECTS = f"{PREFIX}/projects"
HERE = ShemaRegionKey.SOUTH_AMERICA
ELSEWHERE = ShemaRegionKey.AFRICA
WITHHELD_ID = "lingua-sigilosa"
CLEARED_ID = "lingua-aberta"

PLACE = "Terra Sigilosa, Vale Escondido"
BASE = "JOCUM Vale Escondido"
CONTACT = "+00 000 000 0001"
REASON = "motivo sigiloso"
NOTES = "NOTA-SIGILOSA a equipe mudou de vale"
HEALTH_NOTES = "SAUDE-SIGILOSA dois adoeceram"
STATUS = "STATUS-SIGILOSO atrasou"
SCOPE = "ESCOPO-SIGILOSO Marcos e Lucas"
NEED = "NECESSIDADE-SIGILOSA um gravador"
READING_NOTES = "LEITURA-SIGILOSA a equipe chorou"
SECRETS = (PLACE, BASE, CONTACT, REASON, NOTES, HEALTH_NOTES, STATUS, SCOPE, NEED, READING_NOTES)


async def _seed(db_session, project_id: str, *, sensitive: bool, region=HERE) -> ShemaProject:
    row = ShemaProject(
        id=project_id,
        language_name="Lingua Sigilosa" if sensitive else "Lingua Aberta",
        bridge_language="Portugues",
        location=PLACE if sensitive else "Campo Aberto",
        team=BASE,
        team_contact=CONTACT,
        sensitive_country=sensitive,
        sensitivity=REASON if sensitive else "",
        region_key=region,
        notes=NOTES,
        health_notes=HEALTH_NOTES,
        status_comments=STATUS,
        scope_details=SCOPE,
        health_emotional=ShemaHealthLevel.CRITICA,
        health_assessment_date=date(2026, 9, 10),
        health_assessor="Mentoria",
    )
    db_session.add(row)
    db_session.add(
        ShemaNeed(
            project_id=project_id,
            category="equipment",
            urgency=ShemaNeedUrgency.MEDIUM,
            description=NEED,
            prayer_shared=False,
        )
    )
    db_session.add(
        ShemaHealthAssessment(
            project_id=project_id,
            assessment_date=date(2026, 9, 10),
            assessor="Mentoria",
            emotional=ShemaHealthLevel.CRITICA,
            notes=READING_NOTES,
        )
    )
    await db_session.commit()
    return row


@pytest.fixture()
async def withheld(db_session) -> ShemaProject:
    return await _seed(db_session, WITHHELD_ID, sensitive=True)


@pytest.fixture()
async def cleared(db_session) -> ShemaProject:
    return await _seed(db_session, CLEARED_ID, sensitive=False)


async def _headers(db_session, shema_app, role: str, *, regions=(HERE,)) -> dict[str, str]:
    user = await make_scoped_user(
        db_session,
        shema_app,
        email=f"{role.lower()}-{'-'.join(r.value for r in regions)}@circulo.test",
        role_key=role,
        regions=list(regions),
    )
    return await auth_header(db_session, user)


@pytest.fixture()
async def circle(db_session, shema_app) -> dict[str, str]:
    return await _headers(db_session, shema_app, "resourceCircle")


@pytest.fixture()
async def lab(db_session, shema_app) -> dict[str, str]:
    return await _headers(db_session, shema_app, "obtLab")


def _leaks(text: str) -> list[str]:
    return [secret for secret in SECRETS if secret in text]


def _card(page: dict[str, Any], project_id: str) -> dict[str, Any]:
    return next(item for item in page["items"] if item["id"] == project_id)


# --- the Circle reads the truth ----------------------------------------------------------------


async def test_the_circle_reads_a_withheld_ficha_as_the_coordination_does(
    client, db_session, shema_app, withheld, circle
) -> None:
    """Every field OBT-528 and OBT-556 withheld from the Circle, read whole: the place and its
    flag, the base and the contact, the reason, the real name, the four free texts, the need's
    description and the reading's notes — beside ``readAs: trusted``, which says the truth is in
    hand and nothing of coordination's is this reader's to edit."""
    response = await client.get(f"{PROJECTS}/{WITHHELD_ID}", headers=circle)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["readAs"] == "trusted"
    assert body["locationWithheld"] is True
    assert body["sensitiveCountry"] is True
    assert body["location"] == PLACE
    assert body["ywamBase"] == BASE
    assert body["teamContact"] == CONTACT
    assert body["sensitivity"] == REASON
    assert body["languageName"] == "Lingua Sigilosa"
    assert body["languageNameWithheld"] is False
    assert (body["notes"], body["healthNotes"], body["statusComments"], body["scopeDetails"]) == (
        NOTES,
        HEALTH_NOTES,
        STATUS,
        SCOPE,
    )
    assert [need["description"] for need in body["needsItems"]] == [NEED]
    assert body["healthHistory"] is not None and len(body["healthHistory"]) == 1
    assert body["healthHistory"][0]["notes"] == READING_NOTES
    assert body["healthEmotional"] == "critica"

    coordination = await client.get(
        f"{PROJECTS}/{WITHHELD_ID}", headers=await _headers(db_session, shema_app, "coordinator")
    )
    theirs = {k: v for k, v in coordination.json().items() if k not in ("readAs", "etag")}
    mine = {k: v for k, v in body.items() if k not in ("readAs", "etag")}
    assert mine == theirs, "the Circle reads exactly what the coordination reads"
    assert coordination.json()["readAs"] == "coordination"


async def test_the_circle_reads_the_truth_on_the_card_and_is_told_how_many_were_withheld(
    client, withheld, cleared, circle
) -> None:
    """The Projetos screen: the withheld card carries the place, the base and the health, and
    the collection says how many were withheld — the notice GATE-04 gave the coordination, which
    the Circle reads too since it reads what the notice is about."""
    response = await client.get(PROJECTS, headers=circle)

    assert response.status_code == 200, response.text
    page = response.json()
    card = _card(page, WITHHELD_ID)
    assert card["readAs"] == "trusted"
    assert card["locationWithheld"] is True
    assert card["location"] == PLACE
    assert card["team"] == BASE
    assert card["healthEmotional"] == "critica"
    assert page["locationsWithheld"] == 1
    assert "sensitive" in page["counts"]["groups"]


async def test_the_circle_filters_and_sorts_by_health_and_by_sensitivity(
    client, withheld, cleared, circle
) -> None:
    """The filter, the order and the facet the Circle used to have ignored (OBT-553, OBT-556)
    answer it now, because the card they read carries the fields."""
    critical = (await client.get(PROJECTS, params={"health": "critica"}, headers=circle)).json()
    assert sorted(card["id"] for card in critical["items"]) == [CLEARED_ID, WITHHELD_ID]
    assert critical["counts"]["groups"]["health"]["critica"] == 2

    sensitive = (await client.get(PROJECTS, params={"sensitive": "yes"}, headers=circle)).json()
    assert [card["id"] for card in sensitive["items"]] == [WITHHELD_ID]

    by_health = (await client.get(PROJECTS, params={"sort": "health"}, headers=circle)).json()
    assert by_health["sort"] == "health"


async def test_the_circle_reads_the_truth_only_in_its_own_scope(
    client, db_session, shema_app, withheld
) -> None:
    """GATE-04's *cada um na sua região* holds for the Circle as it holds for the coordinator: a
    Circle scoped to another region reaches nothing here, and the one that reaches this region
    is ``trusted`` only in it."""
    elsewhere = await _headers(db_session, shema_app, "resourceCircle", regions=(ELSEWHERE,))

    response = await client.get(f"{PROJECTS}/{WITHHELD_ID}", headers=elsewhere)

    assert response.status_code == 404
    assert _leaks(response.text) == []


async def test_a_circle_who_also_coordinates_reads_as_coordination(
    client, db_session, shema_app, withheld
) -> None:
    """Region rows are per account: holding both roles, the account is coordination wherever it
    reaches — the second field never shadows the first."""
    from tests.test_shema.conftest import grant

    user = await make_scoped_user(
        db_session,
        shema_app,
        email="both@circulo.test",
        role_key="resourceCircle",
        regions=[HERE],
    )
    await grant(db_session, user, shema_app, "coordinator")

    response = await client.get(
        f"{PROJECTS}/{WITHHELD_ID}", headers=await auth_header(db_session, user)
    )

    assert response.json()["readAs"] == "coordination"


# --- the OBT Lab stays exactly as it was -----------------------------------------------------


async def test_the_obt_lab_still_reads_the_reduction(client, withheld, cleared, lab) -> None:
    """Daniel, 7/oct/2026: the OBT Lab stays redacted. ``other`` on the ficha and the card, the
    region in place of the place, no base, no contact, no reason, no free text, no need text, no
    reading notes, no count — and the health, which it reads as the audience it is."""
    ficha = (await client.get(f"{PROJECTS}/{WITHHELD_ID}", headers=lab)).json()
    page = (await client.get(PROJECTS, headers=lab)).json()

    assert ficha["readAs"] == "other"
    assert ficha["location"] == HERE.value
    assert ficha["ywamBase"] == ficha["teamContact"] == ficha["sensitivity"] == ""
    assert ficha["notes"] == ficha["healthNotes"] == ""
    assert ficha["statusComments"] == ficha["scopeDetails"] == ""
    assert [need["description"] for need in ficha["needsItems"]] == [""]
    assert ficha["healthHistory"][0]["notes"] == ""
    assert ficha["healthEmotional"] == "critica"
    assert _card(page, WITHHELD_ID)["readAs"] == "other"
    assert page["locationsWithheld"] is None
    assert "sensitive" not in page["counts"]["groups"]
    assert _leaks(json.dumps(ficha)) == []
    assert _leaks(json.dumps(_card(page, WITHHELD_ID))) == []


# --- the Circle gains no write ------------------------------------------------------------------

COORDINATION_WRITES = {
    "location": {"location": "Outro Lugar"},
    "sensitiveCountry": {"sensitiveCountry": False},
    "sensitivity": {"sensitivity": "outro motivo"},
    "publicLanguageName": {"publicLanguageName": "Outro Nome"},
    "team": {"team": "JOCUM Outra"},
    "teamContact": {"teamContact": "+00 000 000 0009"},
    "languageName": {"languageName": "Outra Lingua"},
    "notes": {"notes": "outra nota"},
    "statusComments": {"statusComments": "outro comentario"},
    "scopeDetails": {"scopeDetails": "outro escopo"},
    "pastoralInterventionName": {"pastoralInterventionName": "Pr. Outro"},
    "needsPastoralIntervention": {"needsPastoralIntervention": "sim"},
}


@pytest.mark.parametrize("field", list(COORDINATION_WRITES))
async def test_the_circle_reads_the_truth_and_may_not_write_it(
    client, db_session, withheld, circle, field
) -> None:
    """*Só não podem editar*: every field the Circle now reads on a withheld record that
    coordination alone writes — the place, the flag, the reason, the public name, the base, the
    contact, the real name, the free texts the save takes and the pastoral follow-up — is refused
    by name,
    and the record does not move."""
    response = await client.patch(
        f"{PROJECTS}/{WITHHELD_ID}",
        json=COORDINATION_WRITES[field],
        headers={**circle, "If-Match": '"1"'},
    )

    assert response.status_code == 403, response.text
    assert field in response.json()["detail"]
    row = (
        await db_session.execute(
            select(ShemaProject)
            .where(ShemaProject.id == WITHHELD_ID)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert (row.version, row.location, row.team, row.notes) == (1, PLACE, BASE, NOTES)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        (
            "POST",
            f"{PREFIX}/projects/{WITHHELD_ID}/health-assessments",
            {"date": "2026-10-01", "assessor": "x", "emotional": "boa", "questionSetVersion": 1},
        ),
        ("PUT", f"{PREFIX}/eten/credits/{WITHHELD_ID}/2026", {"credits": 1}),
        ("POST", f"{PREFIX}/intake-links", {"projectId": WITHHELD_ID}),
        ("POST", f"{PREFIX}/import/projects", [{"id": "x"}]),
        (
            "POST",
            f"{PREFIX}/meetings/log",
            {"meetingId": "bimestral_pi_campo", "scopeKey": HERE.value, "date": "2026-03-10"},
        ),
        (
            "PUT",
            f"{PREFIX}/regions/{HERE.value}/team",
            {"coordinator": None, "obtLab": None, "resourceCircle": None},
        ),
        ("POST", f"{PREFIX}/projects/{WITHHELD_ID}/members", {"userId": "x"}),
        ("POST", f"{PREFIX}/projects/{WITHHELD_ID}/confirm", {}),
        ("POST", f"{PREFIX}/projects/{WITHHELD_ID}/reject", {}),
        (
            "POST",
            f"{PREFIX}/access/grants",
            {"userId": "x", "appKey": "shema", "roleKey": "coordinator"},
        ),
        (
            "POST",
            f"{PREFIX}/access/invites",
            {"email": "x@x.test", "appKey": "shema", "roleKey": "coordinator"},
        ),
    ],
    ids=[
        "file an assessment",
        "record an ETEN credit",
        "mint an intake link",
        "import projects",
        "log a meeting",
        "edit the region's team",
        "add a member",
        "confirm a pending project",
        "reject a pending project",
        "grant a role",
        "send an invite",
    ],
)
async def test_the_circle_holds_no_write_route_it_did_not_hold(
    client, withheld, circle, method: str, path: str, body
) -> None:
    """The DoD's second line, one case per write route of the module the Circle never held:
    each answers 403 to an account holding ``resourceCircle`` alone — refused at the door, before
    the payload is read, so a body good enough to pass validation is not what is being tested.
    The network's own routes (intercessors, the Pulse) are the Circle's and are not listed."""
    response = await client.request(method, path, json=body, headers=circle)

    assert response.status_code == 403, (path, response.text)
