"""Needs and the money they carry — the DoD's six lines, each where it is either true or not.

* *stored with category, urgency and a lifecycle state, queryable by all three* — the three
  axes, each with its own index, and a query written against each one;
* *open and unacknowledged past a threshold, findable in one query* — the sweep, including the
  need nobody dated, because an undated need going missing is the failure this area is for;
* *urgent needs trigger a notification* — routed by role and then by region, staged inside the
  save's own transaction;
* *every amount carries a currency; no write-time conversion* — refused by the payload with a
  sentence, refused by the database with a constraint, and the number that goes in is the
  number that comes out;
* *financial fields covered by the sensitive-country export tests* — here for the money's own
  sake, and in ``test_privacy.py``'s export parametrisation for the boundary's;
* *scope enforced* — the sweep reaches nothing outside the caller's regions, and a need is
  written through the record's own scoped write or not at all.

Driven over the real router wherever the claim is a property of the wire, and against the
service where it is a property of a query.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.api.shema._deps import APP_KEY
from app.db.models.notification import Notification
from app.db.models.shema_audit import ShemaRecordEdit
from app.db.models.shema_enums import ShemaNeedStatus, ShemaNeedUrgency, ShemaRegionKey
from app.db.models.shema_need import ShemaNeed
from app.models.shema_need import ShemaNeedLine, ShemaNeedWrite
from app.services.notifications.get_shema_app_id import SHEMA_APP_KEY
from app.services.shema import (
    NEEDS_FIELD_KEY,
    UNACKNOWLEDGED_AFTER_DAYS,
    URGENT_NEED_EVENT,
    URGENT_NEED_ROLES,
    RegionScope,
    list_unacknowledged_needs,
)
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user, make_shema_project

PROJECTS = f"{PREFIX}/projects"

#: The record a coordinator files, with the four fields the console requires.
NEW = {
    "id": "guarani-mbya",
    "languageName": "Guarani Mbyá",
    "bridgeLanguage": "Português",
    "team": "YWAM Porto Velho",
    "objective": ["NT"],
    "location": "Brazil",
}

TODAY = date(2026, 9, 11)


def need(**overrides) -> dict:
    """One ``needsItems`` row, in the spelling the console sends."""
    return {"category": "financial", "urgency": "low", "status": "open", **overrides}


@pytest.fixture()
async def coordinator(db_session, shema_app):
    """A regional coordinator scoped to South America — never an admin.

    ``require_role`` returns early on ``is_platform_admin``, so a negative test written per
    role with an admin account passes for the wrong reason.
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
    return await client.post(PROJECTS, json={**NEW, **overrides}, headers=headers)


async def _add_need(db_session, project_id: str, **columns) -> ShemaNeed:
    """A need written straight to the table — for the reads, which have no writer to go through.

    Only the columns a test reads are set, which is the fixture rule ``conftest.py`` states:
    a fixture that fills every field hides a default that is wrong.
    """
    row = ShemaNeed(project_id=project_id, category="financial", urgency=ShemaNeedUrgency.LOW)
    for column, value in columns.items():
        setattr(row, column, value)
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


GLOBAL = RegionScope(global_=True, regions=frozenset())
SOUTH_AMERICA = RegionScope(global_=False, regions=frozenset({"south-america"}))


# --- the three axes -------------------------------------------------------------------


async def test_a_need_is_stored_with_its_category_urgency_and_state(
    client, db_session, shema_app, headers
) -> None:
    """The DoD's first line, over the wire: what goes in comes back on the record."""
    created = await _create(
        client,
        headers,
        needsItems=[need(urgency="high", status="in-progress", description="A motorbike")],
    )
    assert created.status_code == 201

    item = created.json()["needsItems"][0]
    assert (item["category"], item["urgency"], item["status"]) == (
        "financial",
        "high",
        "in-progress",
    )
    assert item["id"], "a need the client cannot address is a need it cannot edit"


def test_each_of_the_three_axes_has_an_index_to_be_queried_by() -> None:
    """*Queryable by all three* is a promise about the plan, not only about the predicate.

    A B-tree serves its leading column, so three questions asked without naming a project need
    three leading columns. ``project_id`` and ``category`` already led one each; BE-08 added
    urgency's, and the sweep's own.
    """
    leading = {
        index.name: [column.name for column in index.columns]
        for index in ShemaNeed.__table__.indexes
    }
    assert leading["ix_shema_needs_category_status"][0] == "category"
    assert leading["ix_shema_needs_urgency_status"][0] == "urgency"
    assert leading["ix_shema_needs_project_status"][0] == "project_id"
    assert leading["ix_shema_needs_unacknowledged"] == [
        "acknowledged_at",
        "status",
        "submitted_at",
    ]


async def test_the_lifecycle_has_four_states_and_dropped_is_not_deleted(
    client, db_session, shema_app, headers
) -> None:
    """``dropped`` leaves the open list without losing the history a region is judged by."""
    created = await _create(client, headers, needsItems=[need()])
    item_id = created.json()["needsItems"][0]["id"]

    dropped = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(id=item_id, status="dropped", droppedDate="2026-09-11")]},
        headers={**headers, "If-Match": created.headers["ETag"]},
    )
    assert dropped.status_code == 200

    items = dropped.json()["needsItems"]
    assert len(items) == 1, "a dropped need is still there — that is the whole point of it"
    assert items[0]["status"] == "dropped"
    assert items[0]["droppedDate"] == "2026-09-11"


async def test_a_need_absent_from_the_batch_is_untouched_and_never_deleted(
    client, db_session, shema_app, headers
) -> None:
    """The batch is an upsert, and *absent means unchanged* holds here as everywhere else.

    Deleting by omission would make one field of the record behave opposite to the other
    seventy-two, and it would undo the reason ``dropped`` exists.
    """
    created = await _create(client, headers, needsItems=[need(), need(category="training")])
    etag = created.headers["ETag"]

    kept = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(category="security")]},
        headers={**headers, "If-Match": etag},
    )
    assert kept.status_code == 200
    assert sorted(item["category"] for item in kept.json()["needsItems"]) == [
        "financial",
        "security",
        "training",
    ]


async def test_an_id_that_is_not_this_projects_is_refused_and_nothing_is_written(
    client, db_session, shema_app, headers
) -> None:
    """Every bad row named at once, and the record does not move — the batch rule, applied here."""
    created = await _create(client, headers, needsItems=[need()])
    etag = created.headers["ETag"]

    refused = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(id="not-a-need-of-this-project"), need(category="training")]},
        headers={**headers, "If-Match": etag},
    )
    assert refused.status_code == 400, "a service ValidationError, not Pydantic's own"
    assert "not-a-need-of-this-project" in refused.text

    after = await client.get(f"{PROJECTS}/guarani-mbya", headers=headers)
    assert len(after.json()["needsItems"]) == 1
    assert after.headers["ETag"] == etag, "a refused batch moved the version"


# --- acknowledgement ------------------------------------------------------------------


async def test_acknowledging_stamps_the_day_and_the_person_and_the_client_states_neither(
    client, db_session, shema_app, headers, coordinator
) -> None:
    """The gesture is the client's; the evidence is the server's (FE-44 §7.2's rule)."""
    created = await _create(client, headers, needsItems=[need()])
    item_id = created.json()["needsItems"][0]["id"]
    assert created.json()["needsItems"][0]["acknowledgedAt"] is None

    seen = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(id=item_id, acknowledged=True)]},
        headers={
            **headers,
            "If-Match": created.headers["ETag"],
            "X-Shema-Local-Date": "2026-09-11",
        },
    )
    assert seen.status_code == 200

    item = seen.json()["needsItems"][0]
    assert item["acknowledgedAt"] == "2026-09-11"
    assert item["acknowledgedBy"] == coordinator.display_name


async def test_acknowledgement_does_not_come_back_off(
    client, db_session, shema_app, headers
) -> None:
    """Somebody did see it. A field whose value can be taken back is not evidence."""
    created = await _create(client, headers, needsItems=[need(acknowledged=True)])
    item_id = created.json()["needsItems"][0]["id"]
    stamped = created.json()["needsItems"][0]["acknowledgedAt"]
    assert stamped is not None

    back = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(id=item_id, acknowledged=False)]},
        headers={**headers, "If-Match": created.headers["ETag"]},
    )
    assert back.json()["needsItems"][0]["acknowledgedAt"] == stamped


def test_moving_a_need_out_of_open_is_seeing_it() -> None:
    """*In progress and nobody has looked* is not a state the product has.

    Asserted on the payload, because that is where the two axes are kept from disagreeing — a
    sweep that had to special-case it would hold a second definition of unacknowledged.
    """
    for status in ("in-progress", "fulfilled", "dropped"):
        assert ShemaNeedWrite(category="financial", status=status).acknowledged is True
    assert ShemaNeedWrite(category="financial", status="open").acknowledged is False


# --- the sweep ------------------------------------------------------------------------


async def test_the_sweep_finds_what_is_open_and_unseen_past_the_threshold(
    db_session, shema_app
) -> None:
    """**The DoD's second line.** One query, and each of the three predicates earns its place."""
    await make_shema_project(
        db_session, project_id="guarani-mbya", region_key=ShemaRegionKey.SOUTH_AMERICA
    )
    old = TODAY - timedelta(days=UNACKNOWLEDGED_AFTER_DAYS + 1)
    recent = TODAY - timedelta(days=1)

    wanted = await _add_need(db_session, "guarani-mbya", submitted_at=old)
    await _add_need(db_session, "guarani-mbya", submitted_at=recent)
    await _add_need(db_session, "guarani-mbya", submitted_at=old, acknowledged_at=old)
    await _add_need(db_session, "guarani-mbya", submitted_at=old, status=ShemaNeedStatus.FULFILLED)
    await _add_need(db_session, "guarani-mbya", submitted_at=old, status=ShemaNeedStatus.DROPPED)

    found = await list_unacknowledged_needs(db_session, GLOBAL, today=TODAY)
    assert [line.id for line in found] == [wanted.id]


async def test_an_in_progress_need_nobody_stamped_is_still_swept(db_session, shema_app) -> None:
    """*Still somebody's problem* is ``open`` **or** ``in-progress``, and the predicate says so.

    A sweep written as ``status == open`` would lose a need that was moved to *being attended*
    by an import or a seed that stamped nothing — which is the row most worth finding, because
    somebody said work had started and nobody is on record as having looked.
    """
    await make_shema_project(
        db_session, project_id="guarani-mbya", region_key=ShemaRegionKey.SOUTH_AMERICA
    )
    old = TODAY - timedelta(days=UNACKNOWLEDGED_AFTER_DAYS + 1)
    row = await _add_need(
        db_session, "guarani-mbya", submitted_at=old, status=ShemaNeedStatus.IN_PROGRESS
    )

    found = await list_unacknowledged_needs(db_session, GLOBAL, today=TODAY)
    assert [line.id for line in found] == [row.id]


async def test_an_undated_need_ages_from_the_day_the_row_arrived(db_session, shema_app) -> None:
    """An undated need must not be invisible — that is the failure, not an edge case.

    BE-12's import and BE-16's seed carry rows this module did not type, and ``submitted_at``
    is nullable for them. The fallback is the row's own arrival, so a need with no date still
    has an age; falling back to *now* would have hidden exactly the rows worth finding.
    """
    await make_shema_project(
        db_session, project_id="guarani-mbya", region_key=ShemaRegionKey.SOUTH_AMERICA
    )
    row = await _add_need(db_session, "guarani-mbya", submitted_at=None)

    #: ``created_at`` is today's, so it is inside the band now and outside it a year on.
    assert await list_unacknowledged_needs(db_session, GLOBAL, today=TODAY, after_days=0) != []
    found = await list_unacknowledged_needs(db_session, GLOBAL, today=TODAY, after_days=0)
    assert [line.id for line in found] == [row.id]


async def test_a_need_raised_a_year_ago_and_never_seen_is_what_the_sweep_is_for(
    db_session, shema_app
) -> None:
    """The sentence the issue opens with, as a test."""
    await make_shema_project(
        db_session, project_id="guarani-mbya", region_key=ShemaRegionKey.SOUTH_AMERICA
    )
    row = await _add_need(db_session, "guarani-mbya", submitted_at=TODAY - timedelta(days=365))

    found = await list_unacknowledged_needs(db_session, GLOBAL, today=TODAY, after_days=365)
    assert [line.id for line in found] == [row.id]


async def test_the_sweep_reaches_nothing_outside_the_callers_regions(db_session, shema_app) -> None:
    """**The DoD's sixth line.** A caller who may not see a region does not learn it has a need.

    For a sensitive project that existence *is* the protected fact, which is why the sweep
    builds on ``visible_projects`` rather than filtering afterwards.
    """
    await make_shema_project(
        db_session, project_id="guarani-mbya", region_key=ShemaRegionKey.SOUTH_AMERICA
    )
    await make_shema_project(db_session, project_id="nuer", region_key=ShemaRegionKey.AFRICA)
    old = TODAY - timedelta(days=90)
    mine = await _add_need(db_session, "guarani-mbya", submitted_at=old)
    await _add_need(db_session, "nuer", submitted_at=old)

    found = await list_unacknowledged_needs(db_session, SOUTH_AMERICA, today=TODAY)
    assert [line.id for line in found] == [mine.id]

    nowhere = RegionScope(global_=False, regions=frozenset())
    assert await list_unacknowledged_needs(db_session, nowhere, today=TODAY) == []


async def test_the_sweep_answers_rows_and_never_a_total(db_session, shema_app) -> None:
    """Categories are not commensurable, and neither are currencies.

    *Seven needs outstanding* is a sentence nobody can act on, and *R$ 7.000 outstanding* over
    three currencies is worse: it is wrong. So the service answers needs, and no function in
    this module adds one to another.
    """
    from app.services.shema import list_unacknowledged_needs as sweep

    assert sweep.__annotations__["return"] == "list[ShemaNeedLine]"


# --- the money ------------------------------------------------------------------------


async def test_every_amount_carries_a_currency_and_the_payload_says_which_is_missing(
    client, db_session, shema_app, headers
) -> None:
    """**The DoD's fourth line**, refused where a sentence can name the field."""
    for row, missing in (
        (need(estimatedAmount="5000.00"), "estimatedCurrency"),
        (need(estimatedCurrency="BRL"), "estimatedAmount"),
    ):
        refused = await _create(client, headers, needsItems=[row])
        assert refused.status_code == 422
        assert missing in refused.text


async def test_the_database_refuses_an_amount_without_a_currency(db_session, shema_app) -> None:
    """The same rule one layer down, which is what makes it an invariant of the data.

    A ``CHECK`` is what holds for a seed, an import and a psql session — none of which passes
    through the payload above.
    """
    from sqlalchemy.exc import IntegrityError

    await make_shema_project(
        db_session, project_id="guarani-mbya", region_key=ShemaRegionKey.SOUTH_AMERICA
    )
    with pytest.raises(IntegrityError):
        await _add_need(db_session, "guarani-mbya", estimated_amount=Decimal("10.00"))
    await db_session.rollback()


async def test_the_database_refuses_a_currency_that_is_not_a_code(db_session, shema_app) -> None:
    """Three letters, upper case — a symbol is not an identity (``$`` least of all)."""
    from sqlalchemy.exc import IntegrityError

    await make_shema_project(
        db_session, project_id="guarani-mbya", region_key=ShemaRegionKey.SOUTH_AMERICA
    )
    with pytest.raises(IntegrityError):
        await _add_need(
            db_session, "guarani-mbya", estimated_amount=Decimal("10.00"), estimated_currency="br"
        )
    await db_session.rollback()


async def test_nothing_converts_on_the_way_in(client, db_session, shema_app, headers) -> None:
    """The number stored is the number typed, in the currency it was typed in.

    There is no base currency in this module and no rate anywhere in it: a rate is a fact about
    a day, and writing one into a need would make the record say something nobody said.
    """
    created = await _create(
        client,
        headers,
        needsItems=[
            need(estimatedAmount="1234.50", estimatedCurrency="IDR", estimatedValue="~1.2k, ish"),
            need(category="equipment", estimatedAmount="99.99", estimatedCurrency="BRL"),
        ],
    )
    assert created.status_code == 201

    rows = {item["category"]: item for item in created.json()["needsItems"]}
    assert rows["financial"]["estimatedAmount"] == "1234.50"
    assert rows["financial"]["estimatedCurrency"] == "IDR"
    assert rows["financial"]["estimatedValue"] == "~1.2k, ish", "the caveat is data too"
    assert rows["equipment"]["estimatedAmount"] == "99.99"
    assert rows["equipment"]["estimatedCurrency"] == "BRL"


def test_a_sub_cent_amount_is_refused_rather_than_rounded() -> None:
    """Silent correction hides client bugs — the sibling's rule (``resource_requests`` §7.2)."""
    with pytest.raises(ValueError, match="two decimals"):
        ShemaNeedWrite(category="financial", estimated_amount="10.005", estimated_currency="BRL")


def test_an_amount_asked_for_is_not_negative_and_is_not_a_nan() -> None:
    """A need is a request for help; a negative one is a typo, and ``NaN`` is not an amount.

    The second half is Pydantic's own refusal and is pinned here anyway, because the trap is
    what a guard written in this module would have looked like: every comparison with a ``NaN``
    is false, so a bound check would have waved it straight through to a column that cannot
    hold it.
    """
    with pytest.raises(ValueError, match="not negative"):
        ShemaNeedWrite(category="financial", estimated_amount="-1", estimated_currency="BRL")
    with pytest.raises(ValueError, match="finite number"):
        ShemaNeedWrite(category="financial", estimated_amount="NaN", estimated_currency="BRL")


def test_the_currency_is_upper_cased_and_a_symbol_is_not_a_currency() -> None:
    written = ShemaNeedWrite(category="financial", estimated_amount="1", estimated_currency="usd")
    assert written.estimated_currency == "USD"
    with pytest.raises(ValueError, match="ISO-4217"):
        ShemaNeedWrite(category="financial", estimated_amount="1", estimated_currency="R$")


# --- the money at the boundary ---------------------------------------------------------


async def test_a_financial_line_of_a_sensitive_project_names_the_money_and_not_the_place(
    db_session, shema_app
) -> None:
    """**The DoD's fifth line.** The combination the rule exists for, in one shape.

    An amount against a named project in a named country is what ends up in a spreadsheet
    somebody forwards, so the row that carries the money is the row the boundary reduces. The
    amount is *not* reduced with it: what a flagged project is protected from is being located,
    not being helped.
    """
    project = await make_shema_project(
        db_session, project_id="sensivel-um", region_key=ShemaRegionKey.AFRICA
    )
    project.sensitive_country = True
    project.location = "Egypt"
    project.team = "YWAM Egypt"
    await db_session.commit()
    row = await _add_need(
        db_session,
        "sensivel-um",
        estimated_amount=Decimal("5000.00"),
        estimated_currency="USD",
    )

    line = ShemaNeedLine.of(row, project)
    body = line.model_dump_json(by_alias=True)

    assert line.location_withheld is True
    assert "Egypt" not in body and "YWAM Egypt" not in body
    assert line.location == "africa"
    assert line.estimated_amount == Decimal("5000.00")
    assert line.estimated_currency == "USD"


async def test_a_cleared_projects_line_still_names_its_place(db_session, shema_app) -> None:
    """The other half, so the shape above cannot pass by withholding everything always."""
    project = await make_shema_project(
        db_session, project_id="guarani-mbya", region_key=ShemaRegionKey.SOUTH_AMERICA
    )
    project.location = "Brazil"
    await db_session.commit()
    row = await _add_need(db_session, "guarani-mbya")

    line = ShemaNeedLine.of(row, project)
    assert line.location_withheld is False
    assert line.location == "Brazil"


async def test_the_sweep_hands_out_lines_the_boundary_has_already_reduced(
    db_session, shema_app
) -> None:
    """A list is an output path, and FE-44 §8.7's rule is that display is never enforcement."""
    project = await make_shema_project(
        db_session, project_id="sensivel-um", region_key=ShemaRegionKey.AFRICA
    )
    project.sensitive_country = True
    project.location = "Egypt"
    await db_session.commit()
    await _add_need(db_session, "sensivel-um", submitted_at=TODAY - timedelta(days=90))

    found = await list_unacknowledged_needs(db_session, GLOBAL, today=TODAY)
    assert [line.location_withheld for line in found] == [True]
    assert "Egypt" not in "".join(line.model_dump_json() for line in found)


# --- the notification ------------------------------------------------------------------


@pytest.fixture()
async def obt_lab(db_session, shema_app):
    return await make_scoped_user(
        db_session,
        shema_app,
        email="lab@shema.test",
        role_key="obtLab",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )


@pytest.fixture()
async def elsewhere(db_session, shema_app):
    """A coordinator of another region — a recipient by role and not by reach."""
    return await make_scoped_user(
        db_session,
        shema_app,
        email="africa@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.AFRICA],
    )


async def _notices(db_session) -> list[Notification]:
    rows = await db_session.execute(
        select(Notification).where(Notification.event_type == URGENT_NEED_EVENT)
    )
    return list(rows.scalars())


async def test_an_urgent_need_reaches_somebody(
    client, db_session, shema_app, headers, obt_lab, elsewhere
) -> None:
    """**The DoD's third line.** Routed by role and *then* by region, before anything is capped.

    ``coordinator`` and ``obtLab`` are FE-44 §5.8's routing for a need; ``resourceCircle`` is
    the prayer wall's alone. A holder of the right role in the wrong region is not a recipient
    rather than a recipient somebody filters out later.
    """
    created = await _create(client, headers, needsItems=[need(urgency="high")])
    assert created.status_code == 201

    notices = await _notices(db_session)
    assert sorted(notice.user_id for notice in notices) == sorted([obt_lab.id])
    assert notices[0].title == "Urgent need: financial"
    assert "Guarani Mbyá" in notices[0].body


async def test_a_notice_carries_the_amount_and_never_the_place(
    client, db_session, shema_app, headers, obt_lab
) -> None:
    """The body is built from a leaving shape, so a flagged project's notice cannot name it.

    The recipients could open the record and read the country there; a notice is the payload
    that travels furthest with the least supervision, and the rule is inherited rather than
    remembered.
    """
    created = await _create(
        client,
        headers,
        id="sensivel-um",
        location="Brazil",
        sensitiveCountry=True,
        needsItems=[need(urgency="high", estimatedAmount="5000.00", estimatedCurrency="BRL")],
    )
    assert created.status_code == 201

    notices = await _notices(db_session)
    assert len(notices) == 1
    assert "5000.00 BRL" in notices[0].body
    assert "Brazil" not in notices[0].body
    assert "YWAM Porto Velho" not in notices[0].body


async def test_a_need_that_was_already_urgent_does_not_send_a_second_notice(
    client, db_session, shema_app, headers, obt_lab
) -> None:
    """A need becomes urgent by **entering** the state, not by being in it.

    Otherwise the tenth save of an afternoon is the tenth copy of one notice in a panel, which
    is how a panel stops being read.
    """
    created = await _create(client, headers, needsItems=[need(urgency="high")])
    item_id = created.json()["needsItems"][0]["id"]

    again = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(id=item_id, urgency="high", description="and a helmet")]},
        headers={**headers, "If-Match": created.headers["ETag"]},
    )
    assert again.status_code == 200
    assert len(await _notices(db_session)) == 1


async def test_raising_a_need_to_urgent_does_send_one(
    client, db_session, shema_app, headers, obt_lab
) -> None:
    created = await _create(client, headers, needsItems=[need(urgency="medium")])
    item_id = created.json()["needsItems"][0]["id"]
    assert await _notices(db_session) == []

    raised = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(id=item_id, urgency="high")]},
        headers={**headers, "If-Match": created.headers["ETag"]},
    )
    assert raised.status_code == 200
    assert len(await _notices(db_session)) == 1


async def test_an_urgent_need_that_is_already_fulfilled_tells_nobody(
    client, db_session, shema_app, headers, obt_lab
) -> None:
    """Urgency is only news while the need is still somebody's problem."""
    created = await _create(client, headers, needsItems=[need(urgency="high", status="fulfilled")])
    assert created.status_code == 201
    assert await _notices(db_session) == []


async def test_a_refused_save_leaves_no_notice_behind(
    client, db_session, shema_app, headers, obt_lab
) -> None:
    """The notice is staged inside the save's own transaction (``commit=False``).

    A need that landed always carries its notice, and one that rolled back leaves none — which
    is the property the flag exists for.
    """
    created = await _create(client, headers, needsItems=[need()])
    refused = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(urgency="high"), need(id="no-such-need")]},
        headers={**headers, "If-Match": created.headers["ETag"]},
    )
    assert refused.status_code == 400
    assert await _notices(db_session) == []


def test_the_notice_reaches_the_two_roles_a_need_belongs_to() -> None:
    """FE-44 §5.8, asserted as the routing rather than inside one delivery test."""
    assert URGENT_NEED_ROLES == ("coordinator", "obtLab")
    assert "resourceCircle" not in URGENT_NEED_ROLES


def test_the_app_key_the_notifier_uses_is_the_module_s_own() -> None:
    """The key is written twice — once inside the module, once in the notifications package.

    ``test_the_app_key_is_named_once_in_the_module`` keeps the first honest; this is what keeps
    the pair from drifting apart in silence, which is the check the sibling already makes for
    ``get_rr_app_id``.
    """
    assert SHEMA_APP_KEY == APP_KEY


# --- the trail ------------------------------------------------------------------------


async def test_a_need_that_moves_is_recorded_in_the_records_own_trail(
    client, db_session, shema_app, headers, coordinator
) -> None:
    """One write path, one version guard, one trail — needs included.

    Without a row here a 409 would answer *it moved and I cannot say how*, which
    ``ChangesSince`` calls a real answer and a worse one.
    """
    created = await _create(client, headers, needsItems=[need()])
    item_id = created.json()["needsItems"][0]["id"]

    await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(id=item_id, status="in-progress")]},
        headers={**headers, "If-Match": created.headers["ETag"]},
    )

    rows = await db_session.execute(
        select(ShemaRecordEdit).where(ShemaRecordEdit.field_key == NEEDS_FIELD_KEY)
    )
    trail = list(rows.scalars())
    assert len(trail) == 2, "the need was filed and then moved"
    assert trail[-1].changed_by_name == coordinator.display_name
    assert '"in-progress"' in (trail[-1].new_value or "")


async def test_the_trail_records_the_lifecycle_and_not_the_free_text(
    client, db_session, shema_app, headers
) -> None:
    """A description is text a team wrote about their own situation and could name a place.

    ``_audit.py``'s rule: a trail is read by more people and kept longer than a response body,
    so what travels is that the need moved, and a reader who is allowed to know the rest goes
    to the record.
    """
    await _create(
        client, headers, needsItems=[need(description="The road past the Siwa Oasis checkpoint")]
    )
    rows = await db_session.execute(
        select(ShemaRecordEdit).where(ShemaRecordEdit.field_key == NEEDS_FIELD_KEY)
    )
    written = "".join((row.new_value or "") + (row.old_value or "") for row in rows.scalars())
    assert "Siwa Oasis" not in written


async def test_a_save_that_moves_only_a_need_still_moves_the_version(
    client, db_session, shema_app, headers
) -> None:
    """Two coordinators editing the needs tab is the case the guard exists for.

    A needs-only save that left the version alone would be last-write-wins for one tab of ten,
    and the ``ETag`` the next reader holds would be a lie.
    """
    created = await _create(client, headers, needsItems=[need()])
    item_id = created.json()["needsItems"][0]["id"]

    moved = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(id=item_id, status="in-progress")]},
        headers={**headers, "If-Match": created.headers["ETag"]},
    )
    assert moved.headers["ETag"] != created.headers["ETag"]

    stale = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(id=item_id, status="fulfilled")]},
        headers={**headers, "If-Match": created.headers["ETag"]},
    )
    assert stale.status_code == 409
    assert NEEDS_FIELD_KEY in stale.json()["changedFields"]


async def test_the_day_a_need_was_raised_is_not_cleared_by_a_payload_that_omits_it(
    client, db_session, shema_app, headers
) -> None:
    """The raise day is the sweep's anchor, and a payload that omits it does not un-raise it.

    The server stamps it when the client sends none, so it is a value the client never had —
    and without this rule the first re-save would read as an edit, bump the version and refuse
    every other coordinator in the meeting over a save that moved nothing.
    """
    created = await _create(client, headers, needsItems=[need()])
    item = created.json()["needsItems"][0]
    assert item["submittedAt"] is not None

    again = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(id=item["id"], status="in-progress")]},
        headers={**headers, "If-Match": created.headers["ETag"]},
    )
    assert again.json()["needsItems"][0]["submittedAt"] == item["submittedAt"]


async def test_a_correction_to_the_raise_day_still_lands(
    client, db_session, shema_app, headers
) -> None:
    """*Never cleared* is not *never changed* — a coordinator fixing a wrong date is ordinary."""
    created = await _create(client, headers, needsItems=[need()])
    item = created.json()["needsItems"][0]

    fixed = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(id=item["id"], submittedAt="2026-03-02")]},
        headers={**headers, "If-Match": created.headers["ETag"]},
    )
    assert fixed.json()["needsItems"][0]["submittedAt"] == "2026-03-02"


async def test_a_batch_that_changes_nothing_moves_nothing(
    client, db_session, shema_app, headers
) -> None:
    """A tab re-sending what it read is not an edit, and must not refuse the other editors."""
    created = await _create(client, headers, needsItems=[need()])
    item = created.json()["needsItems"][0]

    again = await client.patch(
        f"{PROJECTS}/guarani-mbya",
        json={"needsItems": [need(id=item["id"])]},
        headers={**headers, "If-Match": created.headers["ETag"]},
    )
    assert again.status_code == 200
    assert again.headers["ETag"] == created.headers["ETag"]


# --- scope ----------------------------------------------------------------------------


async def test_a_need_cannot_be_written_onto_a_project_outside_the_callers_regions(
    client, db_session, shema_app, headers
) -> None:
    """Writes are scoped by the same value as reads, and there is no needs door beside it."""
    await make_shema_project(db_session, project_id="nuer", region_key=ShemaRegionKey.AFRICA)
    refused = await client.patch(
        f"{PROJECTS}/nuer",
        json={"needsItems": [need()]},
        headers={**headers, "If-Match": '"1"'},
    )
    assert refused.status_code == 404

    rows = await db_session.execute(select(ShemaNeed).where(ShemaNeed.project_id == "nuer"))
    assert list(rows.scalars()) == []


def test_there_is_no_needs_endpoint_in_wave_one() -> None:
    """``docs/shema.md`` §5.4 and FE-44 §9.5: adding one gives ``needsItems`` a second owner.

    Asserted off the built application rather than trusted, because the way this rule breaks is
    somebody adding the obvious route — and the obvious route is a second writer of an
    aggregate whose whole point is that it has one.
    """
    from fastapi.routing import APIRoute

    from app.main import create_app

    paths = {
        route.path
        for route in create_app().routes
        if isinstance(route, APIRoute) and route.path.startswith(PREFIX)
    }
    assert not [path for path in paths if "need" in path.lower()]


def test_the_project_is_the_only_thing_a_need_is_reached_through() -> None:
    """The sweep builds on ``visible_projects`` — the property, read off the statement.

    A predicate applied after the fact is a predicate the next reader writes slightly
    differently; underneath a join it survives a ``LIMIT``, an ``ORDER BY`` and a ``count()``.
    """
    from app.services.shema import unacknowledged_needs

    compiled = str(unacknowledged_needs(SOUTH_AMERICA, before=TODAY))
    assert "shema_projects.region_key IN" in compiled
    assert compiled.index("shema_projects") < compiled.index("shema_needs")


def test_nothing_in_the_module_sums_a_need() -> None:
    """*Do not roll needs up into a single number*, as a property of the package.

    Three prayer needs plus one financial need is not four of anything, and the moment a
    ``sum`` over amounts exists somebody renders it. The check is a grep of the two shema
    packages for an aggregate over the money columns.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    offenders = []
    for package in ("app/services/shema", "app/api/shema"):
        for source in sorted((root / package).glob("*.py")):
            text = source.read_text(encoding="utf-8")
            body = "\n".join(
                line for line in text.splitlines() if not line.lstrip().startswith(("#", '"'))
            )
            if "func.sum" in body or ("sum(" in body and "estimated_amount" in body):
                offenders.append(source.name)
    assert offenders == [], f"a need was summed: {offenders}"
