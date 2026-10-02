"""**Who reads** — the coordination reads the truth, everybody else the region (OBT-528).

BE-04 decided *where* a sensitive place may go: everything that leaves coordination leaves
reduced, and the record read carried the truth to anybody allowed to open it. GATE-04 (Karina
22/set, Daniel 23/set) moved the line to the reader: the truth of a sensitive place is
**coordination's** — ``globalStrategist``, and ``coordinator`` in a region of their scope — and
every other reader reads the region, *inclusive na ficha*. So a leaving shape is built for a
reader, three values, one class for all three, and this file is the acceptance of that sentence:

* the reader itself — three values, derived per role, kept on the payload through the page and
  the response, and never taken from the data;
* every shape that inherits the boundary, for every reader;
* the ficha and the Projetos screen over HTTP, per role, and the notice of how many were
  withheld;
* the write: what a reader who is not coordination may not write;
* and what leaves the system, which stays reduced even when coordination is the one writing.

**The canaries are synthetic and nothing else here names a real place.** The projects sit in
the ``other`` region because a save re-derives the region from the location, and a place that
exists nowhere derives to ``other`` — so the rows stay where they were put however often they
are written, without a real country in a test. Every leak assertion reads the **whole** body,
because a field comparison tests the field somebody remembered.

**No negative test here uses an admin account**, for the reason ``conftest.py`` gives: an
installation admin passes every guard and reads as coordination, so a refusal proved with one
would be proved for the wrong reason. The two admins appear only where the truth is the answer.
"""

from __future__ import annotations

import json
import logging
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import TypeAdapter
from sqlalchemy import select

from app.db.models.notification import Notification
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from app.models.shema_forms import IntakeForm
from app.models.shema_need import ShemaNeedLine
from app.models.shema_privacy import READER_KEY, REGION_CENTROIDS, ShemaReader
from app.models.shema_projects import ShemaFacetCounts, ShemaProjectCard, ShemaProjectPage
from app.models.shema_record import ShemaProjectRecord
from app.services.shema import (
    NO_COORDINATION,
    RegionScope,
    read_intake_form,
    readership,
)
from app.services.shema._needs import URGENT_NEED_EVENT
from tests.baker import make_user
from tests.test_shema.conftest import PREFIX, auth_header, grant, make_scoped_user

PROJECTS = f"{PREFIX}/projects"
LINKS = f"{PREFIX}/intake-links"

#: The region the rows live in — see the module docstring for why it is ``other``.
HERE = ShemaRegionKey.OTHER
#: A region the rows are not in, for the coordinator who reaches nothing of them.
ELSEWHERE = ShemaRegionKey.AFRICA

#: The canaries of the withheld record. Invented, and they share no substring with the cleared
#: record's, so a body search cannot find one in the other.
PLACE = "Terra Sigilosa, Vale Escondido"
PLACE2 = "Vila Oculta"
BASE = "JOCUM Vale Escondido"
CONTACT = "+00 000 000 0001"
REASON = "motivo registrado pela coordenacao"
SECRETS = (PLACE, "Terra Sigilosa", PLACE2, BASE, CONTACT, REASON)

#: The two rows' ids, as values: a test that expires the session to re-read a row must not then
#: ask an expired fixture object for its id.
WITHHELD_ID = "lingua-um"
CLEARED_ID = "lingua-dois"

OPEN_PLACE = "Campo Aberto"
OPEN_BASE = "JOCUM Campo Aberto"
OPEN_CONTACT = "+00 000 000 0002"

#: A reading that rates every dimension — what the health wizard files.
READING = {
    "date": "2026-09-10",
    "assessor": "Mentoria",
    "emotional": "boa",
    "relational": "boa",
    "spiritual": "boa",
    "physical": "boa",
    "questionSetVersion": 1,
}


async def _project(db_session, project_id: str, *, sensitive: bool) -> ShemaProject:
    """One row with every field this file tries to extract filled, in :data:`HERE`."""
    row = ShemaProject(
        id=project_id,
        language_name="Lingua Um" if sensitive else "Lingua Dois",
        bridge_language="Portugues",
        location=PLACE if sensitive else OPEN_PLACE,
        location2=PLACE2 if sensitive else "Bairro Aberto",
        latitude=-3.5 if sensitive else -7.25,
        longitude=12.5 if sensitive else 14.75,
        team=BASE if sensitive else OPEN_BASE,
        team_contact=CONTACT if sensitive else OPEN_CONTACT,
        team_leader_contact=CONTACT if sensitive else OPEN_CONTACT,
        mentor_contact=CONTACT if sensitive else OPEN_CONTACT,
        sensitive_country=sensitive,
        sensitivity=REASON if sensitive else "",
        region_key=HERE,
    )
    db_session.add(row)
    await db_session.commit()
    return row


@pytest.fixture()
async def withheld(db_session) -> ShemaProject:
    return await _project(db_session, WITHHELD_ID, sensitive=True)


@pytest.fixture()
async def cleared(db_session) -> ShemaProject:
    return await _project(db_session, CLEARED_ID, sensitive=False)


async def _user(db_session, shema_app, role: str, *, regions=(HERE,), email: str | None = None):
    return await make_scoped_user(
        db_session,
        shema_app,
        email=email or f"{role.lower()}@leitor.test",
        role_key=role,
        regions=list(regions) if role != "globalStrategist" else None,
    )


async def _headers(db_session, user) -> dict[str, str]:
    return await auth_header(db_session, user)


def _leaks(body: Any) -> list[str]:
    text = json.dumps(body, ensure_ascii=False)
    return [secret for secret in SECRETS if secret in text]


def _assert_reduced(body: dict[str, Any]) -> None:
    """What every reader who is not coordination is given of a withheld record."""
    assert _leaks(body) == [], f"withheld values reached the payload: {_leaks(body)}"
    assert body["location"] == HERE.value
    assert body["coords"] == list(REGION_CENTROIDS[HERE])
    assert body["team"] == ""
    assert body["locationWithheld"] is True
    assert body["readAs"] == "other"


def _assert_truth(body: dict[str, Any]) -> None:
    """What coordination is given of the same record: the truth, beside the same marker."""
    assert body["location"] == PLACE
    assert body["team"] == BASE
    assert body["locationWithheld"] is True
    assert body["readAs"] == "coordination"


# --------------------------------------------------------------------------------------
# The reader
# --------------------------------------------------------------------------------------


def test_the_reader_has_three_values_and_outside_is_the_default() -> None:
    """``coordination | other | outside``, and a shape nobody built for a reader is ``outside``
    — the form everything that leaves the system already used, which is what *não muda* means
    for the export, the ETEN report, the Pulse and the leader's link."""
    assert {reader.value for reader in ShemaReader} == {"coordination", "other", "outside"}

    card = ShemaProjectCard.model_validate(
        {"id": "x", "location": PLACE, "sensitive_country": True}
    )
    assert card.reader is ShemaReader.OUTSIDE
    assert card.location == ShemaRegionKey.OTHER.value


REGIONAL = RegionScope(global_=False, regions=frozenset({HERE.value}))
GLOBAL = RegionScope(global_=True, regions=frozenset())


@pytest.mark.parametrize(
    ("granted", "scope", "platform_admin", "here", "elsewhere"),
    [
        ({"globalStrategist"}, GLOBAL, False, "coordination", "coordination"),
        ({"coordinator"}, REGIONAL, False, "coordination", "other"),
        ({"obtLab"}, REGIONAL, False, "other", "other"),
        ({"resourceCircle"}, REGIONAL, False, "other", "other"),
        ({"coordinator", "obtLab"}, REGIONAL, False, "coordination", "other"),
        ({"admin", "obtLab"}, REGIONAL, False, "coordination", "coordination"),
        (set(), GLOBAL, True, "coordination", "coordination"),
        ({"gestor", "mesa"}, RegionScope(False, frozenset()), False, "other", "other"),
    ],
    ids=[
        "globalStrategist",
        "coordinator",
        "obtLab",
        "resourceCircle",
        "coordinator+obtLab",
        "admin (hypothesis)",
        "installation admin",
        "gestor/mesa",
    ],
)
def test_each_role_reads_as_coordination_or_other(
    granted: set[str], scope: RegionScope, platform_admin: bool, here: str, elsewhere: str
) -> None:
    """GATE-04's *coordenação*, per role and per region.

    ``coordinator`` is coordination **in its own regions** and ``other`` everywhere else;
    ``globalStrategist`` everywhere. The ``admin`` row is the issue's reading — the Admin *vê
    tudo* — to confirm with Daniel. Region rows are per account, so a ``coordinator`` who is
    also ``obtLab`` is coordination wherever the account reaches.
    """
    reading = readership(scope, granted, platform_admin=platform_admin)

    assert reading.reader_of(HERE) is ShemaReader(here)
    assert reading.reader_of(ELSEWHERE) is ShemaReader(elsewhere)


def test_a_readership_that_coordinates_nothing_reads_everything_as_other() -> None:
    """The fail-closed floor, and what the notification panel's stale reading uses."""
    assert {NO_COORDINATION.reader_of(region) for region in ShemaRegionKey} == {ShemaReader.OTHER}
    assert NO_COORDINATION.coordinates_anything is False


def _row(**overrides: Any) -> SimpleNamespace:
    """A stand-in for a ``ShemaProject`` row, read by attribute exactly as one is."""
    columns = {
        "id": "lingua-um",
        "language_name": "Lingua Um",
        "location": PLACE,
        "location2": PLACE2,
        "latitude": -3.5,
        "longitude": 12.5,
        "team": BASE,
        "team_contact": CONTACT,
        "team_leader_contact": CONTACT,
        "mentor_contact": CONTACT,
        "sensitivity": REASON,
        "sensitive_country": True,
        "region_key": ShemaRegionKey.AFRICA,
    }
    return SimpleNamespace(**{**columns, **overrides})


def _need_line(reader: ShemaReader, row: SimpleNamespace) -> ShemaNeedLine:
    return ShemaNeedLine.read_by(
        {
            "id": "need-1",
            "project_id": row.id,
            "language_name": row.language_name,
            "location": row.location,
            "team": row.team,
            "category": "financial",
            "sensitive_country": row.sensitive_country,
            "region_key": row.region_key,
        },
        reader,
    )


def _intake_form(reader: ShemaReader, row: SimpleNamespace) -> IntakeForm:
    return IntakeForm.read_by(
        {
            "kind": "pulse",
            "definition_version": 1,
            "language_name": row.language_name,
            "expires_at": "2026-10-01",
            "fields": [],
        },
        reader,
    )


SHAPES = {
    "card": lambda reader, row: ShemaProjectCard.read_by(row, reader),
    "need line": _need_line,
    "intake form": _intake_form,
    "record": lambda reader, row: ShemaProjectRecord.read_by(row, reader),
}


@pytest.mark.parametrize("reader", list(ShemaReader), ids=[r.value for r in ShemaReader])
@pytest.mark.parametrize("shape", list(SHAPES), ids=list(SHAPES))
def test_every_leaving_shape_takes_the_three_readers(shape: str, reader: ShemaReader) -> None:
    """**The issue's acceptance line**: a new reader needs a case per reader in every shape that
    inherits the boundary — the card, the need line and the intake form, and now the record.

    ``coordination`` is given the truth beside the marker; ``other`` and ``outside`` the region,
    no base, no contact, no reason and the region's centroid. The marker is the same for all
    three. The intake form declares no place at all, so for it the proof is that there is
    nothing to leak whoever reads it.
    """
    built = SHAPES[shape](reader, _row())
    body = built.model_dump(by_alias=True, mode="json")

    assert built.reader is reader
    assert body["locationWithheld"] is True
    if reader is ShemaReader.COORDINATION and "location" in body:
        assert body["location"] == PLACE
        assert BASE in json.dumps(body)
    else:
        assert _leaks(body) == [], f"{shape} read as {reader.value} leaked {_leaks(body)}"
        if "location" in body:
            assert body["location"] == ShemaRegionKey.AFRICA.value


@pytest.mark.parametrize("reader", list(ShemaReader), ids=[r.value for r in ShemaReader])
def test_a_cleared_record_is_the_truth_for_every_reader(reader: ShemaReader) -> None:
    """A module that withholds everything is broken, not private — for every reader."""
    body = ShemaProjectRecord.read_by(_row(sensitive_country=False), reader).model_dump(
        by_alias=True, mode="json"
    )
    assert body["location"] == PLACE
    assert body["team"] == body["ywamBase"] == BASE
    assert body["sensitivity"] == REASON
    assert body["locationWithheld"] is False
    assert body["sensitiveCountry"] is False


def test_a_record_that_cannot_say_withholds_from_everybody_but_coordination() -> None:
    """Fail closed: a record built from something with no flag reads as sensitive — on the wire
    too, where ``sensitiveCountry`` is a boolean — and only coordination reads its place."""
    row = _row(sensitive_country=None, region_key=None)

    other = ShemaProjectRecord.read_by(row, ShemaReader.OTHER).model_dump(by_alias=True)
    assert _leaks(other) == []
    assert other["sensitiveCountry"] is True and other["locationWithheld"] is True

    truth = ShemaProjectRecord.read_by(row, ShemaReader.COORDINATION).model_dump(by_alias=True)
    assert truth["location"] == PLACE and truth["sensitiveCountry"] is True


def test_the_reader_survives_the_page_and_the_response_and_never_comes_from_the_data() -> None:
    """The validator runs again on a shape that is already built — a page taking its cards,
    FastAPI validating a handler's return into the response model — and it runs with no
    context. The reader is kept on the instance, so the second pass keeps coordination's truth;
    and because it is private, no input can name one.
    """
    card = ShemaProjectCard.read_by(_row(), ShemaReader.COORDINATION)
    page = ShemaProjectPage(
        items=[card], counts=ShemaFacetCounts(), matched=1, total=1, locations_withheld=1
    )
    assert page.items[0].location == PLACE

    record = ShemaProjectRecord.read_by(_row(), ShemaReader.COORDINATION)
    again = TypeAdapter(ShemaProjectRecord).validate_python(record, from_attributes=True)
    assert again.location == PLACE and again.reader is ShemaReader.COORDINATION

    asked = ShemaProjectRecord.model_validate(
        {**vars(_row()), "reader": "coordination", "_reader": "coordination"}
    )
    assert asked.reader is ShemaReader.OUTSIDE
    assert _leaks(asked.model_dump(by_alias=True)) == []

    with pytest.raises(TypeError):
        ShemaProjectRecord.read_by(record, ShemaReader.OTHER)
    assert record.location == PLACE, "reading a shape for somebody else must not reduce it"


def test_only_an_explicit_context_names_the_reader() -> None:
    """``read_by`` is the one door, and the key it uses is the only one that opens it."""
    other_key = ShemaProjectCard.model_validate(_row(), context={"reader": "coordination"})
    assert other_key.reader is ShemaReader.OUTSIDE

    named = ShemaProjectCard.model_validate(_row(), context={READER_KEY: "coordination"})
    assert named.reader is ShemaReader.COORDINATION


# --------------------------------------------------------------------------------------
# The ficha and the Projetos screen, per role
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["obtLab", "resourceCircle"])
async def test_the_ficha_read_by_obt_lab_carries_the_region_no_base_and_no_coordinates(
    client, db_session, shema_app, withheld, role
) -> None:
    """**The DoD's first line**: read by a role that is not coordination, the ficha brings the
    region, no base, no contact, no reason and the centroid — *inclusive na ficha*."""
    user = await _user(db_session, shema_app, role)

    response = await client.get(
        f"{PROJECTS}/{WITHHELD_ID}", headers=await _headers(db_session, user)
    )

    assert response.status_code == 200
    body = response.json()
    _assert_reduced(body)
    assert body["ywamBase"] == body["location2"] == body["sensitivity"] == ""
    assert body["teamContact"] == body["teamLeaderContact"] == body["mentorContact"] == ""
    assert body["sensitiveCountry"] is True
    assert response.headers["Cache-Control"] == "private, no-store"


async def test_the_ficha_read_by_the_regions_coordinator_carries_the_truth(
    client, db_session, shema_app, withheld
) -> None:
    """The coordinator of the project's region reads the record as it is."""
    user = await _user(db_session, shema_app, "coordinator")

    body = (
        await client.get(f"{PROJECTS}/{WITHHELD_ID}", headers=await _headers(db_session, user))
    ).json()

    _assert_truth(body)
    assert body["teamContact"] == CONTACT
    assert body["sensitivity"] == REASON
    assert body["coords"] == [12.5, -3.5]


async def test_the_ficha_read_by_another_regions_coordinator_is_a_404(
    client, db_session, shema_app, withheld
) -> None:
    """The scope, unchanged: out of region is refused exactly as absent is."""
    user = await _user(db_session, shema_app, "coordinator", regions=(ELSEWHERE,))

    response = await client.get(
        f"{PROJECTS}/{WITHHELD_ID}", headers=await _headers(db_session, user)
    )

    assert response.status_code == 404
    assert _leaks(response.json()) == []


async def test_the_strategist_and_the_admin_read_the_truth(
    client, db_session, shema_app, withheld
) -> None:
    """``globalStrategist`` is GATE-04's own; the ``admin`` is the issue's hypothesis. The admin
    alone reaches no region, so it is granted beside a regional role that does — and that role
    alone (``obtLab``) reads the region, which is what isolates the admin as the cause."""
    strategist = await _user(db_session, shema_app, "globalStrategist")
    _assert_truth(
        (
            await client.get(
                f"{PROJECTS}/{WITHHELD_ID}", headers=await _headers(db_session, strategist)
            )
        ).json()
    )

    admin = await _user(db_session, shema_app, "obtLab", email="admin@leitor.test")
    before = (
        await client.get(f"{PROJECTS}/{WITHHELD_ID}", headers=await _headers(db_session, admin))
    ).json()
    _assert_reduced(before)

    await grant(db_session, admin, shema_app, "admin")
    _assert_truth(
        (
            await client.get(f"{PROJECTS}/{WITHHELD_ID}", headers=await _headers(db_session, admin))
        ).json()
    )


async def test_coordination_reads_the_truth_on_all_five_console_routes(
    client, db_session, shema_app, withheld
) -> None:
    """The list, the read, the create, the patch and the health reading — **over HTTP**, because
    each passes the payload through a second validation (a page, the response model) that runs
    with no reader, and a reader that did not survive it would reduce coordination's truth on
    the way out. And every one of the five says ``private, no-store``: one URL now answers a
    different body to each reader, so no cache may hand one reader's body to another."""
    coordinator = await _user(db_session, shema_app, "coordinator")
    headers = await _headers(db_session, coordinator)

    listed = await client.get(PROJECTS, headers=headers)
    _assert_truth(next(item for item in listed.json()["items"] if item["id"] == WITHHELD_ID))

    read = await client.get(f"{PROJECTS}/{WITHHELD_ID}", headers=headers)
    _assert_truth(read.json())

    patched = await client.patch(
        f"{PROJECTS}/{WITHHELD_ID}",
        json={"notes": "visita feita"},
        headers={**headers, "If-Match": '"1"'},
    )
    assert patched.status_code == 200, patched.text
    _assert_truth(patched.json())

    filed = await client.post(
        f"{PROJECTS}/{WITHHELD_ID}/health-assessments", json=READING, headers=headers
    )
    assert filed.status_code == 201, filed.text
    _assert_truth(filed.json())

    strategist = await _user(db_session, shema_app, "globalStrategist")
    created = await client.post(
        PROJECTS,
        json={
            "id": "af125ed7-856f-54e3-be4b-a7c873041c1b",
            "languageName": "Lingua Tres",
            "bridgeLanguage": "Portugues",
            "team": BASE,
            "objective": ["NT"],
            "location": PLACE,
            "sensitiveCountry": True,
        },
        headers=await _headers(db_session, strategist),
    )
    assert created.status_code == 201, created.text
    _assert_truth(created.json())

    for answer in (listed, read, patched, filed, created):
        assert answer.headers["Cache-Control"] == "private, no-store", answer.request.url


async def test_the_record_a_write_answers_is_built_for_the_writers_reader(
    client, db_session, shema_app, withheld
) -> None:
    """A save answers with the recomputed record (FE-44 §9.3), and it is the writer's reader's
    record: an OBT Lab mentor who saves the team's translators or files a reading gets the region
    back. Not a note: on a withheld record the notes are coordination's to write (OBT-556)."""
    mentor = await _user(db_session, shema_app, "obtLab")
    headers = await _headers(db_session, mentor)

    patched = await client.patch(
        f"{PROJECTS}/{WITHHELD_ID}",
        json={"translators": "Equipe de revisao"},
        headers={**headers, "If-Match": '"1"'},
    )
    assert patched.status_code == 200, patched.text
    _assert_reduced(patched.json())

    filed = await client.post(
        f"{PROJECTS}/{WITHHELD_ID}/health-assessments", json=READING, headers=headers
    )
    assert filed.status_code == 201, filed.text
    _assert_reduced(filed.json())


@pytest.mark.parametrize(
    ("role", "notice"),
    [("obtLab", None), ("resourceCircle", None), ("coordinator", 1), ("globalStrategist", 1)],
)
async def test_the_withheld_notice_is_coordinations_and_null_for_everybody_else(
    client, db_session, shema_app, withheld, cleared, role, notice
) -> None:
    """**The DoD's second line.** ``locationsWithheld`` — the overlay's *N retidos* — is
    announced to coordination only (GATE-04 1.3), and since OBT-556 so is the ``sensitive``
    facet, which is the same number. Every card still carries its own marker, for everybody."""
    user = await _user(db_session, shema_app, role)
    page = (await client.get(PROJECTS, headers=await _headers(db_session, user))).json()

    assert page["locationsWithheld"] == notice
    facet = page["counts"]["groups"].get("sensitive")
    assert facet == (None if notice is None else {"yes": 1, "no": 1})
    marker = {item["id"]: item["locationWithheld"] for item in page["items"]}
    assert marker == {WITHHELD_ID: True, CLEARED_ID: False}


async def test_the_list_read_by_other_is_reduced_and_its_search_and_facets_agree(
    client, db_session, shema_app, withheld
) -> None:
    """The card, the search and the country facet read the same payload, per reader: nobody who
    is not coordination can find the withheld record by its place or count it under one, and
    coordination finds it by the place it reads."""
    mentor = await _user(db_session, shema_app, "obtLab")
    mentor_headers = await _headers(db_session, mentor)
    page = (await client.get(PROJECTS, headers=mentor_headers)).json()

    _assert_reduced(page["items"][0])
    assert _leaks(page) == []
    assert (await client.get(PROJECTS, params={"q": "Sigilosa"}, headers=mentor_headers)).json()[
        "matched"
    ] == 0

    coordinator = await _user(db_session, shema_app, "coordinator")
    coordinator_headers = await _headers(db_session, coordinator)
    truth = (await client.get(PROJECTS, headers=coordinator_headers)).json()
    assert "Terra Sigilosa" in truth["counts"]["groups"]["country"]
    found = await client.get(PROJECTS, params={"q": "Sigilosa"}, headers=coordinator_headers)
    assert found.json()["matched"] == 1


# --------------------------------------------------------------------------------------
# The write
# --------------------------------------------------------------------------------------

#: The place, the flag and the reason — coordination's to write on every record.
PLACE_WRITES = {
    "location": {"location": "Outro Lugar"},
    "location2": {"location2": "Outra Vila"},
    "coords": {"coords": [1.0, 2.0]},
    "sensitiveCountry": {"sensitiveCountry": True},
    "sensitivity": {"sensitivity": "outro motivo"},
}

#: What a withheld record hands the others empty, and so refuses them on write.
UNSEEN_WRITES = {
    "team": {"team": "JOCUM Outra"},
    "ywamBase": {"ywamBase": "JOCUM Outra"},
    "teamContact": {"teamContact": "+00 000 000 0009"},
    "teamLeaderContact": {"teamLeaderContact": "+00 000 000 0009"},
    "mentorContact": {"mentorContact": "+00 000 000 0009"},
}


async def _patch(client, db_session, user, project_id: str, body: dict[str, Any]):
    return await client.patch(
        f"{PROJECTS}/{project_id}",
        json=body,
        headers={**(await _headers(db_session, user)), "If-Match": '"1"'},
    )


async def _stored(db_session, project_id: str) -> ShemaProject:
    """The row as the database holds it now, re-read over the session's own copy."""
    stmt = (
        select(ShemaProject)
        .where(ShemaProject.id == project_id)
        .execution_options(populate_existing=True)
    )
    return (await db_session.execute(stmt)).scalar_one()


@pytest.mark.parametrize("field", list(PLACE_WRITES))
@pytest.mark.parametrize("role", ["obtLab", "resourceCircle"])
async def test_a_role_that_is_not_coordination_may_not_write_the_place_or_the_flag(
    client, db_session, shema_app, cleared, role, field
) -> None:
    """**The DoD's third line**, on a record that is **not** sensitive: the place and the flag
    are coordination's on every record — moving a location moves a region and can move it into
    a sensitive country, and the flag is the decision the whole rule rests on."""
    user = await _user(db_session, shema_app, role)

    response = await _patch(client, db_session, user, CLEARED_ID, PLACE_WRITES[field])

    assert response.status_code == 403, response.text
    assert field in response.json()["detail"]
    row = await _stored(db_session, CLEARED_ID)
    assert row.version == 1
    assert (row.location, row.sensitive_country, row.sensitivity) == (OPEN_PLACE, False, "")


@pytest.mark.parametrize("field", list(UNSEEN_WRITES))
async def test_on_a_withheld_record_the_base_and_the_contacts_are_refused_too(
    client, db_session, shema_app, withheld, cleared, field
) -> None:
    """*Não dá para editar o que não se vê*: a withheld record hands the base and the contacts to
    a reader who is not coordination as ``""``, and a value typed there would overwrite a truth
    they cannot see. On a cleared record they read it, and they may write it."""
    mentor = await _user(db_session, shema_app, "obtLab")

    refused = await _patch(client, db_session, mentor, WITHHELD_ID, UNSEEN_WRITES[field])
    assert refused.status_code == 403, refused.text
    stored = await _stored(db_session, WITHHELD_ID)
    assert (stored.team, stored.team_contact, stored.version) == (BASE, CONTACT, 1)

    allowed = await _patch(client, db_session, mentor, CLEARED_ID, UNSEEN_WRITES[field])
    assert allowed.status_code == 200, allowed.text


async def test_there_is_no_country_to_write_but_the_location(
    client, db_session, shema_app, cleared
) -> None:
    """The DoD names the country: the write shape has none — the country is the first segment of
    ``location`` — so refusing the location is refusing the country, and a ``country`` key is
    not a way around it."""
    mentor = await _user(db_session, shema_app, "obtLab")
    response = await _patch(client, db_session, mentor, CLEARED_ID, {"country": "Outro"})
    assert response.status_code == 422


async def test_coordination_writes_the_place_and_the_flag(
    client, db_session, shema_app, cleared, withheld
) -> None:
    """The other half: the region's coordinator writes the flag, the reason, the second line and
    the coordinates, and the base of a withheld record; the strategist the location."""
    coordinator = await _user(db_session, shema_app, "coordinator")
    response = await _patch(
        client,
        db_session,
        coordinator,
        CLEARED_ID,
        {
            "sensitiveCountry": True,
            "sensitivity": "novo motivo",
            "location2": "x",
            "coords": [3, 4],
        },
    )
    assert response.status_code == 200, response.text
    row = await _stored(db_session, CLEARED_ID)
    assert (row.sensitive_country, row.sensitivity, row.longitude) == (True, "novo motivo", 3.0)

    base = await _patch(client, db_session, coordinator, WITHHELD_ID, {"team": "JOCUM Nova"})
    assert base.status_code == 200, base.text

    strategist = await _user(db_session, shema_app, "globalStrategist")
    moved = await client.patch(
        f"{PROJECTS}/{CLEARED_ID}",
        json={"location": "Outro Campo"},
        headers={**(await _headers(db_session, strategist)), "If-Match": '"2"'},
    )
    assert moved.status_code == 200, moved.text


async def test_a_refused_write_applies_nothing_of_its_payload(
    client, db_session, shema_app, cleared
) -> None:
    """The refusal is about the whole save: the note beside the location is not written, and
    no version moves for a save that never happened."""
    mentor = await _user(db_session, shema_app, "obtLab")

    response = await _patch(
        client, db_session, mentor, CLEARED_ID, {"notes": "nota", "location": "Outro Lugar"}
    )

    assert response.status_code == 403
    row = await _stored(db_session, CLEARED_ID)
    assert (row.notes, row.version) == ("", 1)


async def test_the_refusal_comes_before_the_version_is_read(
    client, db_session, shema_app, cleared
) -> None:
    """A write the reader could never make is not made possible by quoting the right version,
    so a stale one is refused for what it writes rather than sent to reload for nothing."""
    mentor = await _user(db_session, shema_app, "obtLab")
    response = await client.patch(
        f"{PROJECTS}/{CLEARED_ID}",
        json={"location": "Outro Lugar"},
        headers={**(await _headers(db_session, mentor)), "If-Match": '"7"'},
    )
    assert response.status_code == 403


async def test_the_refusal_names_the_fields_and_never_the_record(
    client, db_session, shema_app, withheld, caplog
) -> None:
    """The message names what was sent, in the client's spelling; neither it nor the log line
    names the place, the base, the contact or the reason of the record it refused."""
    mentor = await _user(db_session, shema_app, "obtLab")

    with caplog.at_level(logging.WARNING):
        response = await _patch(
            client, db_session, mentor, WITHHELD_ID, {"sensitiveCountry": False, "team": "x"}
        )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert "sensitiveCountry" in detail and "team" in detail
    assert _leaks(detail) == []
    assert "a field this reader may not write" in caplog.text
    assert [secret for secret in SECRETS if secret in caplog.text] == []


# --------------------------------------------------------------------------------------
# What leaves the system
# --------------------------------------------------------------------------------------


async def test_what_leaves_stays_reduced_when_coordination_is_the_one_writing(
    client, db_session, shema_app, withheld
) -> None:
    """**The DoD's fourth line.** The coordinator reads the truth and raises an urgent need on
    the withheld record; the notice that leaves for the OBT Lab is built for ``outside`` — the
    writer's reader never reaches it."""
    coordinator = await _user(db_session, shema_app, "coordinator")
    await _user(db_session, shema_app, "obtLab")

    response = await _patch(
        client,
        db_session,
        coordinator,
        WITHHELD_ID,
        {"needsItems": [{"category": "security", "urgency": "high", "status": "open"}]},
    )
    assert response.status_code == 200, response.text
    _assert_truth(response.json())

    notices = list(
        (
            await db_session.execute(
                select(Notification).where(Notification.event_type == URGENT_NEED_EVENT)
            )
        ).scalars()
    )
    assert notices, "the urgent need reached nobody, so this proves nothing"
    for notice in notices:
        assert [s for s in SECRETS if s in notice.title + notice.body] == []


async def test_the_leader_link_is_built_for_outside_whoever_minted_it(
    client, db_session, shema_app, withheld
) -> None:
    """The leader's form declares no place, so a body search cannot fail on it — the proof is
    the reader: the coordinator mints the link, and what the link serves is built for
    ``outside``."""
    coordinator = await _user(db_session, shema_app, "coordinator")
    minted = await client.post(
        LINKS, json={"projectId": WITHHELD_ID}, headers=await _headers(db_session, coordinator)
    )
    assert minted.status_code == 201, minted.text
    token = minted.json()["token"]

    form = await read_intake_form(db_session, token)
    assert form.reader is ShemaReader.OUTSIDE

    served = await client.get(f"{PREFIX}/intake/{token}")
    assert served.status_code == 200
    assert _leaks(served.json()) == []
    assert "readAs" not in served.json()


async def test_an_installation_admin_reads_as_coordination(
    client, db_session, shema_app, withheld
) -> None:
    """An installation admin passes every guard and is global; reading less than the guards let
    it reach would make one rule stricter than the rule beside it."""
    admin = await make_user(db_session, email="instalacao@leitor.test", is_platform_admin=True)
    body = (
        await client.get(f"{PROJECTS}/{WITHHELD_ID}", headers=await _headers(db_session, admin))
    ).json()
    _assert_truth(body)


async def test_no_answer_to_a_reader_outside_coordination_names_the_place_through_an_id(
    client, db_session, shema_app
) -> None:
    """OBT-552: the id is not a second channel for the place the reader was given as a region.

    Every record created since OBT-551 takes a minted UUID, and revision ``20261001_shema552``
    moved the imported slugs to one too — so a sensitive project read by the OBT Lab, on the list,
    the record and the export, carries no id that spells where it is.
    """
    strategist = await _user(db_session, shema_app, "globalStrategist")
    created = await client.post(
        PROJECTS,
        json={
            "id": str(uuid.uuid4()),
            "languageName": "Lingua Sigilosa",
            "bridgeLanguage": "Portugues",
            "team": BASE,
            "objective": ["NT"],
            "location": PLACE,
            "sensitiveCountry": True,
        },
        headers=await _headers(db_session, strategist),
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    lab = await _headers(db_session, await _user(db_session, shema_app, "obtLab"))
    listed = await client.get(PROJECTS, headers=lab)
    read = await client.get(f"{PROJECTS}/{project_id}", headers=lab)
    exported = await client.get(f"{PREFIX}/export/projects", params={"format": "json"}, headers=lab)

    for answer in (listed, read, exported):
        assert answer.status_code == 200, answer.text
        assert _leaks(answer.json()) == [], answer.request.url
    assert project_id in {item["id"] for item in listed.json()["items"]}
    assert str(uuid.UUID(project_id)) == project_id
