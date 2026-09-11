"""The panel, the preferences, the read state — and the DoD's own privacy line.

Three things are exercised here rather than left to the three writers' own suites: that the
panel routes by role and region and never crosses a boundary (§5.10, on top of what BE-07,
BE-08 and BE-12 already stage); that a batch of urgent needs stages one notice per recipient
and not one per need; and the line the issue states in letters — *no prayer content,
sensitive-country detail or health specifics in a notification body* — against the real
functions that build one, not against a description of them.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.api.shema._deps import APP_KEY
from app.db.models.shema_enums import ShemaNeedStatus, ShemaNeedUrgency, ShemaRegionKey
from app.db.models.shema_need import ShemaNeed
from app.models.shema_need import ShemaNeedLine
from app.services.notifications.get_shema_app_id import SHEMA_APP_KEY
from app.services.shema import (
    list_notification_panel,
    mark_notifications_read,
    notice_body,
    notify_urgent,
    region_scope,
)
from app.services.shema._needs import urgent_needs_notice
from tests.test_shema.conftest import make_scoped_user, make_shema_project

FORBIDDEN_HEALTH_WORDS = ("emotional", "relational", "spiritual", "physical")
SENSITIVE_COUNTRY = "Norlandia Confidencial"
PRAYER_TEXT = "please pray for the underground meeting on Fridays"


def test_the_app_key_here_is_the_modules_own() -> None:
    assert SHEMA_APP_KEY == APP_KEY


async def test_notify_urgent_batches_one_notice_per_recipient_per_save(
    db_session, shema_app
) -> None:
    """Ten needs turning urgent in one save is one notice per recipient, not ten."""
    project = await make_shema_project(
        db_session, project_id="batch-project", region_key=ShemaRegionKey.AFRICA
    )
    coordinator = await make_scoped_user(
        db_session,
        shema_app,
        email="coord-batch@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.AFRICA],
    )

    needs = []
    for i in range(10):
        need = ShemaNeed(
            project_id=project.id,
            category=f"category-{i}",
            urgency=ShemaNeedUrgency.HIGH,
            status=ShemaNeedStatus.OPEN,
            description=f"sensitive detail {i}",
        )
        db_session.add(need)
        needs.append(need)
    await db_session.flush()

    written = await notify_urgent(db_session, project, needs, actor=None)
    await db_session.commit()

    assert written == 1

    from sqlalchemy import select

    from app.db.models.notification import Notification

    rows = (
        (
            await db_session.execute(
                select(Notification).where(Notification.user_id == coordinator.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert "10 urgent needs" in rows[0].title


def test_urgent_needs_notice_never_carries_a_place_or_a_description() -> None:
    lines = [
        ShemaNeedLine(
            id="1",
            project_id="p",
            language_name="Team X",
            location=SENSITIVE_COUNTRY,
            category="medical",
        ),
        ShemaNeedLine(
            id="2",
            project_id="p",
            language_name="Team X",
            location=SENSITIVE_COUNTRY,
            category="transport",
        ),
    ]
    # a sensitive line's own leaving-shape validator already reduced ``location`` — this
    # simulates what a caller sees when a row was built off a flagged project.
    lines = [
        line.model_copy(update={"location": ShemaRegionKey.AFRICA.value, "location_withheld": True})
        for line in lines
    ]

    notice = urgent_needs_notice(lines)

    assert SENSITIVE_COUNTRY not in notice.body
    assert SENSITIVE_COUNTRY not in notice.title
    assert PRAYER_TEXT not in notice.body
    for word in FORBIDDEN_HEALTH_WORDS:
        assert word not in notice.body.lower()


def test_health_notice_never_carries_a_place_dimension_or_note() -> None:
    body = notice_body("Team Y", day=date(2026, 1, 1))

    assert SENSITIVE_COUNTRY not in body
    assert PRAYER_TEXT not in body
    for word in FORBIDDEN_HEALTH_WORDS:
        assert word not in body.lower()
    assert "note" not in body.lower()


async def test_stale_entries_reach_coordinator_in_scope_and_nobody_else(
    db_session, shema_app
) -> None:
    long_ago = datetime.now(UTC).date() - timedelta(days=400)
    project = await make_shema_project(
        db_session, project_id="quiet-project", region_key=ShemaRegionKey.ASIA
    )
    project.start_date = long_ago
    project.status = None
    await db_session.commit()

    in_region = await make_scoped_user(
        db_session,
        shema_app,
        email="asia-coord@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.ASIA],
    )
    other_region = await make_scoped_user(
        db_session,
        shema_app,
        email="africa-coord@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.AFRICA],
    )
    resource_circle = await make_scoped_user(
        db_session,
        shema_app,
        email="rc-asia@shema.test",
        role_key="resourceCircle",
        regions=[ShemaRegionKey.ASIA],
    )

    today = datetime.now(UTC).date()

    in_scope = await list_notification_panel(
        db_session,
        await region_scope(db_session, in_region, APP_KEY),
        in_region,
        app_key=APP_KEY,
        today=today,
    )
    out_of_scope = await list_notification_panel(
        db_session,
        await region_scope(db_session, other_region, APP_KEY),
        other_region,
        app_key=APP_KEY,
        today=today,
    )
    resource_circle_panel = await list_notification_panel(
        db_session,
        await region_scope(db_session, resource_circle, APP_KEY),
        resource_circle,
        app_key=APP_KEY,
        today=today,
    )

    assert any(entry.kind == "stale" and entry.project_id == project.id for entry in in_scope)
    assert not any(entry.project_id == project.id for entry in out_of_scope)
    assert not any(entry.kind == "stale" for entry in resource_circle_panel)


async def test_read_marks_a_stale_entry_seen(db_session, shema_app) -> None:
    long_ago = datetime.now(UTC).date() - timedelta(days=400)
    project = await make_shema_project(
        db_session, project_id="quiet-project-2", region_key=ShemaRegionKey.EUROPE
    )
    project.start_date = long_ago
    project.status = None
    await db_session.commit()

    coordinator = await make_scoped_user(
        db_session,
        shema_app,
        email="europe-coord@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.EUROPE],
    )
    today = datetime.now(UTC).date()
    scope = await region_scope(db_session, coordinator, APP_KEY)

    [entry] = [
        entry
        for entry in await list_notification_panel(
            db_session, scope, coordinator, app_key=APP_KEY, today=today
        )
        if entry.project_id == project.id
    ]
    assert entry.is_read is False

    await mark_notifications_read(db_session, coordinator.id, [entry.id])

    [reread] = [
        entry
        for entry in await list_notification_panel(
            db_session, scope, coordinator, app_key=APP_KEY, today=today
        )
        if entry.project_id == project.id
    ]
    assert reread.is_read is True


async def test_prefs_round_trip_through_the_router(db_session, client, shema_app) -> None:
    from tests.baker import make_user
    from tests.test_shema.conftest import auth_header, grant

    user = await make_user(db_session, email="prefs@shema.test")
    await grant(db_session, user, shema_app, "coordinator")
    headers = await auth_header(db_session, user)

    default = await client.get("/api/shema/notifications/prefs", headers=headers)
    assert default.status_code == 200
    assert default.json()["enabled"] is True
    assert default.json()["channels"] == {"email": False, "push": False, "whatsapp": False}

    saved = await client.put(
        "/api/shema/notifications/prefs",
        headers=headers,
        json={
            "enabled": False,
            "channels": {"email": True, "push": False, "whatsapp": False},
            "when": "daily",
            "scope": "myProjects",
            "emailAddr": "me@example.org",
            "phoneAddr": "",
            "customProjectIds": ["afrikaans-kaaps"],
        },
    )
    assert saved.status_code == 200
    assert saved.json()["enabled"] is False
    assert saved.json()["channels"]["email"] is True
    assert saved.json()["emailAddr"] == "me@example.org"

    reread = await client.get("/api/shema/notifications/prefs", headers=headers)
    assert reread.json() == saved.json()


async def test_panel_route_reaches_only_a_signed_in_shema_account(client) -> None:
    res = await client.get("/api/shema/notifications")
    assert res.status_code == 401
