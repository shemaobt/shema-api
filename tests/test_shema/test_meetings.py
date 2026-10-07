"""The Rhythm's log: one entry per meeting, region and period, and who may read and write it.

What is tested is what OBT-399's Definition of Done and GATE-02 ask for, not that SQLAlchemy
stores a string: that the log is a listening tracker keyed by ``(meeting, scope, period)`` in
which a second log replaces the first - including when two writes race; that the meeting set is
global and lives in code; that the notes are the meeting's artifact and travel with it; and that
the scope holds on both axes - the region the caller reaches, and the audience the notes are for.

**No negative test here uses a platform-admin account**: an admin passes every guard, so a
refusal proved with one would prove nothing (``tests/test_shema/conftest.py``).
"""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError

from app.core.database import Base
from app.core.exceptions import AuthorizationError, UnprocessableValueError
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_meeting import ShemaMeetingLogEntry
from app.models.shema_meeting import MeetingLogCreate, MeetingLogEntry
from app.services.shema import _meeting_log, log_meeting
from app.services.shema._scope import RegionScope, reaches
from app.utils.shema_derivations import Cadence
from app.utils.shema_meetings import MEETING_CADENCES, ShemaMeetingId
from tests.baker import make_app, make_role, make_user, make_user_app_role
from tests.test_shema.conftest import auth_header, make_scoped_user

LOG = "/api/shema/meetings/log"
AFRICA = ShemaRegionKey.AFRICA
ASIA = ShemaRegionKey.ASIA

BIMESTRAL = "bimestral_pi_campo"
TRIMESTRAL = "trimestral_pi_pontes"
SEMESTRAL = "semestral_member_care"


async def _member(
    db_session, shema_app, *, role: str = "coordinator", regions=(AFRICA,), email=None
):
    """A non-admin account holding one Shemá role, scoped to ``regions``."""
    user = await make_scoped_user(
        db_session,
        shema_app,
        email=email or f"{role}.{'-'.join(r.value for r in regions) or 'none'}@shema.test",
        role_key=role,
        regions=list(regions),
    )
    return user, await auth_header(db_session, user)


def _body(
    meeting_id: str = BIMESTRAL, scope_key: str = "africa", day: str = "2026-03-10", notes=""
):
    return {"meetingId": meeting_id, "scopeKey": scope_key, "date": day, "notes": notes}


async def _rows(db_session) -> list[ShemaMeetingLogEntry]:
    stmt = (
        select(ShemaMeetingLogEntry)
        .order_by(ShemaMeetingLogEntry.period)
        .execution_options(populate_existing=True)
    )
    return list((await db_session.execute(stmt)).scalars())


async def _insert(db_session, *, meeting_id=BIMESTRAL, scope_key="africa", period="2026-B2"):
    """A row written straight to the table - for the states no request can produce."""
    await db_session.execute(
        insert(ShemaMeetingLogEntry).values(
            id=f"{meeting_id}-{scope_key}-{period}",
            meeting_id=meeting_id,
            scope_key=scope_key,
            period=period,
            meeting_date=date(2026, 3, 10),
            notes="",
        )
    )
    await db_session.commit()


# --- one entry per (meeting, scope, period) -----------------------------------------------


async def test_a_second_log_for_the_same_period_replaces_the_first(
    db_session, client, shema_app
) -> None:
    """**The DoD's first line.** Same meeting, region and period: one row, the second one's day
    and notes, and a 200 that says it replaced rather than a second 201."""
    _user, headers = await _member(db_session, shema_app)

    first = await client.post(LOG, headers=headers, json=_body(day="2026-03-10", notes="first"))
    second = await client.post(LOG, headers=headers, json=_body(day="2026-04-02", notes="second"))

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()["period"] == second.json()["period"] == "2026-B2"
    rows = await _rows(db_session)
    assert [(r.period, r.meeting_date, r.notes) for r in rows] == [
        ("2026-B2", date(2026, 4, 2), "second")
    ]
    listed = (await client.get(LOG, headers=headers)).json()
    assert listed == [second.json()]


async def test_a_log_in_another_period_is_a_second_entry(db_session, client, shema_app) -> None:
    _user, headers = await _member(db_session, shema_app)

    await client.post(LOG, headers=headers, json=_body(day="2026-02-27"))
    res = await client.post(LOG, headers=headers, json=_body(day="2026-03-01"))

    assert res.status_code == 201
    assert [r.period for r in await _rows(db_session)] == ["2026-B1", "2026-B2"]


def _payload(**overrides) -> MeetingLogCreate:
    return MeetingLogCreate.model_validate({**_body(), **overrides})


async def test_a_log_that_loses_the_race_to_the_first_insert_replaces_it(
    db_session, shema_app, monkeypatch
) -> None:
    """Two coordinators log the same period at once and both read *nothing*. The unique
    constraint refuses the second insert, and the write is retried as the replacement it is -
    not a 500, and not a second row."""
    user, _headers = await _member(db_session, shema_app)
    await _insert(db_session, period="2026-B2")

    real = _meeting_log.find_log
    blind = {"once": True}

    async def find_log_that_missed_the_first_insert(*args, **kwargs):
        if blind.pop("once", False):
            return None
        return await real(*args, **kwargs)

    monkeypatch.setattr(_meeting_log, "find_log", find_log_that_missed_the_first_insert)
    logged = await log_meeting(
        db_session,
        RegionScope(global_=False, regions=frozenset({"africa"})),
        _payload(notes="the later write"),
        actor=user,
        app_key="shema",
        today=date(2026, 9, 27),
    )

    assert logged.replaced is True
    assert [(r.period, r.notes) for r in await _rows(db_session)] == [
        ("2026-B2", "the later write")
    ]


async def test_a_log_whose_row_was_undone_mid_write_is_written_fresh(
    db_session, shema_app, monkeypatch
) -> None:
    """The mirror race: an undo deletes the row between the write's read and its update. The
    update then matches nothing (``StaleDataError``), and the retry inserts the entry afresh."""
    user, _headers = await _member(db_session, shema_app)
    await _insert(db_session, period="2026-B2")

    real = _meeting_log.find_log
    once = {"undo": True}

    async def find_log_then_lose_it_to_an_undo(db, *args, **kwargs):
        row = await real(db, *args, **kwargs)
        if row is not None and once.pop("undo", False):
            gone = delete(ShemaMeetingLogEntry).where(ShemaMeetingLogEntry.id == row.id)
            await db.execute(gone.execution_options(synchronize_session=False))
        return row

    monkeypatch.setattr(_meeting_log, "find_log", find_log_then_lose_it_to_an_undo)
    logged = await log_meeting(
        db_session,
        RegionScope(global_=False, regions=frozenset({"africa"})),
        _payload(notes="written again"),
        actor=user,
        app_key="shema",
        today=date(2026, 9, 27),
    )

    assert logged.replaced is False
    assert [(r.period, r.notes) for r in await _rows(db_session)] == [("2026-B2", "written again")]


async def test_a_second_collision_is_raised_rather_than_retried_forever(
    db_session, shema_app, monkeypatch
) -> None:
    user, _headers = await _member(db_session, shema_app)
    await _insert(db_session, period="2026-B2")

    async def never_finds(*_args, **_kwargs):
        return None

    monkeypatch.setattr(_meeting_log, "find_log", never_finds)
    with pytest.raises(IntegrityError):
        await log_meeting(
            db_session,
            RegionScope(global_=False, regions=frozenset({"africa"})),
            _payload(),
            actor=user,
            app_key="shema",
            today=date(2026, 9, 27),
        )


async def test_the_log_is_a_listening_tracker_with_exactly_the_frozen_fields() -> None:
    """**The DoD's first and fourth lines, as a pin on the shape.** The table holds the frozen
    ``MeetingLogEntry`` and its own bookkeeping, nothing else: no series, no occurrence, no hour,
    no timezone - and no URL or storage key, because no meeting produces a stored file and the
    log opens no upload path. The day is a ``Date``, and the key is the trio."""
    table = ShemaMeetingLogEntry.__table__
    assert {c.name for c in table.columns} == {
        "id",
        "meeting_id",
        "scope_key",
        "period",
        "meeting_date",
        "notes",
        "created_at",
        "updated_at",
    }
    assert type(table.c.meeting_date.type).__name__ == "Date"
    uniques = [
        tuple(c.name for c in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    ]
    assert uniques == [("meeting_id", "scope_key", "period")]

    assert set(MeetingLogCreate.model_fields) == {"meeting_id", "scope_key", "date", "notes"}
    assert set(MeetingLogEntry.model_fields) == {
        "meeting_id",
        "scope_key",
        "period",
        "date",
        "notes",
    }


async def test_the_client_cannot_state_the_period(db_session, client, shema_app) -> None:
    """The period is the server's to derive (FE-44 §9.7): a body that carries one is refused,
    not quietly trusted."""
    _user, headers = await _member(db_session, shema_app)

    res = await client.post(LOG, headers=headers, json={**_body(), "period": "2026-B6"})

    assert res.status_code == 422
    assert await _rows(db_session) == []


async def test_a_meeting_cannot_be_logged_before_it_happens(db_session, shema_app) -> None:
    """A log says the meeting took place. Tomorrow in UTC is still today somewhere, so it is
    accepted; the day after is nobody's today and is refused."""
    user, _headers = await _member(db_session, shema_app)
    scope = RegionScope(global_=False, regions=frozenset({"africa"}))
    today = date(2026, 9, 27)

    tomorrow = await log_meeting(
        db_session, scope, _payload(date="2026-09-28"), actor=user, app_key="shema", today=today
    )
    assert tomorrow.entry.period == "2026-B5"
    with pytest.raises(UnprocessableValueError):
        await log_meeting(
            db_session, scope, _payload(date="2026-09-29"), actor=user, app_key="shema", today=today
        )


async def test_a_far_future_day_is_refused_through_the_wire(db_session, client, shema_app) -> None:
    _user, headers = await _member(db_session, shema_app)
    later = (datetime.now(UTC).date() + timedelta(days=5)).isoformat()

    res = await client.post(LOG, headers=headers, json=_body(day=later))

    assert res.status_code == 422
    assert res.json()["code"] == "UNPROCESSABLE_VALUE"
    assert await _rows(db_session) == []


# --- the set: global, in code ------------------------------------------------------------


def test_the_three_meetings_carry_the_cadences_gate_02_gave_them() -> None:
    """Pinned because the console holds the same table in ``RITMO_MEETINGS`` and compares the
    period as text: a cadence changed on one side only would leave a card *pending* forever."""
    assert {key.value: cadence for key, cadence in MEETING_CADENCES.items()} == {
        BIMESTRAL: Cadence.BIMONTHLY,
        TRIMESTRAL: Cadence.QUARTERLY,
        SEMESTRAL: Cadence.SEMIANNUAL,
    }
    assert set(MEETING_CADENCES) == set(ShemaMeetingId)


def test_the_meeting_set_is_global_and_lives_in_code_not_in_a_table() -> None:
    """**The DoD's third line.** One ``shema_meeting*`` table and it is the log; no revision
    creates a definitions table; and the set is keyed by meeting alone, with no region in it."""
    assert sorted(t for t in Base.metadata.tables if t.startswith("shema_meeting")) == [
        "shema_meeting_log"
    ]

    versions = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    created = set()
    for revision in versions.glob("*.py"):
        for node in ast.walk(ast.parse(revision.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "attr", None) == "create_table"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                created.add(node.args[0].value)
    assert {t for t in created if str(t).startswith("shema_meeting")} == {"shema_meeting_log"}

    assert all(isinstance(value, Cadence) for value in MEETING_CADENCES.values())


@pytest.mark.parametrize("meeting_id", ["pulso_mensal", "celebracao_anual", "monthly_prayer"])
async def test_the_pulse_and_the_celebration_are_not_logged_as_meetings(
    db_session, client, shema_app, meeting_id: str
) -> None:
    """The Pulse's record is the submission received (BE-12) and the celebration's is the
    yearly report (FE-50); the prototype's prayer meeting is gone. None of them is a log."""
    _user, headers = await _member(db_session, shema_app)

    res = await client.post(LOG, headers=headers, json=_body(meeting_id=meeting_id))

    assert res.status_code == 422
    assert await _rows(db_session) == []


# --- the artifact --------------------------------------------------------------------------


async def test_the_notes_are_the_meetings_artifact_and_travel_with_the_log(
    db_session, client, shema_app
) -> None:
    """**The DoD's fourth line.** GATE-02's *Registro* column answered what each meeting
    produces: the log. Its notes are written with it, replaced with it and removed with it."""
    _user, headers = await _member(db_session, shema_app)
    notes = "Reviewed both teams' forms; one asked for a follow-up call."

    written = await client.post(LOG, headers=headers, json=_body(notes=notes))
    assert written.json()["notes"] == notes
    assert (await client.get(LOG, headers=headers)).json()[0]["notes"] == notes

    await client.post(LOG, headers=headers, json=_body(notes="Rewritten after the call."))
    assert (await client.get(LOG, headers=headers)).json()[0][
        "notes"
    ] == "Rewritten after the call."

    gone = await client.delete(f"{LOG}/{BIMESTRAL}/africa/2026-B2", headers=headers)
    assert gone.status_code == 204
    assert (await client.get(LOG, headers=headers)).json() == []


async def test_notes_past_the_ceiling_are_refused(db_session, client, shema_app) -> None:
    _user, headers = await _member(db_session, shema_app)

    res = await client.post(LOG, headers=headers, json=_body(notes="x" * 10_001))

    assert res.status_code == 422
    assert await _rows(db_session) == []


# --- scope: the region ---------------------------------------------------------------------


async def test_a_regional_caller_reads_only_its_regions_logs(db_session, client, shema_app) -> None:
    """**The DoD's fifth line, read side.** Asia's entry exists and Africa's coordinator does not
    see it."""
    _user, headers = await _member(db_session, shema_app)
    await _insert(db_session, scope_key="africa", period="2026-B2")
    await _insert(db_session, scope_key="asia", period="2026-B2")

    listed = (await client.get(LOG, headers=headers)).json()

    assert [entry["scopeKey"] for entry in listed] == ["africa"]


async def test_a_regional_caller_cannot_log_or_undo_another_regions_meeting(
    db_session, client, shema_app
) -> None:
    """**The DoD's fifth line, write side.** Refused, and re-read: nothing was written, and the
    other region's entry is still there."""
    _user, headers = await _member(db_session, shema_app)
    await _insert(db_session, scope_key="asia", period="2026-B2")

    logged = await client.post(LOG, headers=headers, json=_body(scope_key="asia", notes="x"))
    undone = await client.delete(f"{LOG}/{BIMESTRAL}/asia/2026-B2", headers=headers)

    assert logged.status_code == 403
    assert undone.status_code == 403
    assert [(r.scope_key, r.notes) for r in await _rows(db_session)] == [("asia", "")]


async def test_out_of_scope_is_refused_before_the_row_is_looked_for(
    db_session, client, shema_app
) -> None:
    """The same 403 whether or not the other region's period was ever logged."""
    _user, headers = await _member(db_session, shema_app)

    res = await client.delete(f"{LOG}/{BIMESTRAL}/asia/2026-B2", headers=headers)

    assert res.status_code == 403


async def test_a_regional_role_with_no_region_reads_and_writes_nothing(
    db_session, client, shema_app
) -> None:
    """``_scope.py``'s fail-closed floor, unrelaxed: a coordinator nobody gave a region reaches
    none, on either side."""
    _user, headers = await _member(db_session, shema_app, regions=())
    await _insert(db_session, scope_key="africa", period="2026-B2")

    assert (await client.get(LOG, headers=headers)).json() == []
    res = await client.post(LOG, headers=headers, json=_body())
    assert res.status_code == 403


async def test_a_coordinator_holding_every_region_reads_and_writes_every_region(
    db_session, client, shema_app
) -> None:
    """The seat the Global Strategist's work falls to since OBT-572: a coordinator granted all
    seven regions."""
    _user, headers = await _member(db_session, shema_app, regions=tuple(ShemaRegionKey))
    await _insert(db_session, scope_key="africa", period="2026-B2")

    written = await client.post(LOG, headers=headers, json=_body(scope_key="oceania"))
    listed = (await client.get(LOG, headers=headers)).json()

    assert written.status_code == 201
    assert sorted(entry["scopeKey"] for entry in listed) == ["africa", "oceania"]


async def test_global_is_not_a_region_a_meeting_is_held_in(db_session, client, shema_app) -> None:
    """Every meeting GATE-02 kept is held per region, so ``global`` is refused as a value with
    the reason - for a coordinator holding every region too, whose scope would otherwise let
    it pass."""
    _user, headers = await _member(db_session, shema_app, regions=tuple(ShemaRegionKey))

    logged = await client.post(LOG, headers=headers, json=_body(scope_key="global"))
    undone = await client.delete(f"{LOG}/{BIMESTRAL}/global/2026-B2", headers=headers)

    assert logged.status_code == 422
    assert "per region" in logged.json()["detail"]
    assert undone.status_code == 422
    assert await _rows(db_session) == []


async def test_a_scope_key_outside_the_vocabulary_is_refused_by_the_type(
    db_session, client, shema_app
) -> None:
    _user, headers = await _member(db_session, shema_app)

    assert (
        await client.post(LOG, headers=headers, json=_body(scope_key="mars"))
    ).status_code == 422
    assert (
        await client.delete(f"{LOG}/{BIMESTRAL}/mars/2026-B2", headers=headers)
    ).status_code == 422
    assert (
        await client.delete(f"{LOG}/pulso_mensal/africa/2026-05", headers=headers)
    ).status_code == 422


async def test_the_read_and_write_spellings_of_the_scope_agree(db_session) -> None:
    """``require_writes_region`` is the write's question and ``logs_within`` the read's: for
    every scope and every key, a row is read exactly when it could have been written - and a
    ``global`` row, which cannot be written, is read only by a global caller."""
    scopes = [
        RegionScope(global_=True, regions=frozenset()),
        RegionScope(global_=False, regions=frozenset()),
        RegionScope(global_=False, regions=frozenset({"africa"})),
        RegionScope(global_=False, regions=frozenset({"africa", "asia"})),
    ]
    keys = [AFRICA, ASIA, ShemaRegionKey.OTHER, "global"]
    for key in keys:
        await _insert(db_session, scope_key=str(key), period="2026-B2")

    for scope in scopes:
        stmt = select(ShemaMeetingLogEntry.scope_key).where(_meeting_log.logs_within(scope))
        read = set((await db_session.execute(stmt)).scalars())
        for key in keys:
            if key == "global":
                with pytest.raises(UnprocessableValueError):
                    _meeting_log.require_writes_region(scope, key)
                assert ("global" in read) is scope.global_
                continue
            writable = reaches(scope, key)
            if not writable:
                with pytest.raises(AuthorizationError):
                    _meeting_log.require_writes_region(scope, key)
            else:
                assert _meeting_log.require_writes_region(scope, key) is key
            assert (key.value in read) is writable, (scope, key)


# --- scope: the audience -------------------------------------------------------------------


async def test_the_obt_lab_logs_its_own_regions_meeting(db_session, client, shema_app) -> None:
    _user, headers = await _member(db_session, shema_app, role="obtLab")

    res = await client.post(LOG, headers=headers, json=_body(meeting_id=SEMESTRAL))

    assert res.status_code == 201
    assert res.json()["period"] == "2026-H1"


async def test_the_resource_circle_is_refused_the_log(db_session, client, shema_app) -> None:
    """The notes are a pastoral reading of a team - the reading BE-07 withholds from the
    Resource Circle - so the log is refused on all three routes, in the circle's own region,
    and nothing is written or removed."""
    _user, headers = await _member(db_session, shema_app, role="resourceCircle")
    await _insert(db_session, scope_key="africa", period="2026-B2")

    read = await client.get(LOG, headers=headers)
    logged = await client.post(LOG, headers=headers, json=_body(day="2026-01-10"))
    undone = await client.delete(f"{LOG}/{BIMESTRAL}/africa/2026-B2", headers=headers)

    assert (read.status_code, logged.status_code, undone.status_code) == (403, 403, 403)
    assert [r.period for r in await _rows(db_session)] == ["2026-B2"]


async def test_an_account_without_a_shema_grant_is_refused(db_session, client, shema_app) -> None:
    """Deny by default: a role in another app reaches nothing of this one."""
    other = await make_app(db_session, app_key="another-app", name="Another")
    role = await make_role(db_session, other.id, role_key="coordinator", label="coordinator")
    user = await make_user(db_session, email="outsider@shema.test", is_platform_admin=False)
    await make_user_app_role(db_session, user.id, other.id, role.id)
    headers = await auth_header(db_session, user)

    assert (await client.get(LOG, headers=headers)).status_code == 403
    assert (await client.post(LOG, headers=headers, json=_body())).status_code == 403
    assert (await db_session.execute(select(func.count(ShemaMeetingLogEntry.id)))).scalar() == 0


# --- undo ----------------------------------------------------------------------------------


async def test_undoing_removes_that_period_only(db_session, client, shema_app) -> None:
    """``undoMeeting`` touches one meeting, one region, one period - the console's own test,
    held on the server."""
    _user, headers = await _member(db_session, shema_app, regions=(AFRICA, ASIA))
    await _insert(db_session, scope_key="africa", period="2026-B1")
    await _insert(db_session, scope_key="africa", period="2026-B2")
    await _insert(db_session, scope_key="asia", period="2026-B2")
    await _insert(db_session, meeting_id=TRIMESTRAL, scope_key="africa", period="2026-B2")

    res = await client.delete(f"{LOG}/{BIMESTRAL}/africa/2026-B2", headers=headers)

    assert res.status_code == 204
    assert res.content == b""
    assert sorted((r.meeting_id, r.scope_key, r.period) for r in await _rows(db_session)) == [
        (BIMESTRAL, "africa", "2026-B1"),
        (BIMESTRAL, "asia", "2026-B2"),
        (TRIMESTRAL, "africa", "2026-B2"),
    ]


async def test_undoing_a_log_that_does_not_exist_is_404(db_session, client, shema_app) -> None:
    _user, headers = await _member(db_session, shema_app)

    res = await client.delete(f"{LOG}/{BIMESTRAL}/africa/2026-B2", headers=headers)

    assert res.status_code == 404
