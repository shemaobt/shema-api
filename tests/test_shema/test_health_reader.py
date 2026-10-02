"""Who reads a team's health — OBT-553, every path a reading leaves by, per role.

``GET /projects/{id}/health-assessments`` refuses the Resource Circle (BE-07), and
``_health_audience.py`` says why: the role that sends a team a recorder does not need to know the
team is in emotional difficulty. These tests hold the same answer on every other door — the ficha,
the card, the search (filter, facet, order, the *atenção* preset and the card's tone), the file
the reader exports, the notification panel and the record's own write — and hold the audience's
answer beside it, so a reduction that reached the coordination too would fail here as loudly as a
leak.

The reading is filed by the one writer of the projection, the assessment, as an OBT Lab mentor,
so the projection, the history and the three pastoral fields are what a real reading leaves. The
project sits in ``other`` with no location, which is where a record with no place lands — a save
re-derives the region from the location, and this one stays where its readers reach it.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.db.models.notification import Notification
from app.db.models.shema_enums import ShemaRegionKey
from app.models.shema_projects import ShemaProjectCard
from app.models.shema_record import ShemaProjectRecord
from app.models.shema_transfer import ExportedProject
from app.services.notifications.get_shema_app_id import get_shema_app_id
from app.services.shema._health_audience import UNREAD_HEALTH, in_health_audience
from app.services.shema._health_notice import EVENT_TYPE, TITLE, notice_body
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user, make_shema_project

PROJECTS = f"{PREFIX}/projects"
EXPORT = f"{PREFIX}/export/projects"
PANEL = f"{PREFIX}/notifications"

HERE = ShemaRegionKey.OTHER
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Synthetic markers — the text a leak would carry, findable anywhere in a body.
ASSESSOR = "Avaliadora Marcador"
NOTE = "NOTA-DE-SAUDE-MARCADOR"
PASTOR = "PASTOR-MARCADOR"
WHEN = "QUANDO-MARCADOR"

#: Named so the health order and the default order disagree: by name, ``Alfa`` first; by
#: health, the rated one first.
ASSESSED = "zeta-vale"
UNASSESSED = "alfa-vale"

#: A reading that turns the team critical and raises the pastoral follow-up.
READING = {
    "date": "2026-09-10",
    "assessor": ASSESSOR,
    "emotional": "critica",
    "relational": "atencao",
    "spiritual": "boa",
    "physical": "boa",
    "dimensionNotes": {"emotional": NOTE},
    "questionSetVersion": 1,
    "needsPastoralIntervention": "sim",
    "pastoralInterventionName": PASTOR,
    "pastoralInterventionWhen": WHEN,
}

AUDIENCE = ["coordinator", "obtLab", "globalStrategist"]

READING_DAY = date(2026, 9, 10)


async def person(db_session, shema_app, role_key: str) -> dict[str, str]:
    """An account holding one role — scoped to ``other``, or unscoped for the global seat."""
    user = await make_scoped_user(
        db_session,
        shema_app,
        email=f"{role_key.lower()}@saude.test",
        role_key=role_key,
        regions=None if role_key == "globalStrategist" else [HERE],
    )
    return await auth_header(db_session, user)


@pytest.fixture()
async def assessed(client, db_session, shema_app) -> str:
    """Two projects in ``other``: one read critical by its mentor, one nobody has heard."""
    await make_shema_project(
        db_session, project_id=UNASSESSED, region_key=HERE, language_name="Alfa"
    )
    await make_shema_project(db_session, project_id=ASSESSED, region_key=HERE, language_name="Zeta")
    mentor = await make_scoped_user(
        db_session, shema_app, email="mentora@saude.test", role_key="obtLab", regions=[HERE]
    )
    response = await client.post(
        f"{PROJECTS}/{ASSESSED}/health-assessments",
        json=READING,
        headers=await auth_header(db_session, mentor),
    )
    assert response.status_code == 201, response.text
    return ASSESSED


@pytest.fixture()
async def circle(db_session, shema_app) -> dict[str, str]:
    return await person(db_session, shema_app, "resourceCircle")


def _leaks(text: str) -> list[str]:
    return [marker for marker in (ASSESSOR, NOTE, PASTOR, WHEN) if marker in text]


def _assert_unread(payload: dict[str, Any]) -> None:
    """Every health field as a project nobody assessed holds it, and the keys still there."""
    for key in ("healthEmotional", "healthRelational", "healthSpiritual", "healthPhysical"):
        assert payload[key] is None, key
    assert payload["healthAssessmentDate"] is None
    assert payload["healthAssessor"] == ""
    assert payload["healthNotes"] == ""
    assert payload["derived"]["health"] == "na"
    assert payload["derived"]["healthScore"] == 0
    assert payload["derived"]["priority"] != "critical"


def _assert_read(payload: dict[str, Any]) -> None:
    assert payload["healthEmotional"] == "critica"
    assert payload["healthRelational"] == "atencao"
    assert payload["healthAssessmentDate"] == "2026-09-10"
    assert payload["healthAssessor"] == ASSESSOR
    assert NOTE in payload["healthNotes"]
    assert payload["derived"]["health"] == "critica"
    assert payload["derived"]["healthScore"] > 0
    assert payload["derived"]["priority"] == "critical"


async def _page(client, headers, **params: str) -> dict[str, Any]:
    response = await client.get(PROJECTS, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _ids(page: dict[str, Any]) -> list[str]:
    return [card["id"] for card in page["items"]]


def _card(page: dict[str, Any], project_id: str) -> dict[str, Any]:
    return next(card for card in page["items"] if card["id"] == project_id)


async def _version(client, headers, project_id: str) -> str:
    response = await client.get(f"{PROJECTS}/{project_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.headers["ETag"]


# --- the reader ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("granted", "platform_admin", "reads"),
    [
        ({"resourceCircle"}, False, False),
        ({"admin"}, False, False),
        (set(), False, False),
        ({"coordinator"}, False, True),
        ({"obtLab"}, False, True),
        ({"globalStrategist"}, False, True),
        ({"resourceCircle", "obtLab"}, False, True),
        (set(), True, True),
    ],
)
def test_the_health_reader_is_the_assessment_audience(
    granted: set[str], platform_admin: bool, reads: bool
) -> None:
    """One list, read without a query: the roles the assessment reaches, and an installation
    admin, who passes every guard here."""
    assert in_health_audience(granted, platform_admin=platform_admin) is reads


# --- the ficha -------------------------------------------------------------------------------


async def test_the_resource_circle_reads_no_health_on_the_record(client, assessed, circle) -> None:
    response = await client.get(f"{PROJECTS}/{assessed}", headers=circle)

    assert response.status_code == 200
    record = response.json()
    _assert_unread(record)
    assert record["healthHistory"] is None
    assert record["needsPastoralIntervention"] == "nao"
    assert record["pastoralInterventionName"] == ""
    assert record["pastoralInterventionWhen"] is None
    assert _leaks(response.text) == []


@pytest.mark.parametrize("role_key", AUDIENCE)
async def test_the_health_audience_reads_the_health_on_the_record(
    client, db_session, shema_app, assessed, role_key
) -> None:
    headers = await person(db_session, shema_app, role_key)

    response = await client.get(f"{PROJECTS}/{assessed}", headers=headers)

    assert response.status_code == 200
    record = response.json()
    _assert_read(record)
    assert len(record["healthHistory"]) == 1
    assert record["needsPastoralIntervention"] == "sim"
    assert record["pastoralInterventionName"] == PASTOR
    assert record["pastoralInterventionWhen"] == WHEN


# --- the card and the search -----------------------------------------------------------------


async def test_the_resource_circle_reads_no_health_on_the_card(client, assessed, circle) -> None:
    response = await client.get(PROJECTS, headers=circle)

    assert response.status_code == 200
    _assert_unread(_card(response.json(), assessed))
    assert _leaks(response.text) == []


@pytest.mark.parametrize("role_key", AUDIENCE)
async def test_the_health_audience_reads_the_health_on_the_card(
    client, db_session, shema_app, assessed, role_key
) -> None:
    headers = await person(db_session, shema_app, role_key)

    _assert_read(_card(await _page(client, headers), assessed))


async def test_a_health_filter_from_the_resource_circle_is_ignored(
    client, assessed, circle
) -> None:
    """Ignored, not answered: the same projects with and without it, whatever the team's
    health — so no value of the filter can carve out the teams in difficulty."""
    unfiltered = await _page(client, circle)

    for value in ("critica", "atencao", "boa", "na"):
        filtered = await _page(client, circle, health=value)
        assert _ids(filtered) == _ids(unfiltered), value
        assert filtered["matched"] == unfiltered["matched"] == 2


async def test_the_resource_circle_is_given_no_health_facet(client, assessed, circle) -> None:
    counts = (await _page(client, circle))["counts"]

    assert "health" not in counts["groups"]
    assert "health" not in counts["groupAll"]
    assert "status" in counts["groups"]


async def test_a_health_sort_from_the_resource_circle_falls_back_to_the_default(
    client, assessed, circle
) -> None:
    by_health = await _page(client, circle, sort="health")

    assert by_health["sort"] == "deadline"
    assert _ids(by_health) == _ids(await _page(client, circle)) == [UNASSESSED, ASSESSED]


async def test_the_attention_preset_does_not_read_health_for_the_resource_circle(
    client, assessed, circle
) -> None:
    """A critical team is in *atenção* for its health; the circle's card has none, so neither
    the preset nor its count can say which team is struggling."""
    page = await _page(client, circle, presets="attention")

    assert assessed not in _ids(page)
    assert page["counts"]["presets"]["attention"] == 0


@pytest.mark.parametrize("role_key", AUDIENCE)
async def test_the_health_audience_filters_counts_and_sorts_by_health(
    client, db_session, shema_app, assessed, role_key
) -> None:
    headers = await person(db_session, shema_app, role_key)

    critical = await _page(client, headers, health="critica")
    assert _ids(critical) == [assessed]
    assert critical["counts"]["groups"]["health"]["critica"] == 1

    by_health = await _page(client, headers, sort="health")
    assert by_health["sort"] == "health"
    scores = [card["derived"]["healthScore"] for card in by_health["items"]]
    assert scores == sorted(scores, reverse=True)
    assert _ids(by_health) == [ASSESSED, UNASSESSED]

    attention = await _page(client, headers, presets="attention")
    assert assessed in _ids(attention)


# --- the file --------------------------------------------------------------------------------


async def _exported(client, headers) -> dict[str, Any]:
    response = await client.get(EXPORT, params={"format": "json"}, headers=headers)
    assert response.status_code == 200, response.text
    rows = response.json()["projects"]
    return next(row for row in rows if row["id"] == ASSESSED)


async def test_a_file_exported_outside_the_audience_carries_no_health(
    client, assessed, circle
) -> None:
    assert (await _exported(client, circle))["overallHealth"] == "na"


@pytest.mark.parametrize("role_key", AUDIENCE)
async def test_the_health_audience_exports_the_overall_health(
    client, db_session, shema_app, assessed, role_key
) -> None:
    headers = await person(db_session, shema_app, role_key)

    assert (await _exported(client, headers))["overallHealth"] == "critica"


# --- the panel -------------------------------------------------------------------------------


async def _addressed(db_session, email: str, role_key: str, shema_app) -> dict[str, str]:
    """An account holding ``role_key`` now, with a health notice addressed to it earlier."""
    user = await make_scoped_user(
        db_session, shema_app, email=email, role_key=role_key, regions=[HERE]
    )
    db_session.add(
        Notification(
            user_id=user.id,
            app_id=await get_shema_app_id(db_session),
            event_type=EVENT_TYPE,
            title=TITLE,
            body=notice_body("Zeta", day=READING_DAY),
        )
    )
    await db_session.commit()
    return await auth_header(db_session, user)


async def test_a_health_notice_is_not_read_by_an_account_that_left_the_audience(
    client, db_session, shema_app
) -> None:
    """The notice was addressed while the account was in the audience; it is read by who the
    account is now. The coordinator beside it, holding the same row, still reads it."""
    circle = await _addressed(db_session, "saiu@saude.test", "resourceCircle", shema_app)
    coordinator = await _addressed(db_session, "ficou@saude.test", "coordinator", shema_app)

    left = await client.get(PANEL, headers=circle)
    stayed = await client.get(PANEL, headers=coordinator)

    assert left.status_code == stayed.status_code == 200
    assert [entry["kind"] for entry in left.json()] == []
    assert [entry["kind"] for entry in stayed.json()] == ["health"]


# --- the write -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"pastoralInterventionName": "outro"},
        {"needsPastoralIntervention": "nao"},
        {"pastoralInterventionWhen": "depois"},
    ],
)
async def test_the_resource_circle_may_not_write_the_pastoral_follow_up_it_cannot_read(
    client, assessed, circle, body
) -> None:
    """Não dá para editar o que não se vê: the circle reads ``nao`` and ``""`` where the team's
    follow-up is, so a value typed over them would erase it unseen. Refused by name, and the
    record does not move."""
    version = await _version(client, circle, assessed)

    response = await client.patch(
        f"{PROJECTS}/{assessed}", json=body, headers={**circle, "If-Match": version}
    )

    assert response.status_code == 403
    assert next(iter(body)) in response.text
    assert await _version(client, circle, assessed) == version


@pytest.mark.parametrize("role_key", AUDIENCE)
async def test_the_health_audience_writes_the_pastoral_follow_up(
    client, db_session, shema_app, assessed, role_key
) -> None:
    headers = await person(db_session, shema_app, role_key)
    version = await _version(client, headers, assessed)

    response = await client.patch(
        f"{PROJECTS}/{assessed}",
        json={"pastoralInterventionName": "Outra pessoa"},
        headers={**headers, "If-Match": version},
    )

    assert response.status_code == 200, response.text
    assert response.json()["pastoralInterventionName"] == "Outra pessoa"


# --- the nets --------------------------------------------------------------------------------


@pytest.mark.parametrize("shape", [ShemaProjectRecord, ShemaProjectCard, ExportedProject])
def test_every_health_field_on_a_console_shape_is_withheld(shape) -> None:
    """A health field added to one of the shapes that carry a project is red here until the
    reduction names it — the list and the shapes cannot drift apart."""
    named = {
        name
        for name in shape.model_fields
        if ("health" in name or "pastoral" in name) and name != "derived"
    }

    assert named
    assert named <= set(UNREAD_HEALTH), sorted(named - set(UNREAD_HEALTH))


#: The shapes that carry a team's health, as a constructor names them.
HEALTH_SHAPES = frozenset({"ShemaProjectRecord", "ShemaProjectCard", "ExportedProject"})


def _builds_a_health_shape(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"read_by", "model_validate"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in HEALTH_SHAPES
        ):
            return True
    return False


def _asks_the_health_reader(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Name) and node.id == "health_as_read" for node in ast.walk(tree)
    )


def test_every_builder_of_a_health_shape_asks_the_health_reader() -> None:
    """The reduction is a call, and a call is what the next builder forgets: every service that
    builds a record, a card or an exported row also asks ``health_as_read``."""
    builders = []
    for path in sorted((REPO_ROOT / "app" / "services" / "shema").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if _builds_a_health_shape(tree):
            builders.append(path.name)
            assert _asks_the_health_reader(tree), path.name

    assert {"read_record.py", "browse_projects.py", "export_projects.py"} <= set(builders)
