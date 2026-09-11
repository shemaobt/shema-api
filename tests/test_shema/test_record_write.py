"""The record's write, end to end — the DoD's five behavioural lines, over HTTP.

Every test here is one sentence of the issue:

* *a partial update per tab* — a ``PATCH`` that carries one tab's fields leaves the other nine
  exactly as they were, and absent is unchanged all the way down;
* *a stale write is rejected with a conflict the UI can explain* — the 409 names the version,
  the fields and the person;
* *progress applied as an atomic batch; a partial failure applies nothing* — one bad row in a
  table of sixty-six writes none of them, and the record does not move;
* *progress values validated against real book structure and sane ranges* — a book that is not
  a book, a scope longer than the book, a count above its own row;
* *every write recorded with author and timestamp* — and the guarded fields recorded without
  their values.

Run over the real router through the module's own guards, because three of the five are
properties of the wire — a status code, a header, a body — and a service-level test would pass
with the header never read.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db.models.shema import ShemaProject
from app.db.models.shema_audit import ShemaRecordEdit
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_progress import ShemaProgressEntry
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user, make_shema_project

PROJECTS = f"{PREFIX}/projects"

#: A create the console would accept: the four required fields and nothing more.
NEW = {
    "id": "guarani-mbya",
    "languageName": "Guarani Mbyá",
    "bridgeLanguage": "Português",
    "team": "YWAM Porto Velho",
    "objective": ["NT"],
    "location": "Brazil",
}


def book(book_id: str, chapters: int, translated: int = 0, checked: int = 0, approved: int = 0):
    return {
        "id": book_id,
        "name": book_id,
        "chapters": chapters,
        "translated": translated,
        "communityChecked": checked,
        "mentorApproved": approved,
    }


@pytest.fixture()
async def coordinator(db_session, shema_app):
    """A regional coordinator scoped to South America — not an admin, deliberately.

    ``require_role`` returns early on ``is_platform_admin``, so a test written per role with an
    admin account passes for the wrong reason and keeps passing after the guard is deleted.
    """
    return await make_scoped_user(
        db_session,
        shema_app,
        email="coordenacao@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )


@pytest.fixture()
async def headers(db_session, coordinator):
    return await auth_header(db_session, coordinator)


async def _create(client, headers, **overrides):
    payload = {**NEW, **overrides}
    return await client.post(PROJECTS, json=payload, headers=headers)


def _etag(response) -> str:
    return response.headers["ETag"]


# --- the read -------------------------------------------------------------------------


async def test_the_record_read_answers_the_whole_shape_with_its_version(
    client, db_session, shema_app, headers
) -> None:
    await make_shema_project(
        db_session, project_id="guarani-mbya", region_key=ShemaRegionKey.SOUTH_AMERICA
    )
    response = await client.get(f"{PROJECTS}/guarani-mbya", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "guarani-mbya"
    assert body["ywamBase"] == body["team"]
    assert body["progressHistory"] == []
    assert body["derived"]["status"] == "nao-iniciado"
    assert response.headers["ETag"] == '"1"'


async def test_the_record_read_carries_the_true_place_of_a_sensitive_project(
    client, db_session, shema_app, headers
) -> None:
    """FE-44 §9.0: the record is a **coordination** surface and is the one read that does.

    Hiding the country from the record's own author is data loss rather than privacy (§8.1
    rule 5); the collection read beside it withholds the same row, and
    ``test_privacy.py`` is where that half is pinned.
    """
    project = await make_shema_project(
        db_session, project_id="sensivel-um", region_key=ShemaRegionKey.SOUTH_AMERICA
    )
    project.sensitive_country = True
    project.location = "Colombia"
    project.team = "YWAM Bogotá"
    await db_session.commit()

    body = (await client.get(f"{PROJECTS}/sensivel-um", headers=headers)).json()
    assert body["location"] == "Colombia"
    assert body["team"] == "YWAM Bogotá"
    assert "locationWithheld" not in body


async def test_a_record_in_another_region_is_refused_as_absent(
    client, db_session, shema_app, headers
) -> None:
    """Out of scope and non-existent are indistinguishable on the wire, on purpose."""
    await make_shema_project(db_session, project_id="lao-theung", region_key=ShemaRegionKey.ASIA)
    assert (await client.get(f"{PROJECTS}/lao-theung", headers=headers)).status_code == 404
    assert (await client.get(f"{PROJECTS}/nao-existe", headers=headers)).status_code == 404


# --- the create -----------------------------------------------------------------------


async def test_a_create_mints_nothing_and_answers_the_record(client, db_session, headers) -> None:
    response = await _create(client, headers)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "guarani-mbya"
    assert body["languageName"] == "Guarani Mbyá"
    assert response.headers["ETag"] == '"1"'


async def test_a_create_may_carry_the_whole_frozen_project(client, db_session, headers) -> None:
    """FE-44 §9.3 has ``POST`` take a whole ``Project``, empty org-chart keys included.

    The three are required keys of that interface and the fixtures assert they stay ``""``, so
    a server that refused the *key* would refuse every create the contract describes. A filled
    one is still refused — the next test.
    """
    response = await _create(
        client,
        headers,
        ywamBase="YWAM Porto Velho",
        regionalCoordinator="",
        obtLabPerson="",
        resourceCirclePerson="",
        inETEN=False,
    )
    assert response.status_code == 201
    assert response.json()["ywamBase"] == "YWAM Porto Velho"


async def test_a_create_that_fills_a_role_holder_is_refused(client, headers) -> None:
    response = await _create(client, headers, regionalCoordinator="Joana")
    assert response.status_code == 422
    assert "org chart" in response.text


async def test_the_same_slug_twice_is_a_conflict_and_not_an_overwrite(
    client, db_session, headers
) -> None:
    assert (await _create(client, headers)).status_code == 201
    second = await _create(client, headers, languageName="Outro Idioma")
    assert second.status_code == 409

    stored = (
        await db_session.execute(select(ShemaProject).where(ShemaProject.id == "guarani-mbya"))
    ).scalar_one()
    assert stored.language_name == "Guarani Mbyá"


async def test_a_record_filed_outside_the_callers_regions_is_refused(client, headers) -> None:
    """403 and not 404: the caller chose the id and wrote the location, so nothing is hidden.

    A coordinator scoped to South America may not file a project in Asia, and the check has to
    wait for the payload — the region is a consequence of the ``location`` it carries.
    """
    response = await _create(client, headers, id="kurukh-jharkhand", location="India")
    assert response.status_code == 403


async def test_the_region_is_derived_from_the_location_and_never_typed(
    client, db_session, headers
) -> None:
    await _create(client, headers, location="Colombia, Peru")
    stored = (
        await db_session.execute(select(ShemaProject).where(ShemaProject.id == "guarani-mbya"))
    ).scalar_one()
    assert stored.region_key == ShemaRegionKey.SOUTH_AMERICA


# --- the partial update ---------------------------------------------------------------


async def test_a_tab_writes_its_own_fields_and_leaves_the_others_alone(
    client, db_session, headers
) -> None:
    """Absent is unchanged, all the way down — the whole reason every field is ``| None``."""
    created = await _create(client, headers, mentor="Rodolfo / Debora", notes="não normalizar  ")
    patched = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"statusComments": "visitou a aldeia em maio"},
        headers={**headers, "If-Match": _etag(created)},
    )

    assert patched.status_code == 200
    body = patched.json()
    assert body["statusComments"] == "visitou a aldeia em maio"
    assert body["mentor"] == "Rodolfo / Debora"
    assert body["notes"] == "não normalizar  "
    assert patched.headers["ETag"] == '"2"'


async def test_not_sending_a_prayer_request_is_not_erasing_one(client, db_session, headers) -> None:
    """FE-44 §8.2: an unconditional write of ``""`` deletes a request as a side effect."""
    created = await _create(client, headers)
    stored = (
        await db_session.execute(select(ShemaProject).where(ShemaProject.id == "guarani-mbya"))
    ).scalar_one()
    stored.prayer_requests = "a equipe pede oração pela viagem"
    await db_session.commit()

    await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"statusComments": "nada de novo"},
        headers={**headers, "If-Match": _etag(created)},
    )
    await db_session.refresh(stored)
    assert stored.prayer_requests == "a equipe pede oração pela viagem"


async def test_a_save_that_changed_nothing_moves_no_version_and_writes_no_trail(
    client, db_session, headers
) -> None:
    """A guard that refuses everybody else on an untouched save is a reason not to press save."""
    created = await _create(client, headers)
    again = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"languageName": "Guarani Mbyá"},
        headers={**headers, "If-Match": _etag(created)},
    )

    assert again.status_code == 200
    assert again.headers["ETag"] == '"1"'
    rows = (
        await db_session.execute(select(ShemaRecordEdit).where(ShemaRecordEdit.version > 1))
    ).scalars()
    assert list(rows) == []


# --- the concurrency guard ------------------------------------------------------------


async def test_a_patch_without_if_match_is_refused(client, headers) -> None:
    """A client that cannot say which version it read has no basis for overwriting one."""
    await _create(client, headers)
    response = await client.patch(
        f"{PROJECTS}/guarani-mbya", json={"statusComments": "x"}, headers=headers
    )
    assert response.status_code == 422
    assert "if-match" in response.text.lower()


@pytest.mark.parametrize("tag", ["*", "banana", '"not-a-number"'])
async def test_a_patch_whose_if_match_is_not_a_version_is_refused(client, headers, tag) -> None:
    """``*`` is the spelling of *I do not know what I am overwriting*."""
    await _create(client, headers)
    response = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"statusComments": "x"},
        headers={**headers, "If-Match": tag},
    )
    assert response.status_code == 400


async def test_a_stale_save_is_refused_with_what_moved_and_who_moved_it(
    client, db_session, headers, coordinator
) -> None:
    """**The DoD's second line.** The 409 is what lets the screen explain itself."""
    created = await _create(client, headers)
    stale = _etag(created)

    first = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"statusComments": "gravação começou", "statusGoal": "NT até 2028"},
        headers={**headers, "If-Match": stale},
    )
    assert first.status_code == 200

    second = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"statusComments": "a equipe parou"},
        headers={**headers, "If-Match": stale},
    )

    assert second.status_code == 409
    body = second.json()
    assert body["code"] == "CONFLICT"
    assert body["expectedVersion"] == 1
    assert body["currentVersion"] == 2
    assert set(body["changedFields"]) == {"statusComments", "statusGoal"}
    assert body["changedBy"] == coordinator.display_name
    assert body["changedAt"] is not None
    assert second.headers["ETag"] == '"2"'


async def test_the_refused_write_applied_nothing(client, db_session, headers) -> None:
    created = await _create(client, headers)
    stale = _etag(created)
    await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"statusComments": "gravação começou"},
        headers={**headers, "If-Match": stale},
    )
    await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"statusComments": "a equipe parou"},
        headers={**headers, "If-Match": stale},
    )

    stored = (
        await db_session.execute(select(ShemaProject).where(ShemaProject.id == "guarani-mbya"))
    ).scalar_one()
    await db_session.refresh(stored)
    assert stored.status_comments == "gravação começou"
    assert stored.version == 2


# --- the progress batch ---------------------------------------------------------------


async def test_a_progress_batch_rolls_the_aggregates_and_appends_one_entry(
    client, db_session, headers
) -> None:
    created = await _create(client, headers)
    response = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"bookProgress": [book("mat", 28, 28, 10, 4), book("mrk", 16, 8)]},
        headers={**headers, "If-Match": _etag(created), "X-Shema-Local-Date": "2026-09-11"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["translatedUnits"] == 36
    assert body["communityCheckedUnits"] == 10
    assert body["approvedUnits"] == 4
    assert body["totalUnits"] == 44
    assert len(body["progressHistory"]) == 1
    entry = body["progressHistory"][0]
    assert entry["date"] == "2026-09-11"
    assert entry["previousTranslated"] == 0
    assert len(entry["bookProgress"]) == 2


@pytest.mark.parametrize(
    "bad",
    [
        book("gospel-of-thomas", 12),
        book("mat", 60),
        book("mat", 28, translated=30),
        book("mat", 28, checked=-1),
    ],
    ids=["not-a-book", "longer-than-the-book", "more-than-the-row", "negative"],
)
async def test_one_impossible_row_refuses_the_whole_batch(client, db_session, headers, bad) -> None:
    """**The DoD's third and fourth lines.** A partial failure applies nothing."""
    created = await _create(client, headers)
    response = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"bookProgress": [book("luk", 24, 24), bad, book("jhn", 21, 21)]},
        headers={**headers, "If-Match": _etag(created)},
    )

    assert response.status_code == 422
    stored = (
        await db_session.execute(select(ShemaProject).where(ShemaProject.id == "guarani-mbya"))
    ).scalar_one()
    await db_session.refresh(stored)
    assert stored.book_progress == []
    assert stored.translated_units == 0
    assert stored.version == 1
    assert list((await db_session.execute(select(ShemaProgressEntry))).scalars()) == []


async def test_every_bad_row_in_a_batch_is_named_at_once(client, headers) -> None:
    """A batch refused one row per round trip is a batch nobody can fix."""
    created = await _create(client, headers)
    response = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"bookProgress": [book("nope", 1), book("mat", 60), book("mrk", 16, 20)]},
        headers={**headers, "If-Match": _etag(created)},
    )
    located = {tuple(error["loc"][-2:]) for error in response.json()["detail"]}
    assert {("bookProgress", 0), ("bookProgress", 1), ("bookProgress", 2)} <= located


async def test_a_story_only_table_does_not_zero_the_counts(client, db_session, headers) -> None:
    """FE-44 §7.2's divergence from the prototype, over the wire."""
    created = await _create(client, headers)
    rolled = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"bookProgress": [book("mat", 28, 28, 10, 4)]},
        headers={**headers, "If-Match": _etag(created)},
    )
    after = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"storyProgress": [{"name": "A criação", "audioHours": "2 a 3"}]},
        headers={**headers, "If-Match": _etag(rolled)},
    )

    assert after.json()["translatedUnits"] == 28
    assert len(after.json()["progressHistory"]) == 1


async def test_a_record_may_still_carry_more_translated_than_its_scope(
    client, db_session, headers
) -> None:
    """``156/25`` is a real export record: the scope is what is wrong in it, not the count."""
    created = await _create(client, headers)
    response = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"totalUnits": 25, "translatedUnits": 156},
        headers={**headers, "If-Match": _etag(created)},
    )
    assert response.status_code == 200
    assert response.json()["derived"]["progress"] == pytest.approx(624.0)


async def test_a_deadline_before_the_start_is_refused(client, db_session, headers) -> None:
    created = await _create(client, headers, startDate="2026-01-10")
    response = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"deadline": "2025-12-01"},
        headers={**headers, "If-Match": _etag(created)},
    )
    assert response.status_code == 400
    assert "before the start date" in response.text


@pytest.mark.parametrize("day", ["not-a-day", "2020-01-01"])
async def test_a_local_day_no_timezone_is_on_is_refused(client, headers, day) -> None:
    """A client-stated day is bounded, or it is a way to backdate an ETEN credit."""
    created = await _create(client, headers)
    response = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"bookProgress": [book("mat", 28, 5)]},
        headers={**headers, "If-Match": _etag(created), "X-Shema-Local-Date": day},
    )
    assert response.status_code == 400


async def test_the_actors_own_day_is_what_the_entry_is_stamped_with(
    client, db_session, headers
) -> None:
    """UTC-3 after 21:00 is already tomorrow — and on 31 December, already next year."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    created = await _create(client, headers)
    response = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"bookProgress": [book("mat", 28, 5)]},
        headers={**headers, "If-Match": _etag(created), "X-Shema-Local-Date": tomorrow},
    )
    assert response.json()["progressHistory"][0]["date"] == tomorrow


# --- the trail ------------------------------------------------------------------------


async def _edits(db_session, project_id: str) -> list[ShemaRecordEdit]:
    stmt = (
        select(ShemaRecordEdit)
        .where(ShemaRecordEdit.project_id == project_id)
        .order_by(ShemaRecordEdit.version, ShemaRecordEdit.field_key)
    )
    return list((await db_session.execute(stmt)).scalars())


async def test_every_write_is_recorded_with_its_author_and_its_moment(
    client, db_session, headers, coordinator
) -> None:
    """**The DoD's fifth line.** Who, when, which field, and from what to what."""
    created = await _create(client, headers)
    await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"statusComments": "gravação começou"},
        headers={**headers, "If-Match": _etag(created)},
    )

    rows = await _edits(db_session, "guarani-mbya")
    latest = [row for row in rows if row.version == 2]
    assert [row.field_key for row in latest] == ["statusComments"]
    assert latest[0].old_value == ""
    assert latest[0].new_value == "gravação começou"
    assert latest[0].changed_by == coordinator.id
    assert latest[0].changed_by_name == coordinator.display_name
    assert latest[0].changed_at is not None


async def test_the_create_is_in_the_trail_as_the_fields_the_author_typed(
    client, db_session, headers
) -> None:
    await _create(client, headers)
    keys = {row.field_key for row in await _edits(db_session, "guarani-mbya")}
    assert {"languageName", "bridgeLanguage", "team", "objective", "location"} <= keys
    assert "statusComments" not in keys


async def test_a_guarded_field_records_that_it_moved_and_not_where_to(
    client, db_session, headers
) -> None:
    """A country copied into a second table with different readers has left the boundary."""
    created = await _create(client, headers)
    await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"location": "Colombia", "teamContact": "+55 69 99999-0000"},
        headers={**headers, "If-Match": _etag(created)},
    )

    guarded = {
        row.field_key: (row.old_value, row.new_value)
        for row in await _edits(db_session, "guarani-mbya")
        if row.version == 2
    }
    assert guarded["location"] == (None, None)
    assert guarded["teamContact"] == (None, None)


async def test_the_trail_cannot_be_edited(client, db_session, headers) -> None:
    """Append-only in the database, by the trigger the progress history already uses.

    A history whose rows can be edited answers nothing — and a rule that lives in the one
    service that writes today is a rule the second writer will not have.
    """
    await _create(client, headers)
    row = (await _edits(db_session, "guarani-mbya"))[0]
    row.new_value = "algo que ninguém escreveu"
    with pytest.raises(Exception, match="append-only"):
        await db_session.commit()
    await db_session.rollback()


async def test_the_record_names_who_saved_it_last(client, db_session, headers, coordinator) -> None:
    """The name is a snapshot, so the record can say *saved by Maria* without a join."""
    created = await _create(client, headers)
    await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"statusComments": "x"},
        headers={**headers, "If-Match": _etag(created)},
    )
    stored = (
        await db_session.execute(select(ShemaProject).where(ShemaProject.id == "guarani-mbya"))
    ).scalar_one()
    await db_session.refresh(stored)
    assert stored.updated_by_name == coordinator.display_name
    assert stored.updated_by == coordinator.id
    assert stored.updated_at is not None


def test_an_account_with_no_display_name_is_stamped_by_its_address() -> None:
    """The snapshot has to be readable on its own years later, and ``display_name`` is nullable.

    The address is the one identifier every account in this platform has, which is why it is
    the fallback rather than the id — a trail row naming a uuid answers *who* with a second
    lookup that a deleted account makes impossible.
    """
    from app.db.models.auth import User
    from app.services.shema import author_name

    assert author_name(User(email="sem.nome@shema.test", display_name=None)) == (
        "sem.nome@shema.test"
    )
    assert author_name(None) == "unknown"


# --- scope on the write ---------------------------------------------------------------


async def test_a_write_reaches_exactly_as_far_as_a_read(
    client, db_session, shema_app, headers
) -> None:
    """*Writes are scoped by the same value as reads* — ``docs/shema.md`` §6.1.

    There is no third answer in the product: a regional coordinator who may read a region may
    write it, and one who may not read it is refused as if the record did not exist.
    """
    await make_shema_project(db_session, project_id="lao-theung", region_key=ShemaRegionKey.ASIA)
    response = await client.patch(
        f"{PROJECTS}/lao-theung",
        json={"statusComments": "x"},
        headers={**headers, "If-Match": '"1"'},
    )
    assert response.status_code == 404
