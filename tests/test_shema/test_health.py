"""The health assessment, end to end — the issue's six lines, each as a sentence of a test.

* *submission across all four dimensions, stored as immutable history with author and date* —
  a second submission appends rather than replacing, and nothing in the module can update a row;
* *overall rating computed server-side, matching wave-1 semantics* — the worst of four, ``na``
  when none is rated, per entry and on the record, and ``""`` is never ``boa``;
* *the question set is versioned; historical answers remain interpretable* — a row says which
  set it answered, an unknown version is refused, and the catalogue says what each set asked;
* *read access is at least as narrow as the record's* — ``resourceCircle`` opens the record and
  is refused the assessment;
* *a drop to Critical triggers a notification whose content was written with care* — it reaches
  the region's audience, it fires once, and what it says is asserted word by word;
* *scope and sensitive-country rules applied* — another region is absent, and the notice of a
  sensitive project names no place.

Run over the real router through the module's own guards, because four of the six are properties
of the wire: a status code, a header, who received a row, and what that row says.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.db.models.notification import Notification
from app.db.models.shema import ShemaProject
from app.db.models.shema_audit import ShemaRecordEdit
from app.db.models.shema_enums import ShemaHealthLevel, ShemaRegionKey
from app.db.models.shema_health import ShemaHealthAssessment
from app.models.shema_health import compile_notes
from app.services.shema._health_notice import EVENT_TYPE, TITLE, entered_critical
from app.utils.shema_derivations import OverallHealth
from app.utils.shema_health_questions import (
    CURRENT_QUESTION_SET,
    DIMENSIONS,
    QUESTION_SETS,
    question_set,
)
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user, make_shema_project

PROJECTS = f"{PREFIX}/projects"
QUESTIONS = f"{PREFIX}/health-questions"

#: The four required fields and a location that lands in South America.
NEW = {
    "id": "guarani-mbya",
    "languageName": "Guarani Mbyá",
    "bridgeLanguage": "Português",
    "team": "JOCUM Porto Velho",
    "objective": ["NT"],
    "location": "Brazil",
}

#: A reading that rates every dimension — the submission the wizard produces.
WHOLE = {
    "date": "2026-09-10",
    "assessor": "Marina Alves",
    "emotional": "boa",
    "relational": "atencao",
    "spiritual": "boa",
    "physical": "boa",
    "dimensionNotes": {
        "emotional": "Eles estão firmes.",
        "relational": "Dois tradutores discutiram na semana passada.",
    },
    "questionSetVersion": 1,
}


def assessments(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/health-assessments"


@pytest.fixture()
async def mentor(db_session, shema_app):
    """An OBT Lab mentor scoped to South America — not an admin, deliberately.

    ``require_role`` and ``require_app_access`` both return early on ``is_platform_admin``, so a
    test written per role with an admin account passes for the wrong reason and keeps passing
    after the guard is deleted.
    """
    return await make_scoped_user(
        db_session,
        shema_app,
        email="mentoria@shema.test",
        role_key="obtLab",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )


@pytest.fixture()
async def headers(db_session, mentor):
    return await auth_header(db_session, mentor)


@pytest.fixture()
async def project(client, headers) -> str:
    response = await client.post(PROJECTS, json=NEW, headers=headers)
    assert response.status_code == 201, response.text
    return NEW["id"]


async def _file(client, headers, project_id: str, **overrides):
    payload = {**WHOLE, **overrides}
    return await client.post(assessments(project_id), json=payload, headers=headers)


# --- the submission and its history ---------------------------------------------------


async def test_a_submission_lands_as_history_with_its_author_and_its_day(
    client, db_session, headers, project, mentor
) -> None:
    response = await _file(client, headers, project)
    assert response.status_code == 201, response.text

    rows = list((await db_session.execute(select(ShemaHealthAssessment))).scalars())
    assert len(rows) == 1
    entry = rows[0]
    assert entry.assessment_date == date(2026, 9, 10)
    assert entry.assessor == "Marina Alves"
    assert entry.created_by == mentor.id
    assert entry.created_by_name == mentor.display_name
    assert entry.emotional is ShemaHealthLevel.BOA
    assert entry.relational is ShemaHealthLevel.ATENCAO


async def test_the_record_projects_the_newest_entry_and_not_a_second_truth(
    client, headers, project
) -> None:
    body = (await _file(client, headers, project)).json()
    assert body["healthEmotional"] == "boa"
    assert body["healthRelational"] == "atencao"
    assert body["healthAssessmentDate"] == "2026-09-10"
    assert body["healthAssessor"] == "Marina Alves"
    assert [entry["date"] for entry in body["healthHistory"]] == ["2026-09-10"]


async def test_a_second_reading_appends_and_does_not_replace_the_first(
    client, db_session, headers, project
) -> None:
    """*Immutable history* — never an overwrite. Two readings are two rows."""
    await _file(client, headers, project)
    body = (await _file(client, headers, project, date="2026-09-11", relational="critica")).json()

    rows = list((await db_session.execute(select(ShemaHealthAssessment))).scalars())
    assert len(rows) == 2
    assert [entry["date"] for entry in body["healthHistory"]] == ["2026-09-10", "2026-09-11"]
    assert body["healthRelational"] == "critica"


async def test_two_readings_on_one_day_are_two_rows_and_the_later_one_projects(
    client, db_session, headers, project
) -> None:
    """A same-day correction is a later reading, not an edit of the earlier one."""
    await _file(client, headers, project, emotional="boa")
    body = (await _file(client, headers, project, emotional="critica")).json()

    rows = list((await db_session.execute(select(ShemaHealthAssessment))).scalars())
    assert len(rows) == 2
    assert body["healthEmotional"] == "critica"
    assert body["healthHistory"][-1]["emotional"] == "critica"


async def test_a_backdated_reading_is_kept_and_does_not_overwrite_a_newer_one(
    client, headers, project
) -> None:
    """FE-44 §9.4 in one line: the projection is a comparison of days, not an assignment."""
    await _file(client, headers, project, date="2026-09-10", emotional="boa")
    body = (await _file(client, headers, project, date="2026-06-01", emotional="critica")).json()

    assert body["healthEmotional"] == "boa"
    assert body["healthAssessmentDate"] == "2026-09-10"
    assert [entry["date"] for entry in body["healthHistory"]] == ["2026-06-01", "2026-09-10"]


async def test_the_last_entry_a_client_sees_is_the_one_the_record_projects(
    client, headers, project
) -> None:
    """The read's order and the projection's rule are one key, so these cannot disagree."""
    await _file(client, headers, project, date="2026-09-10")
    body = (await _file(client, headers, project, date="2026-09-10", spiritual="critica")).json()

    newest = body["healthHistory"][-1]
    assert newest["spiritual"] == body["healthSpiritual"] == "critica"
    assert newest["date"] == body["healthAssessmentDate"]


async def test_a_record_that_predates_the_history_has_its_flat_fields_carried_in(
    client, db_session, headers, project
) -> None:
    """Otherwise the first assessment filed here silently erases a reading already on the record."""
    row = await db_session.get(ShemaProject, project)
    row.health_assessment_date = date(2026, 5, 14)
    row.health_assessor = "Notion"
    row.health_emotional = ShemaHealthLevel.ATENCAO
    row.health_notes = "o que o export trouxe"
    await db_session.commit()

    body = (await _file(client, headers, project, date="2026-09-10")).json()
    history = body["healthHistory"]
    assert [entry["date"] for entry in history] == ["2026-05-14", "2026-09-10"]
    carried = history[0]
    assert carried["assessor"] == "Notion"
    assert carried["emotional"] == "atencao"
    assert carried["notes"] == "o que o export trouxe"
    assert carried["questionSetVersion"] is None, "it answered a Notion column, not a questionnaire"
    assert carried["author"] == "", "nobody knows who filed it, and a stand-in would invent one"


async def test_nothing_is_carried_in_for_a_date_with_no_rating_behind_it(
    client, db_session, headers, project
) -> None:
    """A ``healthAssessmentDate`` with four empty dimensions is not a reading anybody took."""
    row = await db_session.get(ShemaProject, project)
    row.health_assessment_date = date(2026, 5, 14)
    row.health_assessor = "Notion"
    await db_session.commit()

    body = (await _file(client, headers, project)).json()
    assert [entry["date"] for entry in body["healthHistory"]] == ["2026-09-10"]


async def test_the_carry_happens_once_and_not_on_every_later_submission(
    client, headers, project
) -> None:
    await _file(client, headers, project, date="2026-09-10")
    body = (await _file(client, headers, project, date="2026-09-11")).json()
    assert len(body["healthHistory"]) == 2


async def test_the_day_is_the_actors_own_when_the_submission_states_none(
    client, headers, project
) -> None:
    payload = {key: value for key, value in WHOLE.items() if key != "date"}
    response = await client.post(
        assessments(project),
        json=payload,
        headers={**headers, "X-Shema-Local-Date": "2026-09-11"},
    )
    assert response.json()["healthAssessmentDate"] == "2026-09-11"


@pytest.mark.parametrize("day", ["2025-09-11", "not-a-day"])
async def test_a_local_day_no_timezone_is_on_is_refused(client, headers, project, day) -> None:
    payload = {key: value for key, value in WHOLE.items() if key != "date"}
    response = await client.post(
        assessments(project), json=payload, headers={**headers, "X-Shema-Local-Date": day}
    )
    assert response.status_code == 400, response.text


async def test_the_history_cannot_be_edited_through_this_module(
    client, db_session, headers, project
) -> None:
    """There is no route that updates or deletes an assessment, and that is the immutability.

    Asserted over the built application rather than by trying a verb, because *no such route* is
    the claim: a 405 on one spelling of the path proves nothing about the next one.
    """
    from app.main import create_app

    paths = {
        (method, route.path)
        for route in create_app().routes
        if getattr(route, "path", "").startswith(f"{PREFIX}/projects")
        for method in (getattr(route, "methods", None) or ())
    }
    assert not [
        pair
        for pair in paths
        if "health-assessments" in pair[1] and pair[0] in {"PUT", "PATCH", "DELETE"}
    ]


async def test_the_write_leaves_a_trail_row_saying_the_history_grew(
    client, db_session, headers, project, mentor
) -> None:
    """*Every write recorded with author and timestamp*, in the key the console already knows.

    The seven flat fields are deliberately **not** in the trail — ``_audit.py`` audits what a
    client may write and the projection is refused on the record's own ``PATCH`` — so what the
    trail says is that the history gained an entry, and by whom. The ratings stay out of it: a
    trail is read by more people and kept longer than a response body.
    """
    await _file(client, headers, project)
    rows = list(
        (
            await db_session.execute(
                select(ShemaRecordEdit).where(ShemaRecordEdit.field_key == "healthHistory")
            )
        ).scalars()
    )
    assert len(rows) == 1
    assert rows[0].changed_by == mentor.id
    assert rows[0].changed_by_name == mentor.display_name
    assert rows[0].old_value is None and rows[0].new_value is None
    assert rows[0].changed_at is not None


async def test_the_version_moves_so_a_record_screen_learns_the_flat_fields_did(
    client, db_session, headers, project
) -> None:
    """No ``If-Match`` going in, a new ``ETag`` coming out — the service docstring says why."""
    before = (await client.get(f"{PROJECTS}/{project}", headers=headers)).headers["ETag"]
    response = await _file(client, headers, project)
    assert response.headers["ETag"] != before
    assert response.headers["ETag"] == f'"{(await db_session.get(ShemaProject, project)).version}"'


async def test_a_submission_needs_no_if_match_and_a_stale_one_is_not_refused(
    client, headers, project
) -> None:
    """Two mentors filing two readings lose nothing, so there is nothing for a guard to refuse."""
    await _file(client, headers, project, date="2026-09-10")
    second = await _file(client, headers, project, date="2026-09-11")
    assert second.status_code == 201, second.text


# --- the overall reading --------------------------------------------------------------


@pytest.mark.parametrize(
    ("ratings", "expected"),
    [
        ({}, "na"),
        ({"emotional": "boa"}, "boa"),
        ({"emotional": "boa", "relational": "atencao"}, "atencao"),
        ({"emotional": "boa", "relational": "atencao", "spiritual": "critica"}, "critica"),
        ({"physical": "critica"}, "critica"),
    ],
)
async def test_the_overall_is_the_worst_of_the_four_on_the_entry_and_on_the_record(
    client, headers, project, ratings, expected
) -> None:
    """Wave-1 semantics, asserted where both of this module's readers of the rule can be seen."""
    payload = {
        "date": "2026-09-10",
        **{dimension.value: "" for dimension in DIMENSIONS},
        **ratings,
    }
    response = await client.post(assessments(project), json=payload, headers=headers)
    if not ratings:
        assert response.status_code == 422, "a submission that rates nothing is not an assessment"
        return
    body = response.json()
    assert body["derived"]["health"] == expected
    assert body["healthHistory"][-1]["overall"] == expected


async def test_an_unrated_dimension_is_null_and_is_never_boa(
    client, db_session, headers, project
) -> None:
    """``docs/shema.md`` §7.4: a server that defaults one reports every silent team as healthy."""
    body = (await _file(client, headers, project, relational="", spiritual="", physical="")).json()
    assert body["healthRelational"] is None
    assert body["healthPhysical"] is None
    assert body["derived"]["health"] == "boa", "the worst of the one that was rated"

    entry = (await db_session.execute(select(ShemaHealthAssessment))).scalar_one()
    assert entry.relational is None
    assert entry.physical is None


async def test_a_submission_that_rates_nothing_is_refused(client, headers, project) -> None:
    response = await client.post(
        assessments(project), json={"date": "2026-09-10", "notes": "conversamos"}, headers=headers
    )
    assert response.status_code == 422
    assert "rates at least one" in response.text


def test_entering_critical_is_a_move_into_it_and_not_a_state() -> None:
    assert entered_critical(OverallHealth.BOA, OverallHealth.CRITICA)
    assert entered_critical(OverallHealth.NA, OverallHealth.CRITICA), "the first reading counts"
    assert not entered_critical(OverallHealth.CRITICA, OverallHealth.CRITICA)
    assert not entered_critical(OverallHealth.CRITICA, OverallHealth.BOA)


# --- the notes ------------------------------------------------------------------------


async def test_the_running_note_is_derived_from_the_parts_and_both_travel(
    client, headers, project
) -> None:
    """The per-dimension note is the data; a server that stored only the blob has lost it."""
    entry = (await _file(client, headers, project)).json()["healthHistory"][-1]
    assert entry["dimensionNotes"] == WHOLE["dimensionNotes"]
    assert entry["notes"] == ("Eles estão firmes.\n\nDois tradutores discutiram na semana passada.")


def test_the_note_is_compiled_in_the_dimensions_own_order_and_names_no_label() -> None:
    compiled = compile_notes({"physical": "cansados", "emotional": "firmes", "spiritual": "  "})
    assert compiled == "firmes\n\ncansados"
    assert "emotional" not in compiled, "a rendered label is the frontend's (docs/shema.md §4.11)"


async def test_a_blob_with_no_parts_is_kept_as_the_fallback_it_is(client, headers, project) -> None:
    payload = {key: value for key, value in WHOLE.items() if key != "dimensionNotes"}
    entry = (
        await client.post(
            assessments(project), json={**payload, "notes": "só o blob"}, headers=headers
        )
    ).json()["healthHistory"][-1]
    assert entry["notes"] == "só o blob"
    assert entry["dimensionNotes"] is None


async def test_a_note_for_something_that_is_not_a_dimension_is_named(
    client, headers, project
) -> None:
    response = await _file(client, headers, project, dimensionNotes={"financial": "faltou"})
    assert response.status_code == 422
    assert "not a health dimension" in response.text


# --- the versioned question set -------------------------------------------------------


async def test_every_appended_row_says_which_questions_it_answered(
    client, db_session, headers, project
) -> None:
    await _file(client, headers, project)
    entry = (await db_session.execute(select(ShemaHealthAssessment))).scalar_one()
    assert entry.question_set_version == 1


async def test_a_submission_that_states_no_version_is_stamped_with_the_current_one(
    client, db_session, headers, project
) -> None:
    payload = {key: value for key, value in WHOLE.items() if key != "questionSetVersion"}
    await client.post(assessments(project), json=payload, headers=headers)
    entry = (await db_session.execute(select(ShemaHealthAssessment))).scalar_one()
    assert entry.question_set_version == CURRENT_QUESTION_SET.version


async def test_a_question_set_this_server_never_published_is_refused(
    client, headers, project
) -> None:
    """Not rounded to the nearest: the whole value of the stamp is that it is true."""
    response = await _file(client, headers, project, questionSetVersion=99)
    assert response.status_code == 422
    assert "not a published question set" in response.text


async def test_the_catalogue_says_what_each_published_set_asked(client, headers) -> None:
    body = (await client.get(QUESTIONS, headers=headers)).json()
    assert body["current"] == CURRENT_QUESTION_SET.version
    assert [entry["version"] for entry in body["sets"]] == [s.version for s in QUESTION_SETS]
    asked = body["sets"][0]["questions"]
    assert [q["dimension"] for q in asked] == [d.value for d in DIMENSIONS]
    assert [q["questionKey"] for q in asked] == [
        "health_q_emotional",
        "health_q_relational",
        "health_q_spiritual",
        "health_q_physical",
    ]


def test_a_published_set_is_addressable_and_an_unpublished_one_answers_nothing() -> None:
    """``None`` rather than a fallback: answering *what we ask now* would be the misleading one."""
    assert question_set(1) is QUESTION_SETS[0]
    assert question_set(99) is None


def test_the_versions_are_distinct_and_only_ever_grow() -> None:
    """The append-only rule, as the one property a test can hold over a constant."""
    versions = [entry.version for entry in QUESTION_SETS]
    assert versions == sorted(set(versions))
    assert CURRENT_QUESTION_SET is QUESTION_SETS[-1]


def test_every_published_set_asks_about_dimensions_the_column_can_hold() -> None:
    """A set that asked about a fifth dimension would store its answer nowhere."""
    for entry in QUESTION_SETS:
        for question in entry.questions:
            assert question.dimension in DIMENSIONS
            assert entry.asks(question.dimension) == question.question_key


# --- who may read a reading of a team -------------------------------------------------


@pytest.fixture()
async def resource_circle(db_session, shema_app):
    return await make_scoped_user(
        db_session,
        shema_app,
        email="recursos@shema.test",
        role_key="resourceCircle",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )


async def test_the_resource_circle_opens_the_record_and_is_refused_the_assessment(
    client, db_session, headers, project, resource_circle
) -> None:
    """**The issue's fourth line, as the one case that makes it mean something.**

    ``resourceCircle`` holds a Shemá role and the same region, so it passes the record's own gate
    and reads the ficha. An assessment is an OBT Lab mentor's reading of how four people are
    actually doing, and FE-44 §5.8's audience table does not send it there — so the narrower
    question has a different answer, which is the whole of what *at least as narrow, and reviewed
    deliberately* asks for.
    """
    await _file(client, headers, project)
    theirs = await auth_header(db_session, resource_circle)

    assert (await client.get(f"{PROJECTS}/{project}", headers=theirs)).status_code == 200
    refused = await client.get(assessments(project), headers=theirs)
    assert refused.status_code == 403, refused.text
    assert "OBT Lab" in refused.text


async def test_the_resource_circle_cannot_file_one_either(
    client, db_session, headers, project, resource_circle
) -> None:
    theirs = await auth_header(db_session, resource_circle)
    assert (await _file(client, theirs, project)).status_code == 403


@pytest.mark.parametrize("role_key", ["coordinator", "obtLab", "globalStrategist"])
async def test_the_audience_reads_and_files(
    client, db_session, shema_app, headers, project, role_key
) -> None:
    """The three roles a reading reaches, each through the real guard chain."""
    regions = None if role_key == "globalStrategist" else [ShemaRegionKey.SOUTH_AMERICA]
    reader = await make_scoped_user(
        db_session, shema_app, email=f"{role_key}@shema.test", role_key=role_key, regions=regions
    )
    theirs = await auth_header(db_session, reader)
    assert (await _file(client, theirs, project)).status_code == 201
    assert (await client.get(assessments(project), headers=theirs)).status_code == 200


async def test_an_account_with_no_shema_role_reaches_neither(client, db_session, project) -> None:
    from tests.baker import make_user

    outsider = await make_user(db_session, email="fora@shema.test", is_platform_admin=False)
    theirs = await auth_header(db_session, outsider)
    assert (await client.get(assessments(project), headers=theirs)).status_code == 403
    assert (await _file(client, theirs, project)).status_code == 403


# --- scope, and the sensitive country -------------------------------------------------


async def test_a_project_in_another_region_is_refused_as_absent(
    client, db_session, shema_app, headers, project
) -> None:
    """The 404 ``_scope.py`` argues for: a Shemá slug names a place, so existence is the secret."""
    await make_shema_project(
        db_session, project_id="amharic-addis", region_key=ShemaRegionKey.AFRICA
    )

    assert (await client.get(assessments("amharic-addis"), headers=headers)).status_code == 404
    assert (await _file(client, headers, "amharic-addis")).status_code == 404


async def test_the_scope_is_checked_before_the_audience(
    client, db_session, shema_app, project, resource_circle
) -> None:
    """Out of region is 404 even for a caller the audience would have refused with a 403.

    The order is the message: the scope's refusal hides whether the project exists, and answering
    403 first would tell a caller outside the region that there is something there to be refused.
    """
    await make_shema_project(
        db_session, project_id="amharic-addis", region_key=ShemaRegionKey.AFRICA
    )
    theirs = await auth_header(db_session, resource_circle)
    assert (await client.get(assessments("amharic-addis"), headers=theirs)).status_code == 404


async def test_a_write_reaches_exactly_as_far_as_a_read(
    client, db_session, shema_app, project
) -> None:
    """``docs/shema.md`` §6.1: a regional holder who may read a region may write it, and no more."""
    elsewhere = await make_scoped_user(
        db_session,
        shema_app,
        email="africa@shema.test",
        role_key="obtLab",
        regions=[ShemaRegionKey.AFRICA],
    )
    theirs = await auth_header(db_session, elsewhere)
    assert (await _file(client, theirs, project)).status_code == 404


# --- the notice -----------------------------------------------------------------------


@pytest.fixture()
async def coordinator(db_session, shema_app):
    """Who a critical reading is for — a regional coordinator, scoped to the project's region."""
    return await make_scoped_user(
        db_session,
        shema_app,
        email="coordenacao@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )


async def _notices(db_session) -> list[Notification]:
    stmt = select(Notification).where(Notification.event_type == EVENT_TYPE)
    return list((await db_session.execute(stmt)).scalars())


async def test_a_drop_to_critical_reaches_the_regions_audience(
    client, db_session, headers, project, coordinator
) -> None:
    await _file(client, headers, project, date="2026-09-10", emotional="boa", relational="boa")
    assert await _notices(db_session) == []

    await _file(client, headers, project, date="2026-09-11", relational="critica")
    notices = await _notices(db_session)
    assert [notice.user_id for notice in notices] == [coordinator.id]


async def test_the_notice_says_enough_to_move_care_and_nothing_about_the_difficulty(
    client, db_session, headers, project, coordinator
) -> None:
    """**What it says is the deliverable.** Asserted word by word, and by what is absent.

    The four things it carries are the team, the day, the state and where to go. The dimension
    that is critical, the mentor's note and the prayer request are all on the record, behind the
    audience check — a notification row is read by more people and kept longer than a response
    body, which is the same argument ``_audit.py`` makes for keeping values out of the trail.
    """
    await _file(
        client,
        headers,
        project,
        date="2026-09-11",
        relational="critica",
        dimensionNotes={"relational": "o casal está se separando"},
        prayerRequests="orem pela família",
    )
    notice = (await _notices(db_session))[0]

    assert notice.title == TITLE
    assert notice.body == (
        "Guarani Mbyá was assessed as critical on 2026-09-11. "
        "Open the project record to read the assessment and decide what support to offer."
    )
    for leaked in ("relational", "separando", "orem", "Brazil", "JOCUM", "Porto Velho"):
        assert leaked not in notice.body, f"{leaked} has no business in a notification row"
        assert leaked not in notice.title


async def test_the_notice_of_a_sensitive_project_names_no_place_either(
    client, db_session, headers, coordinator
) -> None:
    """There is no parameter a place could arrive through, which is stronger than remembering."""
    response = await client.post(
        PROJECTS,
        json={
            **NEW,
            "id": "sensitive-one",
            "languageName": "Uma língua",
            "team": "JOCUM Egypt",
            "location": "Brazil",
            "sensitiveCountry": True,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    await _file(client, headers, "sensitive-one", date="2026-09-11", emotional="critica")

    notice = (await _notices(db_session))[0]
    assert notice.body.startswith("Uma língua was assessed as critical")
    for leaked in ("Brazil", "Egypt", "JOCUM", "south-america"):
        assert leaked not in notice.body


async def test_a_team_already_critical_is_not_announced_twice(
    client, db_session, headers, project, coordinator
) -> None:
    """The second telling is noise, and noise is what makes the first one stop being read."""
    await _file(client, headers, project, date="2026-09-10", emotional="critica")
    await _file(client, headers, project, date="2026-09-11", emotional="critica")
    assert len(await _notices(db_session)) == 1


async def test_a_first_reading_that_is_critical_is_announced(
    client, db_session, headers, project, coordinator
) -> None:
    """``na`` to ``critica`` is not a fall, and it is exactly who the product exists for."""
    await _file(client, headers, project, date="2026-09-11", emotional="critica")
    assert len(await _notices(db_session)) == 1


async def test_a_backdated_critical_reading_that_changes_nothing_announces_nothing(
    client, db_session, headers, project, coordinator
) -> None:
    """The trigger is the projection, not the payload: the current reading is the newer one."""
    await _file(client, headers, project, date="2026-09-10", emotional="boa")
    await _file(client, headers, project, date="2026-06-01", emotional="critica")
    assert await _notices(db_session) == []


async def test_the_mentor_who_filed_it_is_not_told_about_their_own_act(
    client, db_session, shema_app, project, mentor
) -> None:
    """Nobody needs to be told about their own act — the sibling's ``board_watchers`` rule.

    The account that files is a coordinator in the project's own region, so it would be on the
    list for any assessment but this one; the mentor beside it is, which is what keeps this from
    passing because the list was empty.
    """
    filer = await make_scoped_user(
        db_session,
        shema_app,
        email="ambos@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )
    theirs = await auth_header(db_session, filer)
    await _file(client, theirs, project, date="2026-09-11", emotional="critica")

    told = [notice.user_id for notice in await _notices(db_session)]
    assert filer.id not in told
    assert told == [mentor.id]


async def test_a_coordinator_in_another_region_is_not_told(
    client, db_session, shema_app, headers, project
) -> None:
    await make_scoped_user(
        db_session,
        shema_app,
        email="africa-coord@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.AFRICA],
    )
    await _file(client, headers, project, date="2026-09-11", emotional="critica")
    assert await _notices(db_session) == []


async def test_the_resource_circle_is_not_told_either(
    client, db_session, headers, project, resource_circle
) -> None:
    """The recipients are the read audience, so a notice cannot reach somebody who may not read."""
    await _file(client, headers, project, date="2026-09-11", emotional="critica")
    assert [notice.user_id for notice in await _notices(db_session)] == []


async def test_a_critical_reading_that_reaches_nobody_still_lands(
    client, db_session, headers, project
) -> None:
    """A gap in the org chart is not a failure of this write — and it is worth logging."""
    response = await _file(client, headers, project, date="2026-09-11", emotional="critica")
    assert response.status_code == 201
    assert await _notices(db_session) == []
    assert response.json()["derived"]["health"] == "critica"


async def test_the_notice_and_the_assessment_land_under_one_commit(
    client, db_session, headers, project, coordinator
) -> None:
    """``create_notification(commit=False)``: a reading that landed always carries its notice."""
    await _file(client, headers, project, date="2026-09-11", emotional="critica")
    assert len(await _notices(db_session)) == 1
    assert len(list((await db_session.execute(select(ShemaHealthAssessment))).scalars())) == 1


# --- what this endpoint deliberately does not do --------------------------------------


async def test_the_pastoral_escalation_is_stored_and_never_derived(
    client, db_session, headers, project
) -> None:
    """FE-44 §5.9: suggested with reasons, never applied. ``nao`` until a person picks otherwise."""
    body = (await _file(client, headers, project, date="2026-09-11", emotional="critica")).json()
    assert body["needsPastoralIntervention"] == "nao"

    answered = (
        await _file(
            client,
            headers,
            project,
            date="2026-09-12",
            needsPastoralIntervention="sim",
            pastoralInterventionName="Marina Alves",
            pastoralInterventionWhen="now",
        )
    ).json()
    assert answered["needsPastoralIntervention"] == "sim"
    assert answered["pastoralInterventionWhen"] == "now"


async def test_not_sending_a_prayer_request_is_not_erasing_one(
    client, db_session, headers, project
) -> None:
    """FE-44 §8.2: an unconditional ``""`` deletes a request as a side effect of another act."""
    await _file(client, headers, project, date="2026-09-10", prayerRequests="orem pelos anciãos")
    body = (await _file(client, headers, project, date="2026-09-11")).json()
    assert body["prayerRequests"] == "orem pelos anciãos"


async def test_the_flat_projection_cannot_be_written_from_the_submission(
    client, headers, project
) -> None:
    """A second writer of the projection would let a PATCH report a team nobody assessed."""
    for key in ("healthEmotional", "healthAssessmentDate", "healthAssessor", "healthNotes"):
        response = await _file(client, headers, project, **{key: "boa"})
        assert response.status_code == 422, key


async def test_the_record_read_carries_the_history_with_the_version_and_the_overall(
    client, headers, project
) -> None:
    """The ficha reads one shape, so the trend renders without a second call."""
    await _file(client, headers, project)
    entry = (await client.get(f"{PROJECTS}/{project}", headers=headers)).json()["healthHistory"][-1]
    assert entry["questionSetVersion"] == 1
    assert entry["overall"] == "atencao"
    assert entry["author"] == "Test User"


async def test_the_question_catalogue_needs_a_shema_account(client) -> None:
    """It is not a secret and it is still inside the module's deny-by-default router."""
    assert (await client.get(QUESTIONS)).status_code in (401, 403)


async def test_a_stale_assessment_date_is_not_a_progress_update(
    client, db_session, headers, project
) -> None:
    """An assessment moves no count, so it appends no progress entry and changes no staleness."""
    from app.db.models.shema_progress import ShemaProgressEntry

    before = len(list((await db_session.execute(select(ShemaProgressEntry))).scalars()))
    await _file(client, headers, project)
    after = len(list((await db_session.execute(select(ShemaProgressEntry))).scalars()))
    assert after == before
