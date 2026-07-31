from sqlalchemy import select

from app.db.models.phase import Phase
from tests.baker import make_journey, make_phase, make_phase_category, make_user
from tests.test_journeys.conftest import auth_header


async def test_list_categories_with_counts(client, db_session):
    user = await make_user(db_session, email="viewer@example.com")
    category = await make_phase_category(db_session, name="Discovery", icon="compass")
    other = await make_phase_category(db_session, name="Design", icon="pen")
    journey = await make_journey(db_session)
    await make_phase(db_session, name="P1", journey_id=journey.id, category_id=category.id)
    headers = await auth_header(db_session, user)
    resp = await client.get("/api/phase-categories", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    by_id = {c["id"]: c for c in body}
    assert by_id[category.id]["phase_count"] == 1
    assert by_id[other.id]["phase_count"] == 0


async def test_create_category_as_admin(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)
    resp = await client.post(
        "/api/phase-categories",
        json={"name": "Research", "color": "#6F5691", "icon": "search"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Research"
    assert body["color"] == "#6F5691"
    assert body["icon"] == "search"
    assert body["phase_count"] == 0


async def test_create_category_as_non_admin_forbidden(client, db_session):
    user = await make_user(db_session, email="user@example.com")
    headers = await auth_header(db_session, user)
    resp = await client.post(
        "/api/phase-categories",
        json={"name": "Nope", "color": "#000000", "icon": "compass"},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_create_category_invalid_color(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)
    resp = await client.post(
        "/api/phase-categories",
        json={"name": "Bad", "color": "red", "icon": "compass"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_category_invalid_icon(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)
    resp = await client.post(
        "/api/phase-categories",
        json={"name": "Bad", "color": "#123456", "icon": "not-an-icon"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_update_category(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    category = await make_phase_category(db_session, name="Old", color="#111111", icon="compass")
    headers = await auth_header(db_session, admin)
    resp = await client.patch(
        f"/api/phase-categories/{category.id}",
        json={"name": "New", "color": "#A87B12", "icon": "rocket"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New"
    assert body["color"] == "#A87B12"
    assert body["icon"] == "rocket"


async def test_delete_last_category_conflict(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    category = await make_phase_category(db_session, name="Only one")
    headers = await auth_header(db_session, admin)
    resp = await client.delete(f"/api/phase-categories/{category.id}", headers=headers)
    assert resp.status_code == 409


async def test_delete_category_reassigns_phases_to_oldest(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    oldest = await make_phase_category(db_session, name="Oldest")
    doomed = await make_phase_category(db_session, name="Doomed")
    journey = await make_journey(db_session)
    phase = await make_phase(db_session, name="P1", journey_id=journey.id, category_id=doomed.id)
    headers = await auth_header(db_session, admin)
    resp = await client.delete(f"/api/phase-categories/{doomed.id}", headers=headers)
    assert resp.status_code == 204
    fresh = (await db_session.execute(select(Phase).where(Phase.id == phase.id))).scalars().one()
    await db_session.refresh(fresh)
    assert fresh.category_id == oldest.id


async def test_delete_category_as_non_admin_forbidden(client, db_session):
    user = await make_user(db_session, email="user@example.com")
    category = await make_phase_category(db_session)
    await make_phase_category(db_session, name="Other")
    headers = await auth_header(db_session, user)
    resp = await client.delete(f"/api/phase-categories/{category.id}", headers=headers)
    assert resp.status_code == 403
