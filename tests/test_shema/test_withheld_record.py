"""What a reader who is not coordination reads of a withheld record (OBT-556).

Three findings of the INT-12 pass, about one record. The free text a team writes about itself —
its notes, its health notes, its status comments, its scope, a need's description, an
assessment's notes — went to every reader whole, on a project whose place the same payload
withholds (item 6). A save refused as stale told its author which fields moved and who moved
them, the place and the contacts included (item 2). And the Projetos screen counted the
withheld projects for readers GATE-04 tells nothing about them (item 4).

Each rule is asserted for the two readers who are not coordination — the OBT Lab and the
Resource Circle, each holding the region — against the region's coordinator and a
``globalStrategist``, who read everything, and against a cleared record, which is the truth for
everybody. No account here is an installation admin: they pass every guard, and a refusal
asserted with one would pass for the wrong reason.

The canaries are invented, and a cleared record carries its own so a body search cannot find
one record's text in the other's card.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
from sqlalchemy import select

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaHealthLevel, ShemaNeedUrgency, ShemaRegionKey
from app.db.models.shema_health import ShemaHealthAssessment
from app.db.models.shema_need import ShemaNeed
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user

PROJECTS = f"{PREFIX}/projects"
EXPORT = f"{PREFIX}/export/projects"

#: The region both records live in. ``other`` because the invented places below name no
#: country the region map knows, so a save that rewrites the place keeps the record here.
HERE = ShemaRegionKey.OTHER

WITHHELD_ID = "0b8e7c4a-5f61-4d2e-9a37-1c0d2e3f4a51"
CLEARED_ID = "0b8e7c4a-5f61-4d2e-9a37-1c0d2e3f4a52"

#: What the team of the withheld record wrote. Any of these could say where the team is.
NOTES = "NOTA-SIGILOSA a equipe mudou de vale"
HEALTH_NOTES = "SAUDE-SIGILOSA cansaco depois da mudanca"
STATUS = "STATUS-SIGILOSO gravando perto da fronteira"
SCOPE = "ESCOPO-SIGILOSO o dialeto do vale escondido"
NEED = "NECESSIDADE-SIGILOSA um gerador para a casa do vale"
READING_NOTES = "AVALIACAO-SIGILOSA medo de visitas"
DIMENSION = "DIMENSAO-SIGILOSA isolamento"
SECRETS = (NOTES, HEALTH_NOTES, STATUS, SCOPE, NEED, READING_NOTES, DIMENSION)

#: The four the record and the card hold back, in the wire's spelling.
FREE_TEXT_KEYS = ("notes", "healthNotes", "statusComments", "scopeDetails")

NOT_COORDINATION = ["obtLab", "resourceCircle"]


async def _seed(db_session, project_id: str, *, sensitive: bool) -> ShemaProject:
    """One record with its own text, one need shared for prayer and one assessment."""
    tag = "" if sensitive else "ABERTO "
    row = ShemaProject(
        id=project_id,
        language_name="Lingua Um" if sensitive else "Lingua Dois",
        bridge_language="Portugues",
        location="Terra Sigilosa, Vale Escondido" if sensitive else "Campo Aberto",
        team="JOCUM Vale Escondido" if sensitive else "JOCUM Campo Aberto",
        sensitive_country=sensitive,
        region_key=HERE,
        notes=tag + NOTES,
        health_notes=tag + HEALTH_NOTES,
        status_comments=tag + STATUS,
        scope_details=tag + SCOPE,
    )
    db_session.add(row)
    db_session.add(
        ShemaNeed(
            project_id=project_id,
            category="equipment",
            urgency=ShemaNeedUrgency.MEDIUM,
            description=tag + NEED,
            prayer_shared=True,
        )
    )
    db_session.add(
        ShemaHealthAssessment(
            project_id=project_id,
            assessment_date=date(2026, 9, 10),
            assessor="Mentoria",
            emotional=ShemaHealthLevel.ATENCAO,
            notes=tag + READING_NOTES,
            dimension_notes={"emotional": tag + DIMENSION},
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


async def _user(db_session, shema_app, role: str, *, email: str | None = None):
    return await make_scoped_user(
        db_session,
        shema_app,
        email=email or f"{role.lower()}@recolhido.test",
        role_key=role,
        regions=None if role == "globalStrategist" else [HERE],
    )


async def _headers(db_session, shema_app, role: str, *, email: str | None = None):
    return await auth_header(db_session, await _user(db_session, shema_app, role, email=email))


def _leaks(text: str) -> list[str]:
    return [secret for secret in SECRETS if secret in text]


async def _stored(db_session, model: Any, **where: Any) -> Any:
    """The row as the database holds it now, re-read over the session's own copy."""
    stmt = select(model).filter_by(**where).execution_options(populate_existing=True)
    return (await db_session.execute(stmt)).scalar_one()


# --------------------------------------------------------------------------------------
# Item 6 — the free text, on every surface that reads it
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", NOT_COORDINATION)
async def test_a_withheld_records_free_text_is_empty_for_a_reader_who_is_not_coordination(
    client, db_session, shema_app, withheld, role
) -> None:
    """The ficha: the four fields, every need's description and the history's notes, all empty,
    beside the marker the place's reduction already carries — and no canary anywhere in the
    body. The history's ratings stay: they name no place."""
    res = await client.get(
        f"{PROJECTS}/{WITHHELD_ID}", headers=await _headers(db_session, shema_app, role)
    )

    assert res.status_code == 200, res.text
    assert _leaks(res.text) == []
    body = res.json()
    assert body["locationWithheld"] is True
    assert body["readAs"] == "other"
    assert {key: body[key] for key in FREE_TEXT_KEYS} == dict.fromkeys(FREE_TEXT_KEYS, "")
    assert [need["description"] for need in body["needsItems"]] == [""]
    history = body["healthHistory"] or []
    assert all(entry["notes"] == "" and entry["dimensionNotes"] is None for entry in history)
    if role == "obtLab":
        assert [entry["emotional"] for entry in history] == ["atencao"]


@pytest.mark.parametrize("role", ["coordinator", "globalStrategist"])
async def test_coordination_reads_a_withheld_records_free_text(
    client, db_session, shema_app, withheld, role
) -> None:
    """The positive half: the region's coordinator and the strategist read every word."""
    res = await client.get(
        f"{PROJECTS}/{WITHHELD_ID}", headers=await _headers(db_session, shema_app, role)
    )

    body = res.json()
    assert body["readAs"] == "coordination"
    assert [body[key] for key in FREE_TEXT_KEYS] == [NOTES, HEALTH_NOTES, STATUS, SCOPE]
    assert [need["description"] for need in body["needsItems"]] == [NEED]
    assert [(entry["notes"], entry["dimensionNotes"]) for entry in body["healthHistory"]] == [
        (READING_NOTES, {"emotional": DIMENSION})
    ]


async def test_a_cleared_records_free_text_is_read_by_everybody(
    client, db_session, shema_app, cleared
) -> None:
    """Only a withheld record is reduced: the same OBT Lab mentor reads a cleared one whole."""
    res = await client.get(
        f"{PROJECTS}/{CLEARED_ID}", headers=await _headers(db_session, shema_app, "obtLab")
    )

    body = res.json()
    assert body["notes"] == "ABERTO " + NOTES
    assert body["needsItems"][0]["description"] == "ABERTO " + NEED
    assert body["healthHistory"][0]["notes"] == "ABERTO " + READING_NOTES


@pytest.mark.parametrize("role", NOT_COORDINATION)
async def test_the_card_and_the_search_carry_no_free_text_of_a_withheld_record(
    client, db_session, shema_app, withheld, cleared, role
) -> None:
    """The Projetos screen, through a search that finds both records: the withheld card is
    reduced and the cleared card beside it is not, so the reduction is the record's and not the
    page's."""
    res = await client.get(
        PROJECTS, params={"q": "Lingua"}, headers=await _headers(db_session, shema_app, role)
    )

    cards = {card["id"]: card for card in res.json()["items"]}
    assert set(cards) == {WITHHELD_ID, CLEARED_ID}
    assert [cards[WITHHELD_ID][key] for key in FREE_TEXT_KEYS] == ["", "", "", ""]
    assert cards[CLEARED_ID]["notes"] == "ABERTO " + NOTES
    assert _leaks(json.dumps(cards[WITHHELD_ID], ensure_ascii=False)) == []


async def test_the_assessment_history_of_a_withheld_record_carries_no_notes_for_the_obt_lab(
    client, db_session, shema_app, withheld
) -> None:
    """The readings' own route, behind the health audience: the OBT Lab reads the ratings and
    not the notes of a withheld record, and the coordinator reads both."""
    route = f"{PROJECTS}/{WITHHELD_ID}/health-assessments"

    lab = await client.get(route, headers=await _headers(db_session, shema_app, "obtLab"))
    coordination = await client.get(
        route, headers=await _headers(db_session, shema_app, "coordinator")
    )

    assert lab.status_code == 200, lab.text
    assert _leaks(lab.text) == []
    assert [(row["emotional"], row["notes"], row["dimensionNotes"]) for row in lab.json()] == [
        ("atencao", "", None)
    ]
    assert [row["notes"] for row in coordination.json()] == [READING_NOTES]


async def test_a_withheld_projects_free_text_never_reaches_the_export_file(
    client, db_session, shema_app, withheld
) -> None:
    """The file leaves the system, so it is built for nobody: even the region's coordinator
    exports a withheld project with none of its text. Asserted on the bytes.

    **One text does leave, and it is the consent gate's and not this rule's**: the need the team
    shared for prayer travels as ``sharedPrayerRequests``, exactly as it reaches the prayer wall
    and the Pulse. That request was authorized to leave coordination by the people it is about
    (``_consent.py``), which is a different decision from the free text no reader outside
    coordination was ever given; whether a sensitive project's authorized request should still
    leave is the question OBT-556 raises in its pull request instead of deciding here.
    """
    res = await client.get(
        EXPORT,
        params={"format": "json"},
        headers=await _headers(db_session, shema_app, "coordinator"),
    )

    assert res.status_code == 200, res.text
    assert _leaks(res.text) == [NEED]
    (row,) = res.json()["projects"]
    assert row["sharedPrayerRequests"] == [NEED]
    assert "notes" not in row


# --------------------------------------------------------------------------------------
# Item 6 — não dá para editar o que não se vê
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["notes", "statusComments", "scopeDetails"])
@pytest.mark.parametrize("role", NOT_COORDINATION)
async def test_a_reader_who_is_not_coordination_may_not_write_the_free_text_it_cannot_see(
    client, db_session, shema_app, withheld, role, field
) -> None:
    """Handed ``""``, a value typed there would overwrite a text the writer cannot see. The
    refusal names the field and nothing about the record, and the row is untouched."""
    res = await client.patch(
        f"{PROJECTS}/{WITHHELD_ID}",
        json={field: "texto digitado por cima"},
        headers={**(await _headers(db_session, shema_app, role)), "If-Match": '"1"'},
    )

    assert res.status_code == 403
    assert field in res.json()["detail"]
    stored = await _stored(db_session, ShemaProject, id=WITHHELD_ID)
    assert (stored.notes, stored.status_comments, stored.scope_details) == (NOTES, STATUS, SCOPE)
    assert stored.version == 1


async def test_the_free_text_of_a_cleared_record_is_still_written_by_the_obt_lab(
    client, db_session, shema_app, cleared
) -> None:
    """The refusal is the withheld record's: on a cleared one the mentor writes the notes."""
    res = await client.patch(
        f"{PROJECTS}/{CLEARED_ID}",
        json={"notes": "visita feita"},
        headers={**(await _headers(db_session, shema_app, "obtLab")), "If-Match": '"1"'},
    )

    assert res.status_code == 200, res.text
    assert res.json()["notes"] == "visita feita"


def _as_the_console_sends(need: dict[str, Any], **changes: Any) -> dict[str, Any]:
    """A need as the console's ``needWire`` writes it back: every field it read, whole."""
    row = {
        key: need[key]
        for key in (
            "id",
            "category",
            "urgency",
            "status",
            "description",
            "estimatedValue",
            "estimatedAmount",
            "estimatedCurrency",
            "deadline",
            "prayerShared",
            "prayerAnswered",
            "fulfilledBy",
            "fulfilledDate",
            "droppedDate",
            "submittedBy",
            "submittedAt",
        )
    }
    return {**row, "acknowledged": False, **changes}


@pytest.mark.parametrize("role", NOT_COORDINATION)
async def test_a_need_list_saved_back_as_read_keeps_the_descriptions_and_the_shares(
    client, db_session, shema_app, withheld, role
) -> None:
    """The console sends every need back whole on every save of the needs, description
    included — so the ``""`` this reader was handed comes back. It is read as *unchanged*: the
    status moves, the description stays, and the share for prayer does not fall with it (a
    rewritten description would have unshared it, and refused the Resource Circle outright)."""
    headers = await _headers(db_session, shema_app, role)
    read = (await client.get(f"{PROJECTS}/{WITHHELD_ID}", headers=headers)).json()
    rows = [_as_the_console_sends(need, status="in-progress") for need in read["needsItems"]]
    assert [row["description"] for row in rows] == [""]

    res = await client.patch(
        f"{PROJECTS}/{WITHHELD_ID}",
        json={"needsItems": rows},
        headers={**headers, "If-Match": '"1"'},
    )

    assert res.status_code == 200, res.text
    need = await _stored(db_session, ShemaNeed, project_id=WITHHELD_ID)
    assert (need.status.value, need.description, need.prayer_shared) == ("in-progress", NEED, True)


async def test_a_description_typed_over_an_unseen_one_is_refused(
    client, db_session, shema_app, withheld
) -> None:
    """Anything but the ``""`` the reader was handed is a text typed over one they cannot see."""
    headers = await _headers(db_session, shema_app, "obtLab")
    read = (await client.get(f"{PROJECTS}/{WITHHELD_ID}", headers=headers)).json()
    rows = [_as_the_console_sends(need, description="outra coisa") for need in read["needsItems"]]

    res = await client.patch(
        f"{PROJECTS}/{WITHHELD_ID}",
        json={"needsItems": rows},
        headers={**headers, "If-Match": '"1"'},
    )

    assert res.status_code == 403
    assert "needsItems.description" in res.json()["detail"]
    assert (await _stored(db_session, ShemaNeed, project_id=WITHHELD_ID)).description == NEED


async def test_a_new_need_is_described_by_whoever_raises_it(
    client, db_session, shema_app, withheld
) -> None:
    """A create has no text to overwrite, so its author describes it — OBT-528's exception for a
    create, one level down. The coordinator reads what the mentor wrote."""
    headers = await _headers(db_session, shema_app, "obtLab")
    res = await client.patch(
        f"{PROJECTS}/{WITHHELD_ID}",
        json={"needsItems": [{"category": "training", "description": "uma oficina"}]},
        headers={**headers, "If-Match": '"1"'},
    )

    assert res.status_code == 200, res.text
    truth = await client.get(
        f"{PROJECTS}/{WITHHELD_ID}", headers=await _headers(db_session, shema_app, "coordinator")
    )
    assert sorted(need["description"] for need in truth.json()["needsItems"]) == [
        NEED,
        "uma oficina",
    ]


# --------------------------------------------------------------------------------------
# Item 2 — the conflict a save meets
# --------------------------------------------------------------------------------------


async def _coordinator_saves(client, db_session, shema_app, project_id: str, body: dict) -> str:
    """The region's coordinator saves over version 1, and is the name a conflict may give."""
    coordinator = await _user(db_session, shema_app, "coordinator", email="maria@recolhido.test")
    res = await client.patch(
        f"{PROJECTS}/{project_id}",
        json=body,
        headers={**(await auth_header(db_session, coordinator)), "If-Match": '"1"'},
    )
    assert res.status_code == 200, res.text
    return coordinator.display_name or coordinator.email


async def _stale_save(client, headers: dict[str, str], project_id: str):
    """A save of a field everybody writes, from the version everybody read."""
    return await client.patch(
        f"{PROJECTS}/{project_id}",
        json={"translators": "Equipe de revisao"},
        headers={**headers, "If-Match": '"1"'},
    )


#: The coordinator's save: the place, a contact and the notes, which the others read reduced.
UNSEEN = {
    "location": "Terra Sigilosa, Outro Vale",
    "teamContact": "+00 000 000 0007",
    "notes": "outra nota",
}


@pytest.mark.parametrize("role", NOT_COORDINATION)
async def test_a_conflict_names_no_field_the_reader_cannot_see(
    client, db_session, shema_app, withheld, role
) -> None:
    """The coordinator moved the place, a contact, the notes and the translators; this reader
    reads only the last one, and that is the only one their 409 names — with who and when,
    because the change they are told about is one they can see."""
    who = await _coordinator_saves(
        client, db_session, shema_app, WITHHELD_ID, {**UNSEEN, "translators": "Equipe A"}
    )

    res = await _stale_save(client, await _headers(db_session, shema_app, role), WITHHELD_ID)

    assert res.status_code == 409
    body = res.json()
    assert body["changedFields"] == ["translators"]
    assert body["changedBy"] == who
    assert body["changedAt"] is not None
    assert body["currentVersion"] == 2


async def test_a_conflict_says_who_only_for_a_change_the_reader_can_see(
    client, db_session, shema_app, withheld
) -> None:
    """When everything that moved is reduced for this reader, the 409 still refuses — the record
    did move — but names no field, no person and no day: *somebody saved it* is all an edit to
    a field they cannot see may tell them."""
    await _coordinator_saves(client, db_session, shema_app, WITHHELD_ID, UNSEEN)

    res = await _stale_save(client, await _headers(db_session, shema_app, "obtLab"), WITHHELD_ID)

    assert res.status_code == 409
    body = res.json()
    assert (body["changedFields"], body["changedBy"], body["changedAt"]) == ([], None, None)
    assert body["currentVersion"] == 2


async def test_coordination_is_told_every_field_that_moved(
    client, db_session, shema_app, withheld
) -> None:
    """The positive half: another coordinator of the region reads the whole record, so their
    409 names the whole save."""
    who = await _coordinator_saves(client, db_session, shema_app, WITHHELD_ID, UNSEEN)
    headers = await _headers(db_session, shema_app, "coordinator", email="joao@recolhido.test")

    res = await _stale_save(client, headers, WITHHELD_ID)

    body = res.json()
    assert set(body["changedFields"]) == set(UNSEEN)
    assert body["changedBy"] == who


@pytest.mark.parametrize(("role", "told"), [("resourceCircle", False), ("obtLab", True)])
async def test_a_conflict_names_a_prayer_request_only_to_its_audience(
    client, db_session, shema_app, cleared, role, told
) -> None:
    """On a cleared record, a prayer request kept in coordination is ``""`` to the Resource
    Circle and the text to the OBT Lab (BE-09) — and so is the fact that it moved."""
    await _coordinator_saves(
        client, db_session, shema_app, CLEARED_ID, {"prayerRequests": "um pedido da equipe"}
    )

    res = await _stale_save(client, await _headers(db_session, shema_app, role), CLEARED_ID)

    assert res.status_code == 409
    assert ("prayerRequests" in res.json()["changedFields"]) is told


# --------------------------------------------------------------------------------------
# Item 4 — the count of withheld projects is coordination's
# --------------------------------------------------------------------------------------


def _ids(page: dict[str, Any]) -> list[str]:
    return sorted(card["id"] for card in page["items"])


@pytest.mark.parametrize("role", NOT_COORDINATION)
async def test_the_sensitive_facet_is_not_given_to_a_reader_who_coordinates_nothing(
    client, db_session, shema_app, withheld, cleared, role
) -> None:
    """``locationsWithheld`` is ``null`` for this reader, and the facet that counts the same
    projects is absent beside it. The bit on each card stays — GATE-04 decided the notice."""
    page = (await client.get(PROJECTS, headers=await _headers(db_session, shema_app, role))).json()

    assert page["locationsWithheld"] is None
    assert "sensitive" not in page["counts"]["groups"]
    assert "sensitive" not in page["counts"]["groupAll"]
    marks = {card["id"]: card["locationWithheld"] for card in page["items"]}
    assert marks == {WITHHELD_ID: True, CLEARED_ID: False}


@pytest.mark.parametrize("role", NOT_COORDINATION)
@pytest.mark.parametrize("value", ["yes", "no"])
async def test_a_sensitive_filter_from_that_reader_is_ignored(
    client, db_session, shema_app, withheld, cleared, role, value
) -> None:
    """A filter on the bit would hand this reader the hidden number as ``matched``; ignored, the
    answer is the one the same request without it gets."""
    headers = await _headers(db_session, shema_app, role)
    plain = (await client.get(PROJECTS, headers=headers)).json()
    filtered = (await client.get(PROJECTS, params={"sensitive": value}, headers=headers)).json()

    assert _ids(filtered) == _ids(plain) == sorted([WITHHELD_ID, CLEARED_ID])
    assert filtered["matched"] == plain["matched"] == 2


async def test_coordination_counts_and_filters_the_sensitive_projects(
    client, db_session, shema_app, withheld, cleared
) -> None:
    """The positive half: the region's coordinator is told how many, and the filter narrows."""
    headers = await _headers(db_session, shema_app, "coordinator")
    page = (await client.get(PROJECTS, headers=headers)).json()
    flagged = (await client.get(PROJECTS, params={"sensitive": "yes"}, headers=headers)).json()

    assert page["counts"]["groups"]["sensitive"] == {"yes": 1, "no": 1}
    assert page["locationsWithheld"] == 1
    assert _ids(flagged) == [WITHHELD_ID]
