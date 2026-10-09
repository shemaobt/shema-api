"""The audit trail, end to end — OBT-577: *every write to the PME is recorded, dated and signed*.

One DoD line per group. **Every write route is accounted for** (:data:`COVERAGE` against the
built application's route table, so a route added later is red until somebody says where its
mark lands). **The marks are real** (the acts that had no ledger now write to
``shema_change_log``, and the ones that had still do). **The log holds no value** (a canary in a
contact never reaches the table or the feed). **The feed is read by the coordination and the
Admin, inside their regions, and a field a reader is handed reduced is not told** (OBT-556's rule,
applied to a second reader). **The table is append-only.**

No account here is a platform admin, except where a test says so: an admin passes every guard.
"""

from __future__ import annotations

import json

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select, text
from sqlalchemy.exc import DatabaseError

from app.core.database import Base
from app.db.models.shema_audit import ShemaRecordEdit
from app.db.models.shema_change_log import ShemaChangeLog
from app.db.models.shema_enums import ShemaRegionKey
from app.main import create_app
from app.services.shema._trail import COVERAGE, EXEMPT, LEDGER, TRAIL
from tests.test_shema.conftest import (
    PEOPLE,
    PREFIX,
    auth_header,
    make_intercessor,
    make_scoped_user,
    make_shema_project,
)
from tests.test_shema.test_eten import CREDITS, YEAR, listed

AUDIT = f"{PREFIX}/audit"
MEETINGS = f"{PREFIX}/meetings/log"

#: A contact no fixture shares, so a body or a table can be searched for it.
CANARY = "canario.do.audit@example.org"
AFRICA = ShemaRegionKey.AFRICA
SOUTH_AMERICA = ShemaRegionKey.SOUTH_AMERICA


async def _as(db_session, shema_app, role: str, *regions: ShemaRegionKey, email: str | None = None):
    user = await make_scoped_user(
        db_session,
        shema_app,
        email=email or f"{role.lower()}-{'-'.join(r.value for r in regions) or 'none'}@shema.test",
        role_key=role,
        regions=list(regions),
    )
    return user, await auth_header(db_session, user)


async def _log(db_session, **where) -> list[ShemaChangeLog]:
    stmt = select(ShemaChangeLog).order_by(ShemaChangeLog.occurred_at, ShemaChangeLog.id)
    for column, value in where.items():
        stmt = stmt.where(getattr(ShemaChangeLog, column) == value)
    return list(
        (await db_session.execute(stmt.execution_options(populate_existing=True))).scalars()
    )


# --- every write route says where its mark lands ------------------------------------------


def _write_routes() -> dict[str, set[str]]:
    routes: dict[str, set[str]] = {}
    for route in create_app().routes:
        if not isinstance(route, APIRoute) or not route.path.startswith(PREFIX):
            continue
        methods = set(route.methods or ()) - {"GET", "HEAD", "OPTIONS"}
        if methods:
            routes.setdefault(route.endpoint.__name__, set()).update(methods)
    return routes


def test_every_write_route_of_the_module_is_accounted_for() -> None:
    """A write route nobody classified is a write with no author — red until it is listed."""
    assert set(_write_routes()) == set(COVERAGE)


def test_a_ledger_names_a_table_that_exists_and_an_exemption_gives_its_reason() -> None:
    tables = set(Base.metadata.tables)
    for name, (kind, where) in COVERAGE.items():
        assert kind in {TRAIL, LEDGER, EXEMPT}, name
        assert where.strip(), name
        if kind == LEDGER:
            assert any(table in where for table in tables), (name, where)


def test_only_the_users_own_state_is_exempt() -> None:
    assert {name for name, (kind, _) in COVERAGE.items() if kind == EXEMPT} == {
        "read_notifications_mark",
        "write_notification_prefs",
    }


# --- the acts that had no ledger now have one ----------------------------------------------


async def test_an_intercessor_is_created_edited_reviewed_consented_and_erased_under_a_name(
    db_session, client, shema_app
) -> None:
    user, headers = await _as(db_session, shema_app, "resourceCircle")
    person = await make_intercessor(client, headers, contact=CANARY)
    pid = person["id"]

    assert (
        await client.patch(f"{PEOPLE}/{pid}", headers=headers, json={"name": "Maria S."})
    ).is_success
    assert (await client.post(f"{PEOPLE}/{pid}/review", headers=headers)).is_success
    put = await client.put(
        f"{PEOPLE}/{pid}/consents/directory", headers=headers, json={"basis": "verbal, in 2026"}
    )
    assert put.is_success
    assert (
        await client.delete(f"{PEOPLE}/{pid}/consents/directory", headers=headers)
    ).status_code == 204
    assert (await client.delete(f"{PEOPLE}/{pid}", headers=headers)).status_code == 204

    rows = await _log(db_session, subject="intercessor", subject_id=pid)
    assert [row.action for row in rows] == [
        "created",
        "updated",
        "reviewed",
        "consent-recorded",
        "consent-withdrawn",
        "removed",
    ]
    assert {row.actor_name for row in rows} == {user.display_name or user.email}
    assert {row.actor_id for row in rows} == {user.id}
    assert all(row.occurred_at is not None for row in rows)
    assert json.loads(rows[1].field_keys) == ["name"]


async def test_erasing_a_person_through_the_network_consent_is_one_removal(
    db_session, client, shema_app
) -> None:
    _user, headers = await _as(db_session, shema_app, "resourceCircle")
    pid = (await make_intercessor(client, headers))["id"]

    res = await client.delete(f"{PEOPLE}/{pid}/consents/network", headers=headers)

    assert res.status_code == 204
    assert [row.action for row in await _log(db_session, subject_id=pid)] == ["created", "removed"]


async def test_a_refused_act_leaves_no_mark(db_session, client, shema_app) -> None:
    """Staged before the helper that commits, and taken back when that helper refuses."""
    _user, headers = await _as(db_session, shema_app, "resourceCircle")

    for res in (
        await client.patch(f"{PEOPLE}/nobody", headers=headers, json={"name": "X"}),
        await client.delete(f"{PEOPLE}/nobody", headers=headers),
        await client.post(f"{PEOPLE}/nobody/review", headers=headers),
    ):
        assert res.status_code == 404
    # something else commits on the very same session afterwards
    await make_intercessor(client, headers)

    assert [row.action for row in await _log(db_session)] == ["created"]


async def test_the_log_holds_no_contact_and_no_name(db_session, client, shema_app) -> None:
    """The canary goes in as a contact and in as a rename; the table never holds it."""
    _user, headers = await _as(db_session, shema_app, "resourceCircle")
    pid = (await make_intercessor(client, headers, contact=CANARY, name="Nome Canario"))["id"]
    await client.patch(
        f"{PEOPLE}/{pid}", headers=headers, json={"contact": CANARY, "name": "Nome Canario 2"}
    )

    dump = json.dumps(
        [
            {column.name: str(getattr(row, column.name)) for column in ShemaChangeLog.__table__.c}
            for row in await _log(db_session)
        ]
    )
    assert CANARY not in dump
    assert "Nome Canario" not in dump
    assert not {c.name for c in ShemaChangeLog.__table__.c} & {"old_value", "new_value", "value"}


async def test_a_meeting_logged_replaced_and_undone_is_three_marks(
    db_session, client, shema_app
) -> None:
    user, headers = await _as(db_session, shema_app, "coordinator", AFRICA)
    body = {
        "meetingId": "bimestral_pi_campo",
        "scopeKey": "africa",
        "date": "2026-03-10",
        "notes": "private words",
    }
    assert (await client.post(MEETINGS, headers=headers, json=body)).is_success
    assert (
        await client.post(MEETINGS, headers=headers, json={**body, "notes": "again"})
    ).is_success
    res = await client.delete(f"{MEETINGS}/bimestral_pi_campo/africa/2026-B2", headers=headers)
    assert res.status_code == 204

    rows = await _log(db_session, subject="meeting")
    assert [row.action for row in rows] == ["created", "replaced", "removed"]
    assert {row.region_key for row in rows} == {"africa"}
    assert {row.actor_name for row in rows} == {user.display_name or user.email}
    assert "private words" not in json.dumps([row.field_keys for row in rows])


async def test_a_manual_eten_credit_is_marked_each_time_it_moves(
    db_session, client, shema_app
) -> None:
    _user, headers = await _as(db_session, shema_app, "coordinator", *ShemaRegionKey)
    await listed(db_session, "credito")
    for credits in (1, 2):
        res = await client.put(
            f"{CREDITS}/credito/{YEAR}", json={"credits": credits}, headers=headers
        )
        assert res.is_success

    rows = await _log(db_session, subject="eten_credit")
    assert [row.action for row in rows] == ["created", "updated"]
    assert {row.project_id for row in rows} == {"credito"}


# --- the log is append-only ---------------------------------------------------------------


@pytest.mark.parametrize(
    "verb", ["UPDATE shema_change_log SET actor_name = 'x'", "DELETE FROM shema_change_log"]
)
async def test_the_log_cannot_be_rewritten_or_emptied(db_session, client, shema_app, verb) -> None:
    _user, headers = await _as(db_session, shema_app, "resourceCircle")
    await make_intercessor(client, headers)

    with pytest.raises(DatabaseError):
        await db_session.execute(text(verb))
    await db_session.rollback()


# --- who reads the feed ------------------------------------------------------------------


async def _seed_feed(db_session, client, shema_app):
    """One act in Africa, one in South America, one that belongs to no region."""
    await make_shema_project(db_session, project_id="afr", region_key=AFRICA)
    await make_shema_project(db_session, project_id="sam", region_key=SOUTH_AMERICA)
    _c, circle = await _as(db_session, shema_app, "resourceCircle")
    await make_intercessor(client, circle)
    for pid, region in (("afr", AFRICA.value), ("sam", SOUTH_AMERICA.value)):
        db_session.add(
            ShemaChangeLog(
                subject="intake_link",
                action="revoked",
                project_id=pid,
                region_key=region,
                actor_name="Alguém",
            )
        )
    await db_session.commit()


async def test_a_regional_coordinator_reads_their_regions_and_the_acts_of_no_region(
    db_session, client, shema_app
) -> None:
    await _seed_feed(db_session, client, shema_app)
    _u, headers = await _as(db_session, shema_app, "coordinator", AFRICA)

    res = await client.get(AUDIT, headers=headers)

    assert res.status_code == 200
    seen = {(entry["subject"], entry["projectId"]) for entry in res.json()}
    assert seen == {("intercessor", None), ("intake_link", "afr")}


async def test_the_admin_reads_every_region(db_session, client, shema_app) -> None:
    await _seed_feed(db_session, client, shema_app)
    _u, headers = await _as(db_session, shema_app, "admin")

    res = await client.get(AUDIT, headers=headers)

    assert res.status_code == 200
    assert {entry["projectId"] for entry in res.json()} == {None, "afr", "sam"}


async def test_the_project_filter_narrows_the_feed(db_session, client, shema_app) -> None:
    await _seed_feed(db_session, client, shema_app)
    _u, headers = await _as(db_session, shema_app, "admin")

    res = await client.get(AUDIT, headers=headers, params={"projectId": "sam"})

    assert {entry["projectId"] for entry in res.json()} == {"sam"}


@pytest.mark.parametrize("role", ["resourceCircle", "obtLab"])
async def test_nobody_else_reads_who_changed_what(db_session, client, shema_app, role) -> None:
    _u, headers = await _as(db_session, shema_app, role, AFRICA)

    assert (await client.get(AUDIT, headers=headers)).status_code == 403


async def test_a_reader_with_no_region_reads_nothing(db_session, client, shema_app) -> None:
    await _seed_feed(db_session, client, shema_app)
    _u, headers = await _as(db_session, shema_app, "coordinator")

    assert (await client.get(AUDIT, headers=headers)).json() == []


async def test_the_feed_needs_a_sign_in(client) -> None:
    assert (await client.get(AUDIT)).status_code in {401, 403}


async def test_the_feed_carries_the_record_fields_with_both_sides(
    db_session, client, shema_app
) -> None:
    await make_shema_project(db_session, project_id="afr", region_key=AFRICA)
    db_session.add(
        ShemaRecordEdit(
            project_id="afr",
            version=2,
            field_key="statusComments",
            old_value="antes",
            new_value="depois",
            changed_by_name="Maria",
        )
    )
    await db_session.commit()
    _u, headers = await _as(db_session, shema_app, "coordinator", AFRICA)

    [entry] = (await client.get(AUDIT, headers=headers)).json()

    assert entry["source"] == "record"
    assert (entry["fields"], entry["oldValue"], entry["newValue"]) == (
        ["statusComments"],
        "antes",
        "depois",
    )
    assert entry["changedBy"] == "Maria"
    assert entry["changedAt"]


async def test_a_field_the_reader_is_handed_reduced_is_not_told_to_have_moved(
    db_session, client, shema_app
) -> None:
    """A team's health is read by the coordinator and not by the Admin role (OBT-553): so a
    move of ``healthNotes`` is on the coordinator's feed and not on the Admin's, exactly as the
    409 leaves it out (OBT-556)."""
    await make_shema_project(db_session, project_id="afr", region_key=AFRICA)
    for key in ("healthNotes", "statusComments"):
        db_session.add(
            ShemaRecordEdit(project_id="afr", version=2, field_key=key, changed_by_name="Maria")
        )
    await db_session.commit()
    _c, coordinator = await _as(db_session, shema_app, "coordinator", AFRICA)
    _a, admin = await _as(db_session, shema_app, "admin")

    told_coordinator = {
        e["fields"][0] for e in (await client.get(AUDIT, headers=coordinator)).json()
    }
    told_admin = {e["fields"][0] for e in (await client.get(AUDIT, headers=admin)).json()}

    assert told_coordinator == {"healthNotes", "statusComments"}
    assert told_admin == {"statusComments"}


async def test_the_feed_is_newest_first_and_bounded(db_session, client, shema_app) -> None:
    await make_shema_project(db_session, project_id="afr", region_key=AFRICA)
    for n in range(5):
        db_session.add(
            ShemaChangeLog(
                subject="intake_link",
                action=f"a{n}",
                project_id="afr",
                region_key="africa",
                actor_name="x",
            )
        )
        await db_session.commit()
    _u, headers = await _as(db_session, shema_app, "coordinator", AFRICA)

    body = (await client.get(AUDIT, headers=headers, params={"limit": 3})).json()

    assert len(body) == 3
    assert [e["changedAt"] for e in body] == sorted((e["changedAt"] for e in body), reverse=True)
    assert (await client.get(AUDIT, headers=headers, params={"limit": 0})).status_code == 422
