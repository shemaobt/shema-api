from tests.baker import (
    make_journey,
    make_phase,
    make_phase_category,
    make_phase_dependency,
    make_user,
)
from tests.test_journeys.conftest import auth_header


async def test_create_phase_requires_journey_field(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)
    resp = await client.post("/api/phases", json={"name": "No journey"}, headers=headers)
    assert resp.status_code == 422


async def test_create_phase_unknown_journey(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)
    resp = await client.post(
        "/api/phases",
        json={"name": "Ghost", "journey_id": "missing-journey"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_phase_assigns_incremental_sort_order(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session)
    category = await make_phase_category(db_session)
    headers = await auth_header(db_session, admin)
    first = await client.post(
        "/api/phases",
        json={"name": "First", "journey_id": journey.id, "category_id": category.id},
        headers=headers,
    )
    second = await client.post(
        "/api/phases",
        json={"name": "Second", "journey_id": journey.id},
        headers=headers,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["sort_order"] == 0
    assert second.json()["sort_order"] == 1
    assert first.json()["journey_id"] == journey.id
    assert first.json()["category_id"] == category.id


async def test_create_phase_as_non_admin_forbidden(client, db_session):
    user = await make_user(db_session, email="user@example.com")
    journey = await make_journey(db_session)
    headers = await auth_header(db_session, user)
    resp = await client.post(
        "/api/phases",
        json={"name": "Nope", "journey_id": journey.id},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_list_phases_filtered_by_journey_ordered(client, db_session):
    user = await make_user(db_session, email="viewer@example.com")
    journey = await make_journey(db_session)
    other = await make_journey(db_session, name="Other")
    p2 = await make_phase(db_session, name="Second", journey_id=journey.id, sort_order=1)
    p1 = await make_phase(db_session, name="First", journey_id=journey.id, sort_order=0)
    await make_phase(db_session, name="Elsewhere", journey_id=other.id)
    headers = await auth_header(db_session, user)
    resp = await client.get(f"/api/phases?journey_id={journey.id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert [p["id"] for p in body] == [p1.id, p2.id]


async def test_update_phase_category_and_icon_url(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session)
    category = await make_phase_category(db_session)
    phase = await make_phase(db_session, journey_id=journey.id)
    headers = await auth_header(db_session, admin)
    resp = await client.patch(
        f"/api/phases/{phase.id}",
        json={"category_id": category.id, "icon_url": "https://cdn.example.com/icon.png"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["category_id"] == category.id
    assert body["icon_url"] == "https://cdn.example.com/icon.png"

    cleared = await client.patch(
        f"/api/phases/{phase.id}",
        json={"category_id": None, "icon_url": None},
        headers=headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["category_id"] is None
    assert cleared.json()["icon_url"] is None


async def test_update_phase_as_non_admin_forbidden(client, db_session):
    user = await make_user(db_session, email="user@example.com")
    journey = await make_journey(db_session)
    phase = await make_phase(db_session, journey_id=journey.id)
    headers = await auth_header(db_session, user)
    resp = await client.patch(f"/api/phases/{phase.id}", json={"name": "X"}, headers=headers)
    assert resp.status_code == 403


async def test_delete_phase_as_non_admin_forbidden(client, db_session):
    user = await make_user(db_session, email="user@example.com")
    journey = await make_journey(db_session)
    phase = await make_phase(db_session, journey_id=journey.id)
    headers = await auth_header(db_session, user)
    resp = await client.delete(f"/api/phases/{phase.id}", headers=headers)
    assert resp.status_code == 403


async def test_reorder_phases_happy_path(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session)
    p1 = await make_phase(db_session, name="A", journey_id=journey.id, sort_order=0)
    p2 = await make_phase(db_session, name="B", journey_id=journey.id, sort_order=1)
    headers = await auth_header(db_session, admin)
    resp = await client.post(
        "/api/phases/reorder",
        json={"journey_id": journey.id, "phase_ids": [p2.id, p1.id]},
        headers=headers,
    )
    assert resp.status_code == 204
    listed = await client.get(f"/api/phases?journey_id={journey.id}", headers=headers)
    assert [p["id"] for p in listed.json()] == [p2.id, p1.id]


async def test_reorder_phases_mismatched_set(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session)
    p1 = await make_phase(db_session, name="A", journey_id=journey.id)
    await make_phase(db_session, name="B", journey_id=journey.id, sort_order=1)
    headers = await auth_header(db_session, admin)
    resp = await client.post(
        "/api/phases/reorder",
        json={"journey_id": journey.id, "phase_ids": [p1.id]},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_reorder_phases_as_non_admin_forbidden(client, db_session):
    user = await make_user(db_session, email="user@example.com")
    journey = await make_journey(db_session)
    headers = await auth_header(db_session, user)
    resp = await client.post(
        "/api/phases/reorder",
        json={"journey_id": journey.id, "phase_ids": []},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_add_dependency_as_non_admin_forbidden(client, db_session):
    user = await make_user(db_session, email="user@example.com")
    journey = await make_journey(db_session)
    a = await make_phase(db_session, name="A", journey_id=journey.id)
    b = await make_phase(db_session, name="B", journey_id=journey.id)
    headers = await auth_header(db_session, user)
    resp = await client.post(
        f"/api/phases/{a.id}/dependencies",
        json={"depends_on_id": b.id},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_add_dependency_rejects_cycle(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session)
    a = await make_phase(db_session, name="A", journey_id=journey.id)
    b = await make_phase(db_session, name="B", journey_id=journey.id)
    c = await make_phase(db_session, name="C", journey_id=journey.id)
    await make_phase_dependency(db_session, b.id, a.id)
    await make_phase_dependency(db_session, c.id, b.id)
    headers = await auth_header(db_session, admin)
    resp = await client.post(
        f"/api/phases/{a.id}/dependencies",
        json={"depends_on_id": c.id},
        headers=headers,
    )
    assert resp.status_code == 409
