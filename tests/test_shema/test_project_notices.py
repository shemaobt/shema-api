"""The project notices in the bell — facts the console words, and no place a reader cannot reach.

OBT-559, and OBT-556's first item with it. The four project writers stage, beside the platform's
row, what happened (``shema_project_notices``); the panel answers those facts with an empty
``title`` and ``body`` for the PME to word in its reader's language, and reads who and where the
project is off the project, when it is read. What is proven here, against the real writers and
the real panel:

* every writer stages its facts, and no stored row — prose or facts — names the place;
* the panel answers the five project kinds as facts and never as prose, stale included;
* an urgent need's place goes only to a reader who reaches the project **now**, and leaves as
  ``outside``: a withheld project reads its region even for the coordination;
* a notice written before this change answers its kind and nothing it said;
* a withheld project's name is not answered, even on a notice written before it was flagged.

The place and the name below are fictional, by the module's rule for test data.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.api.shema._deps import APP_KEY
from app.db.models.notification import Notification
from app.db.models.shema_enums import (
    ShemaNeedStatus,
    ShemaNeedUrgency,
    ShemaPrayerVisibility,
    ShemaRegionKey,
)
from app.db.models.shema_form import ShemaSubmission
from app.db.models.shema_need import ShemaNeed
from app.db.models.shema_notification import ShemaProjectNotice
from app.models.shema_need import ShemaNeedLine
from app.services.notifications import create_notification, get_shema_app_id
from app.services.shema import list_notification_panel, region_scope, set_region_scope
from app.services.shema._health_notice import EVENT_TYPE as HEALTH_EVENT
from app.services.shema._health_notice import notify_critical
from app.services.shema._needs import URGENT_NEED_EVENT, notify_urgent, urgent_needs_facts
from app.services.shema._submission_notices import (
    ARRIVAL_EVENT,
    PRAYER_EVENT,
    notify_shared_request,
    notify_submission,
)
from tests.baker import make_user
from tests.test_shema.conftest import auth_header, make_scoped_user, make_shema_project

AFRICA = ShemaRegionKey.AFRICA
ASIA = ShemaRegionKey.ASIA
PANEL = "/api/shema/notifications"
TODAY = datetime.now(UTC).date()

#: Where the project is, and a name that says it too — neither may reach a reader who may not.
SECRET_PLACE = "Norlandia Confidencial, Vila Sigilosa"
SECRET_NAME = "Língua da Norlandia Confidencial"

PROJECT_KINDS = {"health", "need", "field", "prayer", "stale"}


async def _project(db_session, project_id: str, *, sensitive: bool = False, name: str = "Kuikuro"):
    project = await make_shema_project(
        db_session, project_id=project_id, region_key=AFRICA, language_name=name
    )
    project.location = SECRET_PLACE
    project.sensitive_country = sensitive
    await db_session.commit()
    return project


async def _coordinator(
    db_session, shema_app, email: str = "coord@notices.test", role="coordinator"
):
    return await make_scoped_user(
        db_session, shema_app, email=email, role_key=role, regions=[AFRICA]
    )


async def _panel(db_session, user) -> list[dict]:
    scope = await region_scope(db_session, user, APP_KEY)
    entries = await list_notification_panel(db_session, scope, user, app_key=APP_KEY, today=TODAY)
    return [entry.model_dump(mode="json", by_alias=True) for entry in entries]


async def _urgent(db_session, project, *amounts: tuple[str, str] | None, categories=None) -> None:
    """Raise one urgent need per amount (``None`` for one with no money), in one save."""
    needs = []
    for index, amount in enumerate(amounts):
        need = ShemaNeed(
            project_id=project.id,
            category=(categories or ["financial"] * len(amounts))[index],
            urgency=ShemaNeedUrgency.HIGH,
            status=ShemaNeedStatus.OPEN,
            description="free text a team wrote",
            estimated_amount=None if amount is None else Decimal(amount[0]),
            estimated_currency=None if amount is None else amount[1],
        )
        db_session.add(need)
        needs.append(need)
    await db_session.flush()
    await notify_urgent(db_session, project, needs, actor=None)
    await db_session.commit()


async def _critical(db_session, project, day: date) -> None:
    mentor = await make_user(db_session, email="mentor@notices.test")
    await notify_critical(
        db_session,
        app_key=APP_KEY,
        project_id=project.id,
        language_name=project.language_name,
        region=project.region_key,
        day=day,
        actor=mentor,
    )
    await db_session.commit()


async def _pulse(db_session, project, *, prayer: bool) -> None:
    submission = ShemaSubmission(language_name=project.language_name, submitted_by="Kuaray")
    await notify_submission(db_session, project, submission, app_key=APP_KEY)
    if prayer:
        # Applied, the Pulse put its request on the wall (OBT-566).
        await notify_shared_request(db_session, project, app_key=APP_KEY)
    await db_session.commit()


async def _details(db_session) -> dict[str, ShemaProjectNotice]:
    rows = await db_session.execute(select(ShemaProjectNotice))
    return {detail.notification_id: detail for detail in rows.scalars()}


async def _rows(db_session, event_type: str) -> list[Notification]:
    rows = await db_session.execute(
        select(Notification).where(Notification.event_type == event_type)
    )
    return list(rows.scalars())


def _by_kind(panel: list[dict]) -> dict[str, dict]:
    return {entry["kind"]: entry for entry in panel}


# --- what is stored ----------------------------------------------------------------------------


def test_a_project_notice_has_no_column_a_place_could_arrive_through() -> None:
    """What happened, never who or where: the name, the region and the place are the project's,
    read when the panel is read, so no column here can keep one past the rule that withholds it."""
    assert set(ShemaProjectNotice.__table__.columns.keys()) == {
        "notification_id",
        "project_id",
        "assessed_on",
        "need_count",
        "need_categories",
        "need_totals",
        "submitted_by",
    }


async def test_each_writer_stages_what_happened_beside_its_row(db_session, shema_app) -> None:
    project = await _project(db_session, "a1b2c3d4-0000-4000-8000-000000000001")
    project.prayer_visibility = ShemaPrayerVisibility.REDE
    await db_session.commit()
    await _coordinator(db_session, shema_app)
    await make_scoped_user(
        db_session,
        shema_app,
        email="circle@notices.test",
        role_key="resourceCircle",
        regions=[AFRICA],
    )

    await _critical(db_session, project, date(2026, 9, 11))
    await _urgent(
        db_session,
        project,
        ("5000.00", "BRL"),
        ("250.50", "BRL"),
        ("40.00", "USD"),
        categories=["medical", "financial", "medical"],
    )
    await _pulse(db_session, project, prayer=True)

    details = await _details(db_session)
    [health] = await _rows(db_session, HEALTH_EVENT)
    [need] = await _rows(db_session, URGENT_NEED_EVENT)
    [arrival] = await _rows(db_session, ARRIVAL_EVENT)
    [prayer] = await _rows(db_session, PRAYER_EVENT)

    assert {row.id for row in (health, need, arrival, prayer)} == set(details)
    assert all(detail.project_id == project.id for detail in details.values())
    assert details[health.id].assessed_on == date(2026, 9, 11)
    assert details[need.id].need_count == 3
    assert details[need.id].need_categories == ["financial", "medical"]
    assert details[need.id].need_totals == [
        {"amount": "5250.50", "currency": "BRL"},
        {"amount": "40.00", "currency": "USD"},
    ]
    assert details[arrival.id].submitted_by == "Kuaray"
    prayer_detail = details[prayer.id]
    assert (prayer_detail.assessed_on, prayer_detail.need_count, prayer_detail.submitted_by) == (
        None,
        None,
        None,
    )


async def test_no_stored_notice_names_the_place(db_session, shema_app) -> None:
    """**OBT-556, item 1, at the source.** A cleared project's place is the truth for every reader
    of the record — and was written, as such, into every urgent notice's body, to be read later by
    whoever then held the row. Neither the prose nor the facts carry it now, one need or many."""
    project = await _project(db_session, "a1b2c3d4-0000-4000-8000-000000000002")
    await _coordinator(db_session, shema_app)

    await _urgent(db_session, project, ("100.00", "BRL"))
    await _urgent(db_session, project, None, None, categories=["security", "transport"])

    rows = await _rows(db_session, URGENT_NEED_EVENT)
    assert len(rows) == 2
    stored = [row.title + row.body for row in rows] + [
        json.dumps([detail.need_categories, detail.need_totals, detail.submitted_by])
        for detail in (await _details(db_session)).values()
    ]
    for text in stored:
        assert "Norlandia" not in text
        assert "Sigilosa" not in text
    assert any("Kuikuro raised an urgent financial need" in row.body for row in rows)


# --- what the panel answers --------------------------------------------------------------------


async def test_every_project_kind_answers_its_facts_and_no_prose(db_session, shema_app) -> None:
    """**The DoD's second line, on the server.** The five project kinds answer facts and an empty
    ``title`` and ``body`` — the console words them in its reader's language — stale included."""
    project = await _project(db_session, "a1b2c3d4-0000-4000-8000-000000000003")
    project.prayer_visibility = ShemaPrayerVisibility.REDE
    await db_session.commit()
    coordinator = await _coordinator(db_session, shema_app)
    circle = await make_scoped_user(
        db_session,
        shema_app,
        email="circle@notices.test",
        role_key="resourceCircle",
        regions=[AFRICA],
    )

    await _critical(db_session, project, date(2026, 9, 11))
    await _urgent(
        db_session,
        project,
        ("5000.00", "BRL"),
        ("40.00", "USD"),
        categories=["medical", "financial"],
    )
    await _pulse(db_session, project, prayer=True)

    panel = _by_kind(await _panel(db_session, coordinator))
    assert set(panel) == {"health", "need", "field"}
    [panel["prayer"]] = await _panel(db_session, circle)

    # The project then goes quiet, and the stale reading is read by a coordinator who arrived after
    # the three were told: SQLite hands ``notifications.created_at`` back without its zone, so a
    # panel holding both halves cannot be sorted here — the shared table's type is not this
    # issue's to change, and Postgres answers it with one.
    project.start_date = TODAY - timedelta(days=400)
    project.status = None
    await db_session.commit()
    quiet_reader = await _coordinator(db_session, shema_app, email="arrived@notices.test")
    [panel["stale"]] = await _panel(db_session, quiet_reader)

    for kind, entry in panel.items():
        assert (entry["title"], entry["body"]) == ("", ""), kind
        assert entry["projectId"] == project.id, kind
        assert entry["region"] == "africa", kind
        assert entry["facts"]["languageName"] == "Kuikuro", kind

    assert panel["health"]["facts"]["assessedOn"] == "2026-09-11"
    assert panel["need"]["facts"]["needCount"] == 2
    assert panel["need"]["facts"]["needCategories"] == ["financial", "medical"]
    assert panel["need"]["facts"]["needTotals"] == [
        {"amount": "5000.00", "currency": "BRL"},
        {"amount": "40.00", "currency": "USD"},
    ]
    assert panel["field"]["facts"]["submittedBy"] == "Kuaray"
    assert panel["stale"]["facts"]["daysSinceUpdate"] is not None
    assert panel["stale"]["facts"]["daysSinceUpdate"] >= 365
    assert all(panel[kind]["facts"]["place"] is None for kind in PROJECT_KINDS - {"need"})


def test_need_totals_stay_per_currency() -> None:
    """A number never travels without its currency, and two currencies are never one number."""
    lines = [
        ShemaNeedLine(
            id="1",
            project_id="p",
            category="medical",
            estimated_amount=Decimal("100.00"),
            estimated_currency="BRL",
        ),
        ShemaNeedLine(
            id="2",
            project_id="p",
            category="medical",
            estimated_amount=Decimal("50.50"),
            estimated_currency="BRL",
        ),
        ShemaNeedLine(
            id="3",
            project_id="p",
            category="transport",
            estimated_amount=Decimal("10.00"),
            estimated_currency="USD",
        ),
        ShemaNeedLine(id="4", project_id="p", category="food"),
    ]

    urgent = urgent_needs_facts(lines)

    assert urgent.raised == 4
    assert urgent.categories == ("food", "medical", "transport")
    assert urgent.totals == {"BRL": Decimal("150.50"), "USD": Decimal("10.00")}


async def test_the_place_goes_only_to_a_reader_who_reaches_the_project(
    db_session, shema_app
) -> None:
    """**OBT-556, item 1, at the reader.** Both were told while they reached the region; one has
    since been moved to Asia. The one who still reaches the project reads where it is; the one who
    does not reads the region, and nothing that would open or locate the record."""
    project = await _project(db_session, "a1b2c3d4-0000-4000-8000-000000000004")
    moved = await _coordinator(db_session, shema_app, email="moved@notices.test")
    lab = await _coordinator(db_session, shema_app, email="lab@notices.test", role="obtLab")
    await _urgent(db_session, project, ("100.00", "BRL"))

    await set_region_scope(db_session, moved.id, [ASIA])

    [still] = await _panel(db_session, lab)
    assert still["projectId"] == project.id
    # ``languageNameWithheld`` rides on every leaving shape since OBT-560; a place has no name.
    assert still["facts"]["place"] == {
        "location": SECRET_PLACE,
        "locationWithheld": False,
        "languageNameWithheld": False,
    }

    [gone] = await _panel(db_session, moved)
    assert gone["kind"] == "need"
    assert gone["projectId"] is None
    assert gone["facts"]["place"] is None
    assert gone["region"] == "africa"
    assert "Norlandia" not in json.dumps(gone)


async def test_a_sensitive_project_s_notice_reads_the_region_even_for_coordination(
    db_session, client, shema_app
) -> None:
    """A notice is an output path (``docs/shema.md`` §6.4): it is built for ``outside`` whoever
    reads it, so the coordinator in scope — who reads the truth on the record — reads the region
    here. Through the route, because the response model validates the place a second time."""
    project = await _project(db_session, "a1b2c3d4-0000-4000-8000-000000000005", sensitive=True)
    coordinator = await _coordinator(db_session, shema_app)
    await _urgent(db_session, project, ("100.00", "BRL"))

    res = await client.get(PANEL, headers=await auth_header(db_session, coordinator))
    assert res.status_code == 200, res.text
    [entry] = res.json()

    assert entry["projectId"] == project.id
    assert entry["facts"]["place"] == {
        "location": "africa",
        "locationWithheld": True,
        "languageNameWithheld": False,
    }
    assert "Norlandia" not in res.text and "Sigilosa" not in res.text


async def test_a_sensitive_project_s_notice_never_names_its_language(db_session, shema_app) -> None:
    """A withheld project's name can name the place (OBT-560), so a notice does not answer it —
    and a notice written before the project was flagged reads the way the project reads now."""
    project = await _project(db_session, "a1b2c3d4-0000-4000-8000-000000000006", name=SECRET_NAME)
    coordinator = await _coordinator(db_session, shema_app)
    await _critical(db_session, project, date(2026, 9, 11))
    [before] = await _panel(db_session, coordinator)
    assert before["facts"]["languageName"] == SECRET_NAME

    project.sensitive_country = True
    await db_session.commit()

    [after] = await _panel(db_session, coordinator)
    assert after["facts"]["languageName"] == ""
    assert "Norlandia" not in json.dumps(after)


async def test_a_quiet_sensitive_project_is_not_named_either(db_session, shema_app) -> None:
    """The stale reading has no row: its name comes off the card ``browse_projects`` built for a
    reader outside coordination, and a withheld project's is not answered there either."""
    project = await _project(
        db_session, "a1b2c3d4-0000-4000-8000-000000000007", sensitive=True, name=SECRET_NAME
    )
    project.start_date = TODAY - timedelta(days=400)
    project.status = None
    await db_session.commit()
    coordinator = await _coordinator(db_session, shema_app)

    [stale] = await _panel(db_session, coordinator)

    assert stale["kind"] == "stale"
    assert stale["facts"]["languageName"] == ""
    assert stale["facts"]["daysSinceUpdate"] >= 365
    assert "Norlandia" not in json.dumps(stale)


async def test_an_old_notice_answers_its_kind_and_none_of_its_prose(db_session, shema_app) -> None:
    """**OBT-556, item 1, for what is already stored.** Rows written before OBT-559 carry their
    sentence and no facts — the urgent one with the place in it. The panel answers each one's kind
    and nothing it said: no prose, no project, no region."""
    coordinator = await _coordinator(db_session, shema_app)
    app_id = await get_shema_app_id(db_session)
    for event_type, body in (
        (HEALTH_EVENT, "Kuikuro was assessed as critical on 2026-09-11."),
        (URGENT_NEED_EVENT, f"Kuikuro ({SECRET_PLACE}) raised an urgent medical need."),
        (ARRIVAL_EVENT, "Kuaray submitted the monthly Pulse for Kuikuro."),
        (PRAYER_EVENT, "The Pulse received for Kuikuro carries a prayer request."),
    ):
        await create_notification(
            db_session,
            user_id=coordinator.id,
            app_id=app_id,
            event_type=event_type,
            title=f"Old notice — {SECRET_PLACE}",
            body=body,
        )

    panel = await _panel(db_session, coordinator)

    assert sorted(entry["kind"] for entry in panel) == ["field", "health", "need", "prayer"]
    for entry in panel:
        assert (entry["title"], entry["body"]) == ("", "")
        assert (entry["projectId"], entry["region"], entry["facts"]) == (None, None, None)
    assert "Norlandia" not in json.dumps(panel)
    assert "Kuikuro" not in json.dumps(panel)
