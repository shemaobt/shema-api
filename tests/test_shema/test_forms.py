"""Definitions, submissions and where a submission goes — the other five DoD lines.

* *Definitions stored and versioned; submissions record the version they answered* — an edited
  spec cuts a new version, the old one stays readable, and the row points at the one it
  answered rather than at the newest.
* *Submissions validated server-side against their definition and rejected whole on mismatch* —
  every fault named at once, and **nothing archived** for a submission that failed.
* *Submissions trigger notification to the right recipients* — by role **and** by region, with
  the prayer half behind the consent gate.
* *Sensitive-country and scope rules applied to anything the form surfaces* — the inbox is
  scoped like every read in this module, and the one shape that leaves coordination is the
  intake form, which ``tests/test_shema/test_intake_link.py`` holds to the minimum.

The import path is here too, because it is the half that makes the deposit worth anything: an
imported progress change goes through ``save_project`` with a ``ProgressSource``, which is
BE-06's own seam, and the trail cannot tell it from a typed save afterwards except by the two
columns that say where it came from.
"""

import json

import pytest
from sqlalchemy import select

from app.db.models.notification import Notification
from app.db.models.shema_enums import ShemaPrayerVisibility, ShemaRegionKey
from app.db.models.shema_form import ShemaFormDefinition, ShemaSubmission
from app.db.models.shema_progress import ShemaProgressEntry
from app.services.shema._submission_notices import ARRIVAL_EVENT, PRAYER_EVENT
from app.utils.shema_forms import PULSE_FORM_TYPE, PULSE_KIND
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user, make_shema_project

LINKS = f"{PREFIX}/intake-links"
SUBMISSIONS = f"{PREFIX}/forms/submissions"


def book(chapters: int, translated: int) -> dict:
    return {
        "id": "mrk",
        "name": "Marcos",
        "chapters": chapters,
        "translated": translated,
        "communityChecked": 0,
        "mentorApproved": 0,
    }


def answers(**overrides) -> dict:
    return {"submittedBy": "Kuaray", "period": "2026-09", **overrides}


@pytest.fixture()
async def coordinator(db_session, shema_app):
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


@pytest.fixture()
async def project(db_session):
    return await make_shema_project(
        db_session,
        project_id="guarani-mbya",
        region_key=ShemaRegionKey.SOUTH_AMERICA,
        language_name="Guarani Mbyá",
    )


async def a_link(client, headers, project_id: str = "guarani-mbya") -> dict:
    response = await client.post(LINKS, json={"projectId": project_id}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def answer(client, token: str, version: int = 1, **kwargs):
    return await client.post(
        f"{PREFIX}/intake/{token}",
        json={"definitionVersion": version, "answers": answers(**kwargs)},
    )


# --- stored and versioned -------------------------------------------------------------


async def test_the_definition_is_published_once_and_reused(
    client, db_session, shema_app, headers, project
) -> None:
    """Publishing is by content, so a second link cuts no second version.

    Without this, every link a coordinator mints would retire the previous definition and the
    version number would count links rather than changes to the form.
    """
    first = await a_link(client, headers)
    second = await a_link(client, headers)

    assert first["definitionVersion"] == second["definitionVersion"] == 1
    rows = (await db_session.execute(select(ShemaFormDefinition))).scalars().all()
    assert len(rows) == 1


async def test_an_edited_spec_cuts_a_new_version_and_leaves_the_old_one_standing(
    client, db_session, shema_app, headers, project, monkeypatch
) -> None:
    """**The DoD's first line, as the failure it prevents.**

    A definition edited in place rewrites the meaning of every answer already given to it. Here
    the spec moves between two links: the first link keeps answering version 1 — the form it was
    minted with and the one the leader was shown — and the second gets version 2. Both rows
    stand, and a submission filed under either stays readable against the words it answered.
    """
    import app.services.shema._form_definitions as definitions
    from app.utils.shema_forms import PULSE_FIELDS, FormField, ShemaFieldType, field_specs

    old_link = await a_link(client, headers)

    grown = (
        *PULSE_FIELDS,
        FormField(
            key="rainfall",
            type=ShemaFieldType.TEXT,
            required=False,
            label_key="forms_q_rainfall",
        ),
    )
    monkeypatch.setattr(
        definitions, "field_specs", lambda kind: [f.as_spec() for f in grown] if kind else []
    )
    new_link = await a_link(client, headers)

    assert field_specs  # the real one is still importable; only the service's view moved
    assert old_link["definitionVersion"] == 1
    assert new_link["definitionVersion"] == 2

    still_v1 = await client.get(f"{PREFIX}/intake/{old_link['token']}")
    assert still_v1.json()["definitionVersion"] == 1
    assert "rainfall" not in {f["key"] for f in still_v1.json()["fields"]}

    now_v2 = await client.get(f"{PREFIX}/intake/{new_link['token']}")
    assert "rainfall" in {f["key"] for f in now_v2.json()["fields"]}


async def test_a_submission_records_the_version_it_answered(
    client, db_session, shema_app, headers, project
) -> None:
    link = await a_link(client, headers)

    assert (await answer(client, link["token"])).status_code == 202

    row = (await db_session.execute(select(ShemaSubmission))).scalar_one()
    definition = await db_session.get(ShemaFormDefinition, row.definition_id)
    assert definition is not None
    assert definition.version == 1
    assert row.intake_link_id == link["id"]

    inbox = await client.get(SUBMISSIONS, headers=headers)
    assert inbox.json()[0]["definitionVersion"] == 1
    assert inbox.json()[0]["kind"] == PULSE_KIND


# --- rejected whole -------------------------------------------------------------------


async def test_a_submission_that_does_not_match_is_rejected_whole(
    client, db_session, shema_app, headers, project
) -> None:
    """Nothing is archived, which is the half the status code does not say.

    *Never store an unvalidated payload to clean later* — later does not come, and what is left
    is a column nobody can interpret.
    """
    link = await a_link(client, headers)

    response = await client.post(
        f"{PREFIX}/intake/{link['token']}",
        json={"definitionVersion": 1, "answers": {"period": "not-a-month"}},
    )

    assert response.status_code == 400
    assert (await db_session.execute(select(ShemaSubmission))).first() is None


async def test_every_fault_is_named_at_once(
    client, db_session, shema_app, headers, project
) -> None:
    """A leader on a bad connection pays once for one form, not once per mistake."""
    link = await a_link(client, headers)

    response = await client.post(
        f"{PREFIX}/intake/{link['token']}",
        json={
            "definitionVersion": 1,
            "answers": {"period": "septembro", "prayerVisibility": "todo-mundo", "voice": 7},
        },
    )

    detail = response.json()["detail"]
    assert response.status_code == 400
    assert "submittedBy: required" in detail
    assert "period:" in detail
    assert "prayerVisibility:" in detail
    assert "voice: expected text" in detail


async def test_a_field_the_form_does_not_have_is_a_fault(
    client, db_session, shema_app, headers, project
) -> None:
    """A client answering a field this version has not got is answering a different form.
    Dropping it silently files an answer with a hole nothing downstream can see."""
    link = await a_link(client, headers)

    response = await answer(client, link["token"], rainfall="heavy")

    assert response.status_code == 400
    assert "rainfall: this form has no such field" in response.json()["detail"]


async def test_a_submission_quoting_another_version_than_the_link_is_refused(
    client, db_session, shema_app, headers, project
) -> None:
    """The version comes off the link and the client's is checked against it, never used to
    select one — reading an answer against today's spec would invent which words it answered."""
    link = await a_link(client, headers)

    response = await answer(client, link["token"], version=2)

    assert response.status_code == 400
    assert "Reload the form" in response.json()["detail"]


async def test_a_progress_row_longer_than_its_book_is_refused_by_the_same_path(
    client, db_session, shema_app, headers, project
) -> None:
    """Not re-checked here: the rows go to ``ShemaProjectUpdate``, where BE-06 already refuses
    a book that is not one of the 66 and a scope longer than the book. A second reading of what
    a progress row is would drift from that one, and the drift would show as a Pulse the console
    can save and the import cannot."""
    await a_link(client, headers)

    response = await client.post(
        f"{SUBMISSIONS}",
        json={"projectId": "guarani-mbya", "answers": answers(bookProgress=[book(16, 30)])},
        headers={**headers, "If-Match": '"1"'},
    )

    assert response.status_code == 400
    assert "book_progress.0" in response.json()["detail"]
    # Nothing archived and nothing announced: the record's refusal is checked before the write,
    # so a row no coordinator could ever apply does not land in the inbox looking applicable.
    assert (await db_session.execute(select(ShemaSubmission))).first() is None
    assert (await db_session.execute(select(ShemaProgressEntry))).first() is None


# --- archived byte-identically, and idempotent ----------------------------------------


async def test_the_archive_keeps_the_bytes_that_arrived(
    client, db_session, shema_app, headers, project
) -> None:
    """Not a re-serialisation of what the server understood — what the leader sent."""
    link = await a_link(client, headers)
    await answer(client, link["token"], voice="A colheita foi boa.")

    row = (await db_session.execute(select(ShemaSubmission))).scalar_one()
    kept = json.loads(row.archived_payload)

    assert kept["answers"]["voice"] == "A colheita foi boa."
    assert kept["definitionVersion"] == 1

    detail = await client.get(f"{SUBMISSIONS}/{row.id}", headers=headers)
    assert detail.json()["answers"]["voice"] == "A colheita foi boa."
    definition = await db_session.get(ShemaFormDefinition, row.definition_id)
    assert definition is not None
    assert {f["key"] for f in detail.json()["fields"]} == {
        field["key"] for field in definition.fields
    }


async def test_a_second_arrival_of_the_same_bytes_is_a_no_op(
    client, db_session, shema_app, headers, project
) -> None:
    """*A double import is a no-op* — one archive, one notice, and no second progress entry.

    This is the shape a leader on a bad connection actually produces: tap send, see nothing
    happen, tap send again.
    """
    link = await a_link(client, headers)

    assert (await answer(client, link["token"])).status_code == 202
    assert (await answer(client, link["token"])).status_code == 202

    rows = (await db_session.execute(select(ShemaSubmission))).scalars().all()
    assert len(rows) == 1

    arrivals = (
        (
            await db_session.execute(
                select(Notification).where(Notification.event_type == ARRIVAL_EVENT)
            )
        )
        .scalars()
        .all()
    )
    assert len(arrivals) == 1


async def test_a_resend_after_the_spec_moved_is_still_a_no_op(
    client, db_session, shema_app, headers, project, monkeypatch
) -> None:
    """The sharp edge where *versioned* and *idempotent* meet.

    The same bytes arrive twice with a new definition cut in between. The second arrival is a
    no-op — it is not re-checked against today's spec, because re-checking would refuse a
    submission that is already archived, which is the opposite of idempotent. And what it
    answers with is the version the **stored** row answered, not the one standing now: saying
    otherwise would claim the leader answered words they never saw.
    """
    import app.services.shema._form_definitions as definitions
    from app.utils.shema_forms import PULSE_FIELDS

    body = {"projectId": "guarani-mbya", "answers": answers(voice="A colheita foi boa.")}
    first = await client.post(SUBMISSIONS, json=body, headers={**headers, "If-Match": '"1"'})
    assert first.status_code == 201
    assert first.json()["definitionVersion"] == 1

    narrowed = tuple(field for field in PULSE_FIELDS if field.key != "voice")
    monkeypatch.setattr(
        definitions, "field_specs", lambda kind: [f.as_spec() for f in narrowed] if kind else []
    )
    await a_link(client, headers)  # cuts version 2, which no longer has `voice`

    again = await client.post(SUBMISSIONS, json=body, headers={**headers, "If-Match": '"1"'})

    assert again.status_code == 201
    assert again.json()["id"] == first.json()["id"]
    assert again.json()["definitionVersion"] == 1
    assert len((await db_session.execute(select(ShemaSubmission))).scalars().all()) == 1


# --- routed to the right recipients ---------------------------------------------------


async def test_a_submission_reaches_the_coordinators_and_mentors_of_its_own_region(
    client, db_session, shema_app, headers, coordinator, project
) -> None:
    """FE-44 §5.8's ``field`` audience: ``coordinator`` and ``obtLab`` — **and the region**.

    A notice that went to every coordinator would tell a coordinator in Oceania that a project
    in Africa reported, which is the collection read leaking one row at a time through a channel
    nobody audits.
    """
    mentor = await make_scoped_user(
        db_session,
        shema_app,
        email="mentor@shema.test",
        role_key="obtLab",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )
    elsewhere = await make_scoped_user(
        db_session,
        shema_app,
        email="oceania@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.OCEANIA],
    )
    link = await a_link(client, headers)

    await answer(client, link["token"])

    told = {
        row.user_id
        for row in (
            (
                await db_session.execute(
                    select(Notification).where(Notification.event_type == ARRIVAL_EVENT)
                )
            )
            .scalars()
            .all()
        )
    }
    assert told == {coordinator.id, mentor.id}
    assert elsewhere.id not in told


async def test_an_unshared_prayer_request_reaches_the_resource_circle_through_nothing(
    client, db_session, shema_app, headers, project
) -> None:
    """*An unauthorized prayer request is absent from all four output paths*, and notifications
    is the fourth. ``prayer_visibility`` is NULL here, and NULL means ``coordenacao``."""
    await make_scoped_user(
        db_session,
        shema_app,
        email="circulo@shema.test",
        role_key="resourceCircle",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )
    link = await a_link(client, headers)

    await answer(client, link["token"], prayerRequest="Orem pela seca.")

    prayer = (
        await db_session.execute(
            select(Notification).where(Notification.event_type == PRAYER_EVENT)
        )
    ).first()
    assert prayer is None


async def test_a_shared_prayer_request_reaches_the_resource_circle_alone(
    client, db_session, shema_app, headers, coordinator, project
) -> None:
    """``resourceCircle`` **alone** — the one row of FE-44 §5.8's audience table with a single
    role in it, and not an oversight to be tidied up."""
    circle = await make_scoped_user(
        db_session,
        shema_app,
        email="circulo@shema.test",
        role_key="resourceCircle",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )
    project.prayer_visibility = ShemaPrayerVisibility.REDE
    await db_session.commit()
    link = await a_link(client, headers)

    await answer(client, link["token"], prayerRequest="Orem pela seca.")

    prayer = (
        (
            await db_session.execute(
                select(Notification).where(Notification.event_type == PRAYER_EVENT)
            )
        )
        .scalars()
        .all()
    )
    assert {row.user_id for row in prayer} == {circle.id}
    assert all("Orem pela seca" not in row.body for row in prayer)


async def test_no_notification_body_names_where_the_project_is(
    client, db_session, shema_app, headers, project
) -> None:
    """A notification row is a copy of data in a table with different readers and no region
    predicate of its own. The copy is the leak, whatever the body says about withholding."""
    project.location = "Sudão"
    project.team = "YWAM Cartum"
    project.sensitive_country = True
    await db_session.commit()
    link = await a_link(client, headers)

    await answer(client, link["token"])

    rows = (await db_session.execute(select(Notification))).scalars().all()
    assert rows
    for row in rows:
        assert "Sudão" not in row.body and "Sudão" not in row.title
        assert "Cartum" not in row.body and "Cartum" not in row.title


# --- the import, through BE-06's own write path ---------------------------------------


async def test_an_import_writes_the_progress_through_the_same_path_as_a_typed_save(
    client, db_session, shema_app, headers, project
) -> None:
    """**FE-44 §9.9's requirement**, and the two columns that make the difference visible.

    The entry is written by ``_progress.record_progress`` — the module's single progress
    writer — and carries ``fromField`` and ``formType``, which the ficha's own ``PATCH`` never
    fills. That is what makes an imported update and a typed one indistinguishable afterwards
    except by where they say they came from.
    """
    link = await a_link(client, headers)
    await answer(client, link["token"], bookProgress=[book(16, 9)])
    submission = (await db_session.execute(select(ShemaSubmission))).scalar_one()

    response = await client.post(
        f"{SUBMISSIONS}/{submission.id}/import",
        headers={**headers, "If-Match": '"1"'},
    )

    assert response.status_code == 200, response.text
    assert response.json()["appliedAt"] is not None

    await db_session.refresh(project)
    assert project.translated_units == 9
    assert project.total_units == 16

    entry = (await db_session.execute(select(ShemaProgressEntry))).scalar_one()
    assert entry.from_field == "Kuaray"
    assert entry.form_type == PULSE_FORM_TYPE


async def test_a_double_import_does_not_double_a_chapter_count(
    client, db_session, shema_app, headers, project
) -> None:
    """*A leader who forwards the same file twice must not double a chapter count.*

    Two nets and both are asserted: ``applied_at`` stops the second apply, and underneath it
    the data agrees — a Pulse carries **absolute** counts, so re-applying the same numbers moves
    nothing anyway.
    """
    link = await a_link(client, headers)
    await answer(client, link["token"], bookProgress=[book(16, 9)])
    submission = (await db_session.execute(select(ShemaSubmission))).scalar_one()
    route = f"{SUBMISSIONS}/{submission.id}/import"

    first = await client.post(route, headers={**headers, "If-Match": '"1"'})
    await db_session.refresh(project)
    version_after_first = project.version

    second = await client.post(route, headers={**headers, "If-Match": f'"{version_after_first}"'})

    assert first.status_code == second.status_code == 200
    await db_session.refresh(project)
    assert project.translated_units == 9
    assert project.version == version_after_first
    assert len((await db_session.execute(select(ShemaProgressEntry))).scalars().all()) == 1


async def test_a_coordinator_can_file_and_apply_an_answer_that_arrived_some_other_way(
    client, db_session, shema_app, headers, project
) -> None:
    """The Pulse's whole point is that the person with the information is often offline, so the
    answer arrives on paper or read out over a bad line. Same validation, same archive, same
    idempotency — and an actor the audit trail can name.

    **No link is minted anywhere in this test, and that is part of what it asserts.** The spec
    is published on this write as it is on the link's, so filing an answer for a leader who
    never used a link is not gated on somebody having minted one for them.
    """
    response = await client.post(
        SUBMISSIONS,
        json={"projectId": "guarani-mbya", "answers": answers(bookProgress=[book(16, 4)])},
        headers={**headers, "If-Match": '"1"'},
    )

    assert response.status_code == 201, response.text
    assert response.json()["definitionVersion"] == 1
    await db_session.refresh(project)
    assert project.translated_units == 4


async def test_an_import_from_a_stale_version_is_refused(
    client, db_session, shema_app, headers, project
) -> None:
    """An import is a write of the record and is guarded exactly as a typed save is. A guard
    that can be skipped is last-write-wins one forgotten header away, and BE-06 made it
    required for that reason — a form writing the record does not make it less required."""
    response = await client.post(
        SUBMISSIONS,
        json={"projectId": "guarani-mbya", "answers": answers(bookProgress=[book(16, 4)])},
        headers={**headers, "If-Match": '"7"'},
    )

    assert response.status_code == 409
    assert (await db_session.execute(select(ShemaSubmission))).scalar_one().applied_at is None


async def test_an_empty_prayer_answer_does_not_delete_what_is_already_there(
    client, db_session, shema_app, headers, project
) -> None:
    """FE-44 §8.2's sharp case: *a save that writes* ``prayerRequests: ""`` *unconditionally
    deletes an existing request as a side effect of an unrelated action* — and a monthly form
    with an untouched prayer box would do exactly that, every month, to the team most likely to
    have written something the month before."""
    project.prayer_requests = "Orem pela travessia do rio."
    await db_session.commit()

    response = await client.post(
        SUBMISSIONS,
        json={"projectId": "guarani-mbya", "answers": answers(prayerRequest="  ")},
        headers={**headers, "If-Match": '"1"'},
    )

    assert response.status_code == 201
    await db_session.refresh(project)
    assert project.prayer_requests == "Orem pela travessia do rio."


async def test_the_submission_detail_serves_only_what_the_record_does_not(
    client, db_session, shema_app, headers, project
) -> None:
    """**The read answers what maps to no column, and it closes a hole while doing it.**

    An answer the import applies is readable on the record, behind the record's own surface;
    an answer that maps to nothing is readable nowhere else and is what this read is for. The
    hole the rule closes is real: this route admits **any** member in the caller's region —
    an OBT Lab mentor reads a Pulse as legitimately as a coordinator, and ``require_role``
    cannot say *or* — so without it a ``resourceCircle`` account, which is the prayer wall's
    own audience, could read an archived prayer request for a team that consented to
    ``coordenacao`` and nothing more.
    """
    link = await a_link(client, headers)
    await answer(
        client,
        link["token"],
        voice="A colheita foi boa.",
        blockers="O gerador queimou.",
        prayerRequest="Orem pela travessia do rio.",
        prayerVisibility="coordenacao",
        bookProgress=[book(16, 9)],
    )
    row = (await db_session.execute(select(ShemaSubmission))).scalar_one()

    circle = await make_scoped_user(
        db_session,
        shema_app,
        email="circulo@shema.test",
        role_key="resourceCircle",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )
    response = await client.get(
        f"{SUBMISSIONS}/{row.id}", headers=await auth_header(db_session, circle)
    )

    assert response.status_code == 200
    served = response.json()["answers"]
    assert set(served) == {"submittedBy", "period", "voice", "blockers"}
    assert "Orem pela travessia do rio." not in response.text
    assert "coordenacao" not in response.text


# --- scope ----------------------------------------------------------------------------


async def test_the_inbox_is_scoped_like_every_other_read_in_this_module(
    client, db_session, shema_app, headers, project
) -> None:
    """A submission on a project the caller cannot reach is not in their inbox and cannot be
    opened by id."""
    await make_shema_project(db_session, project_id="wolof-dakar", region_key=ShemaRegionKey.AFRICA)
    # A coordinator of the other region, not a global one: minting is a coordinator's act, and
    # ``globalStrategist`` does not hold that role.
    africa = await make_scoped_user(
        db_session,
        shema_app,
        email="africa@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.AFRICA],
    )
    elsewhere = await a_link(
        client, await auth_header(db_session, africa), project_id="wolof-dakar"
    )
    await answer(client, elsewhere["token"])

    mine = await client.get(SUBMISSIONS, headers=headers)
    assert mine.json() == []

    row = (await db_session.execute(select(ShemaSubmission))).scalar_one()
    assert (await client.get(f"{SUBMISSIONS}/{row.id}", headers=headers)).status_code == 404


async def test_an_import_cannot_reach_a_project_outside_the_scope(
    client, db_session, shema_app, headers, project
) -> None:
    await make_shema_project(db_session, project_id="wolof-dakar", region_key=ShemaRegionKey.AFRICA)

    response = await client.post(
        SUBMISSIONS,
        json={"projectId": "wolof-dakar", "answers": answers()},
        headers={**headers, "If-Match": '"1"'},
    )

    assert response.status_code == 404
    assert (await db_session.execute(select(ShemaSubmission))).first() is None


# --- the wiring, read off the built application ---------------------------------------


def test_the_app_key_here_is_the_modules_own() -> None:
    """``get_shema_app_id`` names the key outside the module, where its three siblings do.

    The pair is kept honest here rather than by a convention, exactly as
    ``test_notifications.py`` keeps ``get_rr_app_id`` honest against the resource-request
    module's own constant.
    """
    from app.api.shema._deps import APP_KEY
    from app.services.notifications.get_shema_app_id import SHEMA_APP_KEY

    assert SHEMA_APP_KEY == APP_KEY


def test_the_limited_routes_resolve_their_dependencies() -> None:
    """``@limiter.limit`` wraps the handler, and FastAPI resolves a string annotation against
    ``call.__globals__`` — which for a wrapped function is *slowapi's* module.

    With ``from __future__ import annotations`` in the router, ``Db`` does not resolve there,
    the parameter stops being a dependency and becomes a required query parameter, and every
    call to a limited route answers 422 before the handler runs. Caught here because the symptom
    is a mystery 422 on the one route in this module that has no guard to blame.
    """
    from fastapi.routing import APIRoute

    from app.main import create_app

    app = create_app()
    intake = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == f"{PREFIX}/intake/{{token}}"
    ]
    assert len(intake) == 2
    for route in intake:
        names = {param.name for param in route.dependant.query_params}
        assert names == set(), f"{sorted(route.methods)} resolved dependencies as query params"


def test_only_the_pulse_is_archivable() -> None:
    """``ReceivedSubmission.kind`` is ``ArchivedKind`` and the table has no ``kind`` column.

    A server that archived a ``health`` submission would have landed a kind that by definition
    never travelled: the Avaliação de Saúde is filled in-app, produces no file, and its history
    belongs to ``shema_health_assessments``.
    """
    assert PULSE_KIND == "pulso"
    assert not hasattr(ShemaSubmission, "kind")


def test_no_file_of_this_issue_spells_a_guarded_column() -> None:
    """**Why BE-12 adds no line to** ``test_privacy_owners.py``'s **allowlist.**

    The mapping from a form field to a record column lives in ``app/utils/shema_forms.py`` —
    data, outside both guarded packages — so the ingest hands the definition's own strings to
    ``ShemaProjectUpdate`` and never writes a guarded name itself. That is what keeps
    ``app/services/shema/_consent.py`` the single reader of the three prayer columns while a
    form writes two of them.

    Read off the source rather than inferred from the allowlist being short, so a later
    simplification that "inlines the mapping" fails here — where the reason is written — rather
    than in BE-04's file, where the fix would look like adding one more owner.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "app"
    guarded = ("prayer_requests", "prayer_visibility", "prayer_requests_audio")
    mine = [
        root / "services" / "shema" / name
        for name in (
            "import_submission.py",
            "receive_submission.py",
            "_form_validation.py",
            "_submission_archive.py",
            "_submission_notices.py",
            "read_submission.py",
            "read_intake_form.py",
            "create_intake_link.py",
        )
    ] + [root / "api" / "shema" / "forms.py"]

    offenders = {
        source.name: [column for column in guarded if column in source.read_text(encoding="utf-8")]
        for source in mine
    }
    assert {name: found for name, found in offenders.items() if found} == {}
