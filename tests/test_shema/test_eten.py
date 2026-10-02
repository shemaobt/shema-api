"""The ETEN report and its ledger, end to end — ``/api/shema/eten`` and the stamp it reads.

``test_eten_rule.py`` pins the rule case by case with no database. This file pins what the rule
is wrapped in, one DoD line at a time: the report reads only the projects **listed** in ETEN and
**in the caller's scope**; every total names the projects and the entries it came from; every
report answered is **recorded** with the data behind it; a project in a sensitive country leaves as
its region — for **every** reader, in the payload **and** in the recorded report — and still
counts; nothing is marked provisional; and ``save_project`` stamps the completion date the rule
reads.

**Every place, base and contact below is invented**, and they are canaries: most privacy
assertions search the whole body for them, which only works while nothing else in the fixtures
contains them. **No account here is a platform admin**: an admin passes every guard, so a
negative test per role written with one would pass for the wrong reason.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DatabaseError

from app.api.shema._deps import APP_KEY
from app.db.models.shema import ShemaProject
from app.db.models.shema_audit import ShemaRecordEdit
from app.db.models.shema_enums import (
    ShemaEtenCreditSource,
    ShemaProjectStatus,
    ShemaRegionKey,
)
from app.db.models.shema_eten import ShemaEtenCredit, ShemaEtenReport
from app.db.models.shema_progress import ShemaProgressEntry
from app.models.shema import ShemaProjectUpdate
from app.models.shema_eten import EtenYearReport, EtenYearSnapshot
from app.services.shema import eten_report, readership, region_scope, save_project
from app.services.shema._scope import GLOBAL_ROLE
from app.utils.shema_derivations import fiscal_year_of
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user

REPORT = f"{PREFIX}/eten/report"
CREDITS = f"{PREFIX}/eten/credits"
PROJECTS = f"{PREFIX}/projects"

#: The withheld record's place, base and contact — invented, and searched for in whole bodies.
HIDDEN_PLACE = "Terra Oculta, Vale Escondido"
HIDDEN_BASE = "JOCUM Vale Escondido"
HIDDEN_CONTACT = "+00 0000 0001"
#: The open record's, in a different invented country so a body search cannot mix the two.
OPEN_PLACE = "Norlandia, Porto Claro"
OPEN_BASE = "JOCUM Porto Claro"

#: A closed fiscal year and the one before it, relative to the day the suite runs — the route
#: reads the real clock, and a written year would turn into an open one the day it arrived.
YEAR = fiscal_year_of(datetime.now(UTC).date()) - 1
BEFORE = YEAR - 1

#: The keys FE-44 §5.6 froze, and the evidence BE-11 adds beside them — the whole of each shape.
REPORT_KEYS = {
    "year",
    "listedProjects",
    "advancingProjects",
    "totalCredits",
    "hasData",
    "snapshots",
    "periodStart",
    "periodEnd",
    "asOf",
    "reportId",
    "recordedAt",
}
LINE_KEYS = {
    "projectId",
    "languageName",
    "languageNameWithheld",
    "country",
    "scopeUnits",
    "approvedAtStart",
    "approvedAtEnd",
    "advanced",
    "concluded",
    "completedInYear",
    "undatedCompletion",
    "hasData",
    "credits",
    "creditsSource",
    "locationWithheld",
    "startReading",
    "endReading",
    "completedDate",
    "completionSource",
    "approvedUnverified",
    "manualEntry",
}


def cut(year: int) -> date:
    return date(year, 7, 31)


async def listed(
    db_session,
    project_id: str,
    *,
    region: ShemaRegionKey = ShemaRegionKey.SOUTH_AMERICA,
    sensitive: bool = False,
    in_eten: bool = True,
    total: int = 260,
    status: ShemaProjectStatus | None = ShemaProjectStatus.EM_ANDAMENTO,
    partner: str = "",
) -> ShemaProject:
    project = ShemaProject(
        id=project_id,
        language_name=f"Lingua {project_id}",
        location=HIDDEN_PLACE if sensitive else OPEN_PLACE,
        location2="Aldeia Funda" if sensitive else None,
        team=HIDDEN_BASE if sensitive else OPEN_BASE,
        team_contact=HIDDEN_CONTACT if sensitive else "",
        team_leader_contact=HIDDEN_CONTACT if sensitive else None,
        sensitive_country=sensitive,
        region_key=region,
        in_eten=in_eten,
        total_units=total,
        status=status,
        partner_org=partner,
    )
    db_session.add(project)
    await db_session.commit()
    return project


async def entry(
    db_session, project_id: str, day: date, approved: int, *, previous: int | None = None
) -> ShemaProgressEntry:
    row = ShemaProgressEntry(
        project_id=project_id,
        entry_date=day,
        approved_units=approved,
        total_units=260,
        previous_approved=previous,
    )
    db_session.add(row)
    await db_session.commit()
    return row


async def closed_in_year(db_session, project_id: str, **options) -> tuple[str, str]:
    """A project that crosses its 260-chapter scope inside :data:`YEAR`; the two entry ids."""
    await listed(db_session, project_id, **options)
    start = await entry(db_session, project_id, cut(BEFORE), 240)
    end = await entry(db_session, project_id, cut(YEAR) - timedelta(days=30), 260, previous=240)
    return start.id, end.id


@pytest.fixture()
async def strategist(db_session, shema_app):
    return await make_scoped_user(
        db_session, shema_app, email="estrategia@shema.test", role_key="globalStrategist"
    )


@pytest.fixture()
async def strategist_headers(db_session, strategist):
    return await auth_header(db_session, strategist)


async def as_role(db_session, shema_app, role: str, *regions: ShemaRegionKey) -> dict[str, str]:
    user = await make_scoped_user(
        db_session,
        shema_app,
        email=f"{role.lower()}-{'-'.join(r.value for r in regions) or 'global'}@shema.test",
        role_key=role,
        regions=list(regions) if regions else None,
    )
    return await auth_header(db_session, user)


async def report(client, headers, year: int = YEAR) -> dict:
    response = await client.get(REPORT, params={"year": year}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def line_of(body: dict, project_id: str) -> dict:
    return next(line for line in body["snapshots"] if line["projectId"] == project_id)


# --- the rule, through the route ------------------------------------------------------------


async def test_the_report_counts_only_listed_projects_in_the_callers_scope(
    client, db_session, shema_app
) -> None:
    await closed_in_year(db_session, "lista-sul")
    await closed_in_year(db_session, "fora-da-lista", in_eten=False)
    await closed_in_year(db_session, "lista-asia", region=ShemaRegionKey.ASIA)
    headers = await as_role(db_session, shema_app, "coordinator", ShemaRegionKey.SOUTH_AMERICA)

    body = await report(client, headers)

    assert [line["projectId"] for line in body["snapshots"]] == ["lista-sul"]
    assert (body["listedProjects"], body["totalCredits"]) == (1, 1)


async def test_each_partner_receives_the_whole_credit(
    client, db_session, strategist_headers
) -> None:
    """GATE-01 5.2: no split and no agreement field — two partners, one whole credit."""
    await closed_in_year(db_session, "dois-parceiros", partner="Parceiro Um, Parceiro Dois")
    assert line_of(await report(client, strategist_headers), "dois-parceiros")["credits"] == 1


async def test_a_year_with_no_data_is_not_a_year_of_zero_credits(
    client, db_session, strategist_headers
) -> None:
    await listed(db_session, "sem-historico")
    await listed(db_session, "com-historico")
    await entry(db_session, "com-historico", cut(YEAR), 10)

    body = await report(client, strategist_headers)

    silent, measured = line_of(body, "sem-historico"), line_of(body, "com-historico")
    assert (silent["hasData"], silent["credits"]) == (False, None)
    assert (measured["hasData"], measured["credits"]) == (True, 0)


async def test_an_empty_report_is_honest(client, db_session, strategist_headers) -> None:
    """Nothing listed — the 127 migrated records' real state — is an empty report, not seeded."""
    await listed(db_session, "nao-listado", in_eten=False)
    body = await report(client, strategist_headers)

    assert body["snapshots"] == []
    assert (body["listedProjects"], body["totalCredits"], body["hasData"]) == (0, 0, False)
    assert (body["periodStart"], body["periodEnd"]) == (
        f"{YEAR - 1}-08-01",
        f"{YEAR}-07-31",
    )


async def test_a_year_with_only_manual_credits_still_reports_its_total(
    client, db_session, strategist_headers
) -> None:
    """No reading at all and a figure somebody set: the total is stated, not *no data*."""
    await listed(db_session, "so-manual", status=ShemaProjectStatus.CONCLUIDO)
    response = await client.put(
        f"{CREDITS}/so-manual/{YEAR}", json={"credits": 1}, headers=strategist_headers
    )
    assert response.status_code == 200, response.text

    body = await report(client, strategist_headers)
    line = line_of(body, "so-manual")
    assert (line["hasData"], line["credits"], line["creditsSource"]) == (False, 1, "manual")
    assert (body["hasData"], body["totalCredits"]) == (True, 1)


async def test_the_report_needs_a_year(client, strategist_headers) -> None:
    assert (await client.get(REPORT, headers=strategist_headers)).status_code == 422
    too_far = await client.get(REPORT, params={"year": 1999}, headers=strategist_headers)
    assert too_far.status_code == 422


async def test_the_report_does_not_mark_its_figures_provisional(
    client, db_session, strategist_headers
) -> None:
    """GATE-01 closed on 25/sep: the whole shape, key for key, and no provisional flag in it."""
    await closed_in_year(db_session, "chaves")
    body = await report(client, strategist_headers)

    assert set(body) == REPORT_KEYS
    assert set(line_of(body, "chaves")) == LINE_KEYS
    assert "provisional" not in json.dumps(body).lower()


# --- traceability ----------------------------------------------------------------------------


async def test_every_row_names_the_history_entries_it_read(
    client, db_session, strategist_headers
) -> None:
    start_id, end_id = await closed_in_year(db_session, "rastreavel")
    line = line_of(await report(client, strategist_headers), "rastreavel")

    assert line["startReading"] == {
        "source": "history",
        "approvedUnits": 240,
        "totalUnits": 260,
        "entryId": start_id,
        "date": cut(BEFORE).isoformat(),
    }
    assert line["endReading"]["entryId"] == end_id
    assert (line["approvedAtStart"], line["approvedAtEnd"], line["advanced"]) == (240, 260, 20)
    assert line["completionSource"] == "snapshots"


async def test_the_total_is_the_sum_of_the_rows_that_carry_it(
    client, db_session, strategist_headers
) -> None:
    await closed_in_year(db_session, "credita-um")
    await closed_in_year(db_session, "credita-dois")
    await listed(db_session, "parcial")
    await entry(db_session, "parcial", cut(BEFORE), 0)
    await entry(db_session, "parcial", cut(YEAR), 100, previous=0)

    body = await report(client, strategist_headers)

    assert body["totalCredits"] == sum(line["credits"] or 0 for line in body["snapshots"]) == 2
    assert body["advancingProjects"] == 3
    assert [line["projectId"] for line in body["snapshots"]] == [
        "credita-dois",
        "credita-um",
        "parcial",
    ]


async def test_a_manual_credit_names_who_recorded_it_and_when(
    client, db_session, strategist, strategist_headers
) -> None:
    await listed(db_session, "manual", status=ShemaProjectStatus.CONCLUIDO)
    await client.put(f"{CREDITS}/manual/{YEAR}", json={"credits": 1}, headers=strategist_headers)

    manual = line_of(await report(client, strategist_headers), "manual")["manualEntry"]
    assert manual["credits"] == 1
    assert manual["recordedBy"] == (strategist.display_name or strategist.email)
    assert manual["recordedAt"] is not None


async def test_the_completion_is_a_trail_event_with_its_author(
    client, db_session, strategist, strategist_headers
) -> None:
    await listed(db_session, "concluindo")
    etag = (await client.get(f"{PROJECTS}/concluindo", headers=strategist_headers)).headers["ETag"]
    response = await client.patch(
        f"{PROJECTS}/concluindo",
        json={"status": "concluido"},
        headers={**strategist_headers, "If-Match": etag},
    )
    assert response.status_code == 200, response.text

    edits = (
        await db_session.execute(
            select(ShemaRecordEdit).where(
                ShemaRecordEdit.project_id == "concluindo",
                ShemaRecordEdit.field_key == "completedDate",
            )
        )
    ).scalars()
    (edit,) = list(edits)
    assert edit.old_value is None
    assert edit.new_value is not None
    assert edit.changed_by == strategist.id


# --- the stamp -------------------------------------------------------------------------------


async def _patch_status(client, headers, project_id: str, status: str, **extra) -> dict:
    etag = (await client.get(f"{PROJECTS}/{project_id}", headers=headers)).headers["ETag"]
    response = await client.patch(
        f"{PROJECTS}/{project_id}",
        json={"status": status},
        headers={**headers, "If-Match": etag, **extra},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _completed(db_session, project_id: str) -> date | None:
    return (
        await db_session.execute(
            select(ShemaProject.completed_date).where(ShemaProject.id == project_id)
        )
    ).scalar_one()


async def test_moving_status_to_concluido_stamps_the_savers_local_day(
    client, db_session, strategist_headers
) -> None:
    """The actor's day from ``X-Shema-Local-Date``, not the server's — UTC-3 at 22:00 is today."""
    await listed(db_session, "dia-local")
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    await _patch_status(
        client,
        strategist_headers,
        "dia-local",
        "concluido",
        **{"X-Shema-Local-Date": yesterday.isoformat()},
    )

    assert await _completed(db_session, "dia-local") == yesterday


async def test_the_record_serves_the_day_the_save_stamped_and_null_once_it_is_cleared(
    client, db_session, strategist_headers
) -> None:
    """OBT-413: the stamp travels on the record as ``completedDate`` — the answer to the save
    and every read after it — because FE-50's annual report reads it off ``Project``."""
    await listed(db_session, "servido")
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    saved = await _patch_status(
        client,
        strategist_headers,
        "servido",
        "concluido",
        **{"X-Shema-Local-Date": yesterday.isoformat()},
    )
    read = (await client.get(f"{PROJECTS}/servido", headers=strategist_headers)).json()

    assert saved["completedDate"] == read["completedDate"] == yesterday.isoformat()

    reopened = await _patch_status(client, strategist_headers, "servido", "em-andamento")
    assert reopened["completedDate"] is None


async def test_a_tab_saved_after_the_stamp_still_saves_and_keeps_the_day(
    client, db_session, strategist_headers
) -> None:
    """Today's save, against a record that now carries ``completedDate``: the console sends the
    fields a tab owns (``SERVER_WRITABLE``) and never the stamp, so the save goes through and
    the day it read is the day that stays."""
    await listed(db_session, "depois-do-carimbo")
    stamped = (await _patch_status(client, strategist_headers, "depois-do-carimbo", "concluido"))[
        "completedDate"
    ]
    etag = (await client.get(f"{PROJECTS}/depois-do-carimbo", headers=strategist_headers)).headers[
        "ETag"
    ]

    response = await client.patch(
        f"{PROJECTS}/depois-do-carimbo",
        json={"statusComments": "relatório entregue"},
        headers={**strategist_headers, "If-Match": etag},
    )

    assert response.status_code == 200, response.text
    assert stamped is not None
    assert response.json()["completedDate"] == stamped


async def test_a_completion_saved_on_31_july_counts_for_the_year_that_closes(
    db_session, strategist
) -> None:
    """The stamp and the year boundary together, at the service, on the two days that matter."""
    scope = await region_scope(db_session, strategist, APP_KEY)
    for project_id, day in (("em-31-julho", cut(YEAR)), ("em-1-agosto", cut(YEAR) + timedelta(1))):
        await listed(db_session, project_id)
        await save_project(
            db_session,
            scope,
            project_id,
            ShemaProjectUpdate(status=ShemaProjectStatus.CONCLUIDO),
            readership=readership(scope, {GLOBAL_ROLE}, platform_admin=False),
            user=strategist,
            expected_version=1,
            day=day,
        )

    today = cut(YEAR) + timedelta(days=60)
    closing = await eten_report(db_session, scope, YEAR, user=strategist, today=today)
    opening = await eten_report(db_session, scope, YEAR + 1, user=strategist, today=today)
    credit = {line.project_id: line.credits for line in closing.snapshots}
    after = {line.project_id: line.credits for line in opening.snapshots}

    assert credit["em-31-julho"] == 1 and after["em-31-julho"] == 0
    assert after["em-1-agosto"] == 1 and credit["em-1-agosto"] is None


async def test_a_record_already_concluded_is_not_dated_by_a_later_save(
    client, db_session, strategist_headers
) -> None:
    """*Só daqui para frente*: a record that was ``concluido`` before the stamp stays undated."""
    await listed(db_session, "antigo", status=ShemaProjectStatus.CONCLUIDO)
    etag = (await client.get(f"{PROJECTS}/antigo", headers=strategist_headers)).headers["ETag"]
    response = await client.patch(
        f"{PROJECTS}/antigo",
        json={"statusComments": "revisado"},
        headers={**strategist_headers, "If-Match": etag},
    )
    assert response.status_code == 200

    assert await _completed(db_session, "antigo") is None
    line = line_of(await report(client, strategist_headers), "antigo")
    assert (line["undatedCompletion"], line["credits"]) == (True, None)


async def test_leaving_concluido_clears_the_completion_date(
    client, db_session, strategist_headers
) -> None:
    await listed(db_session, "reaberto")
    await _patch_status(client, strategist_headers, "reaberto", "concluido")
    assert await _completed(db_session, "reaberto") is not None

    await _patch_status(client, strategist_headers, "reaberto", "em-andamento")
    assert await _completed(db_session, "reaberto") is None


async def test_a_record_born_concluded_is_not_dated(client, db_session, strategist_headers) -> None:
    """A record filed already finished did not finish today — fail closed on a funder's number."""
    response = await client.post(
        PROJECTS,
        json={
            "id": "794f9ed5-72ad-5655-8d3e-885c71945f8a",
            "languageName": "Lingua nascida",
            "bridgeLanguage": "Portugues",
            "team": OPEN_BASE,
            "objective": ["NT"],
            "status": "concluido",
        },
        headers=strategist_headers,
    )
    assert response.status_code == 201, response.text
    assert await _completed(db_session, "794f9ed5-72ad-5655-8d3e-885c71945f8a") is None


async def test_the_client_cannot_write_the_completion_date(
    client, db_session, strategist_headers
) -> None:
    await listed(db_session, "escrita")
    etag = (await client.get(f"{PROJECTS}/escrita", headers=strategist_headers)).headers["ETag"]
    response = await client.patch(
        f"{PROJECTS}/escrita",
        json={"completedDate": "2020-01-01"},
        headers={**strategist_headers, "If-Match": etag},
    )
    assert response.status_code == 422
    assert await _completed(db_session, "escrita") is None


async def test_a_create_cannot_carry_the_completion_date_either(
    client, db_session, strategist_headers
) -> None:
    """The record serves ``completedDate`` since OBT-413, and the write still has no such field:
    a create that sends it back is refused whole and files nothing."""
    response = await client.post(
        PROJECTS,
        json={
            "id": "12170ce8-031d-5694-970b-d2bd18286761",
            "languageName": "Lingua datada",
            "bridgeLanguage": "Portugues",
            "team": OPEN_BASE,
            "objective": ["NT"],
            "status": "concluido",
            "completedDate": "2020-01-01",
        },
        headers=strategist_headers,
    )

    assert response.status_code == 422
    assert "completedDate" in response.text
    assert await db_session.get(ShemaProject, "12170ce8-031d-5694-970b-d2bd18286761") is None


# --- the recorded report ---------------------------------------------------------------------


async def _recorded(db_session) -> list[ShemaEtenReport]:
    rows = await db_session.execute(
        select(ShemaEtenReport).order_by(ShemaEtenReport.created_at, ShemaEtenReport.id)
    )
    return list(rows.scalars())


async def test_every_report_answered_is_recorded_with_its_payload(
    client, db_session, strategist, strategist_headers
) -> None:
    start_id, end_id = await closed_in_year(db_session, "gravado")
    body = await report(client, strategist_headers)

    (row,) = await _recorded(db_session)
    assert body["reportId"] == row.id
    assert (row.year, row.scope_key, row.computed_by) == (YEAR, "global", strategist.id)
    assert row.content["total_credits"] == body["totalCredits"] == 1
    (line,) = row.content["snapshots"]
    assert (line["credits"], line["region"]) == (1, "south-america")
    readings = (line["start_reading"]["entry_id"], line["end_reading"]["entry_id"])
    assert readings == (start_id, end_id)


async def test_the_recorded_report_keeps_the_data_and_not_the_form(
    client, db_session, strategist_headers
) -> None:
    """ETEN changes its report's format every year, and this year's had not reached the client
    on 28/sep/2026. What is recorded is the data under the fields' own names — none of
    FE-44 §9.8's spelling, no ``country`` display — so a new form leaves the record as it was."""
    await closed_in_year(db_session, "forma")
    body = await report(client, strategist_headers)

    (row,) = await _recorded(db_session)
    assert set(row.content) == set(EtenYearReport.model_fields) - {
        "as_of",
        "report_id",
        "recorded_at",
    }
    data = {name for name, field in EtenYearSnapshot.model_fields.items() if not field.exclude}
    (line,) = row.content["snapshots"]
    assert set(line) == data | {"region"}
    assert "country" in body["snapshots"][0]


async def test_an_unchanged_report_is_recorded_once(client, db_session, strategist_headers) -> None:
    await closed_in_year(db_session, "uma-vez")
    first = await report(client, strategist_headers)
    second = await report(client, strategist_headers)

    assert first["reportId"] == second["reportId"]
    assert len(await _recorded(db_session)) == 1


async def test_a_changed_report_is_recorded_again_and_the_first_still_says_what_it_said(
    client, db_session, strategist_headers
) -> None:
    """March and June: both figures on record, each with the data that produced it."""
    await closed_in_year(db_session, "mudou")
    march = await report(client, strategist_headers)

    await client.put(f"{CREDITS}/mudou/{YEAR}", json={"credits": 0}, headers=strategist_headers)
    june = await report(client, strategist_headers)

    assert march["reportId"] != june["reportId"]
    first, second = await _recorded(db_session)
    assert first.content["total_credits"] == 1
    assert second.content["total_credits"] == 0
    assert second.content["snapshots"][0]["credits_source"] == "manual"


async def test_a_recorded_report_cannot_be_edited_or_deleted(
    client, db_session, strategist_headers
) -> None:
    await closed_in_year(db_session, "imutavel")
    await report(client, strategist_headers)

    with pytest.raises(DatabaseError):
        await db_session.execute(text("UPDATE shema_eten_reports SET year = 1"))
        await db_session.commit()
    await db_session.rollback()
    with pytest.raises(DatabaseError):
        await db_session.execute(text("DELETE FROM shema_eten_reports"))
        await db_session.commit()
    await db_session.rollback()


# --- sensitive countries ---------------------------------------------------------------------


async def test_a_withheld_project_leaves_as_its_region_and_nothing_else(
    client, db_session, strategist_headers
) -> None:
    """The region, no base, no contact — and the ``projectId`` the line is found by, which the
    client allowed to travel on 28/sep/2026 (``docs/shema.md`` §9.4)."""
    await closed_in_year(db_session, "oculto", sensitive=True, region=ShemaRegionKey.AFRICA)
    await closed_in_year(db_session, "aberto")

    response = await client.get(REPORT, params={"year": YEAR}, headers=strategist_headers)
    body = response.json()

    hidden, shown = line_of(body, "oculto"), line_of(body, "aberto")
    assert hidden["country"] == {"withheld": True, "regionLabelKey": "continent_africa"}
    assert hidden["locationWithheld"] is True
    assert shown["country"] == {"withheld": False, "location": "Norlandia"}
    for canary in ("Terra Oculta", "Vale Escondido", "Aldeia Funda", HIDDEN_CONTACT):
        assert canary not in response.text
    assert not {"team", "base", "ywamBase", "location"} & set(hidden)


async def test_a_withheld_project_still_counts_in_the_totals(
    client, db_session, strategist_headers
) -> None:
    """Reduced precision, never omission: a funder total that dropped it would be wrong."""
    await closed_in_year(db_session, "oculto-conta", sensitive=True, region=ShemaRegionKey.AFRICA)
    body = await report(client, strategist_headers)
    assert (body["listedProjects"], body["totalCredits"]) == (1, 1)


@pytest.mark.parametrize(
    ("role", "regions"),
    [
        ("globalStrategist", ()),
        ("coordinator", (ShemaRegionKey.AFRICA,)),
        ("obtLab", (ShemaRegionKey.AFRICA,)),
        ("resourceCircle", (ShemaRegionKey.AFRICA,)),
    ],
)
async def test_the_report_is_withheld_for_every_reader(
    client, db_session, shema_app, role, regions
) -> None:
    """An ETEN report leaves the system: the region's own coordinator reads it withheld too.

    OBT-528 lets the coordination read the truth on the record; this report is an ``outside``
    reader and must not follow it there.
    """
    await closed_in_year(db_session, "oculto-papel", sensitive=True, region=ShemaRegionKey.AFRICA)
    headers = await as_role(db_session, shema_app, role, *regions)

    response = await client.get(REPORT, params={"year": YEAR}, headers=headers)

    assert response.status_code == 200
    assert line_of(response.json(), "oculto-papel")["country"]["withheld"] is True
    assert "Terra Oculta" not in response.text


async def test_the_recorded_report_holds_no_place_name_at_all(
    client, db_session, strategist_headers
) -> None:
    """Not the withheld one, and **not the open one either**: a flag raised tomorrow could not
    reach a country already copied into an append-only table."""
    await closed_in_year(db_session, "oculto-gravado", sensitive=True, region=ShemaRegionKey.AFRICA)
    await closed_in_year(db_session, "aberto-gravado")
    await report(client, strategist_headers)

    (row,) = await _recorded(db_session)
    stored = json.dumps(row.content)
    for canary in ("Terra Oculta", "Vale Escondido", "Norlandia", "Porto Claro", HIDDEN_CONTACT):
        assert canary not in stored
    assert {line["region"] for line in row.content["snapshots"]} == {"africa", "south-america"}


# --- the manual ledger -----------------------------------------------------------------------


async def test_a_regional_coordinator_records_a_manual_credit(
    client, db_session, shema_app
) -> None:
    await listed(db_session, "coordenado")
    headers = await as_role(db_session, shema_app, "coordinator", ShemaRegionKey.SOUTH_AMERICA)

    response = await client.put(
        f"{CREDITS}/coordenado/{YEAR}", json={"credits": 1}, headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["projectId"], body["year"], body["credits"], body["source"]) == (
        "coordenado",
        YEAR,
        1,
        "manual",
    )


@pytest.mark.parametrize("role", ["obtLab", "resourceCircle"])
async def test_obt_lab_and_resource_circle_may_not_record_a_credit(
    client, db_session, shema_app, role
) -> None:
    await listed(db_session, "recusado")
    headers = await as_role(db_session, shema_app, role, ShemaRegionKey.SOUTH_AMERICA)

    response = await client.put(f"{CREDITS}/recusado/{YEAR}", json={"credits": 1}, headers=headers)

    assert response.status_code == 403
    count = await db_session.execute(select(func.count()).select_from(ShemaEtenCredit))
    assert count.scalar_one() == 0


async def test_a_credit_out_of_scope_is_refused_as_not_found(client, db_session, shema_app) -> None:
    """Indistinguishable from a slug that does not exist — the module's one answer."""
    await listed(db_session, "outra-regiao", region=ShemaRegionKey.ASIA)
    headers = await as_role(db_session, shema_app, "coordinator", ShemaRegionKey.SOUTH_AMERICA)

    elsewhere = await client.put(
        f"{CREDITS}/outra-regiao/{YEAR}", json={"credits": 1}, headers=headers
    )
    missing = await client.put(f"{CREDITS}/nao-existe/{YEAR}", json={"credits": 1}, headers=headers)

    assert elsewhere.status_code == missing.status_code == 404
    assert elsewhere.json() == missing.json()


@pytest.mark.parametrize("credits", [-1, 0.5, "1", None])
async def test_a_manual_credit_is_a_whole_number_of_scopes(
    client, db_session, strategist_headers, credits
) -> None:
    await listed(db_session, "inteiro")
    response = await client.put(
        f"{CREDITS}/inteiro/{YEAR}", json={"credits": credits}, headers=strategist_headers
    )
    assert response.status_code == 422


async def test_recording_again_replaces_the_manual_entry(
    client, db_session, strategist_headers
) -> None:
    await listed(db_session, "de-novo")
    for credits in (1, 0):
        response = await client.put(
            f"{CREDITS}/de-novo/{YEAR}", json={"credits": credits}, headers=strategist_headers
        )
        assert response.status_code == 200

    rows = list((await db_session.execute(select(ShemaEtenCredit))).scalars())
    assert [(row.credits, row.source) for row in rows] == [(0, ShemaEtenCreditSource.MANUAL)]


async def test_the_credit_ledger_lists_only_projects_in_scope(
    client, db_session, shema_app, strategist_headers
) -> None:
    await listed(db_session, "livro-sul")
    await listed(db_session, "livro-asia", region=ShemaRegionKey.ASIA)
    for project_id in ("livro-sul", "livro-asia"):
        await client.put(
            f"{CREDITS}/{project_id}/{YEAR}", json={"credits": 1}, headers=strategist_headers
        )
    headers = await as_role(db_session, shema_app, "coordinator", ShemaRegionKey.SOUTH_AMERICA)

    response = await client.get(CREDITS, headers=headers)

    assert response.status_code == 200
    assert [entry["projectId"] for entry in response.json()] == ["livro-sul"]
