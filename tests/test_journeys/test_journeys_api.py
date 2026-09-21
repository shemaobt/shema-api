from sqlalchemy import select

from app.db.models.journey import Journey
from app.db.models.phase import Phase, PhaseStatusLog, ProjectPhase
from app.db.models.project import Project
from tests.baker import (
    make_journey,
    make_language,
    make_phase,
    make_phase_status_log,
    make_project,
    make_project_phase,
    make_user,
)
from tests.test_journeys.conftest import auth_header


async def test_list_journeys_with_counts(client, db_session):
    """The actor is an admin because the catalog is scoped to a manager's own
    projects since OBT-507; this test is about the counts, not about who reads."""
    user = await make_user(db_session, email="viewer@example.com", is_platform_admin=True)
    journey = await make_journey(db_session, name="Journey A")
    other = await make_journey(db_session, name="Journey B")
    await make_phase(db_session, name="P1", journey_id=journey.id)
    await make_phase(db_session, name="P2", journey_id=journey.id)
    lang = await make_language(db_session, code="tst")
    await make_project(db_session, language_id=lang.id, journey_id=journey.id)

    headers = await auth_header(db_session, user)
    resp = await client.get("/api/journeys", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    by_id = {j["id"]: j for j in body}
    assert by_id[journey.id]["phase_count"] == 2
    assert by_id[journey.id]["project_count"] == 1
    assert by_id[other.id]["phase_count"] == 0
    assert by_id[other.id]["project_count"] == 0


async def test_create_journey_as_admin(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)
    resp = await client.post(
        "/api/journeys",
        json={"name": "New journey", "description": "desc"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "New journey"
    assert body["description"] == "desc"
    assert body["created_by"] == admin.id
    assert body["phase_count"] == 0
    assert body["project_count"] == 0


async def test_create_journey_as_non_admin_forbidden(client, db_session):
    user = await make_user(db_session, email="user@example.com")
    headers = await auth_header(db_session, user)
    resp = await client.post("/api/journeys", json={"name": "Nope"}, headers=headers)
    assert resp.status_code == 403


async def test_get_journey_with_counts(client, db_session):
    """Admin actor for the same reason as the listing above (OBT-507)."""
    user = await make_user(db_session, email="viewer@example.com", is_platform_admin=True)
    journey = await make_journey(db_session, name="Journey A")
    await make_phase(db_session, name="P1", journey_id=journey.id)
    headers = await auth_header(db_session, user)
    resp = await client.get(f"/api/journeys/{journey.id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == journey.id
    assert body["phase_count"] == 1
    assert body["project_count"] == 0


async def test_get_journey_not_found(client, db_session):
    """Only an unscoped reader can be told an id is missing: a scoped one is
    refused first, which `test_journey_scope.py` pins on purpose (OBT-507)."""
    user = await make_user(db_session, email="viewer@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, user)
    resp = await client.get("/api/journeys/missing-id", headers=headers)
    assert resp.status_code == 404


async def test_update_journey_as_admin(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session, name="Old name")
    headers = await auth_header(db_session, admin)
    resp = await client.patch(
        f"/api/journeys/{journey.id}",
        json={"name": "New name", "description": "Updated"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New name"
    assert body["description"] == "Updated"


async def test_update_journey_clears_description_with_explicit_null(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session, name="Kept", description="To be cleared")
    headers = await auth_header(db_session, admin)
    resp = await client.patch(
        f"/api/journeys/{journey.id}",
        json={"description": None},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] is None
    assert body["name"] == "Kept"


async def test_update_journey_omitting_description_leaves_it_alone(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session, name="Old name", description="Kept")
    headers = await auth_header(db_session, admin)
    resp = await client.patch(
        f"/api/journeys/{journey.id}",
        json={"name": "New name"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Kept"


async def test_update_journey_as_non_admin_forbidden(client, db_session):
    user = await make_user(db_session, email="user@example.com")
    journey = await make_journey(db_session)
    headers = await auth_header(db_session, user)
    resp = await client.patch(f"/api/journeys/{journey.id}", json={"name": "X"}, headers=headers)
    assert resp.status_code == 403


async def test_delete_journey_as_non_admin_forbidden(client, db_session):
    user = await make_user(db_session, email="user@example.com")
    journey = await make_journey(db_session)
    headers = await auth_header(db_session, user)
    resp = await client.delete(f"/api/journeys/{journey.id}", headers=headers)
    assert resp.status_code == 403


async def test_delete_journey_cascades(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session, name="Doomed")
    phase = await make_phase(db_session, name="P1", journey_id=journey.id)
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id, journey_id=journey.id)
    await make_project_phase(db_session, project.id, phase.id, status="in_progress")
    await make_phase_status_log(
        db_session,
        project.id,
        phase.id,
        to_status="in_progress",
        changed_by=admin.id,
    )

    headers = await auth_header(db_session, admin)
    resp = await client.delete(f"/api/journeys/{journey.id}", headers=headers)
    assert resp.status_code == 204

    journeys = (await db_session.execute(select(Journey))).scalars().all()
    assert journeys == []
    phases = (await db_session.execute(select(Phase))).scalars().all()
    assert phases == []
    links = (await db_session.execute(select(ProjectPhase))).scalars().all()
    assert links == []
    logs = (await db_session.execute(select(PhaseStatusLog))).scalars().all()
    assert logs == []
    fresh_project = (
        (await db_session.execute(select(Project).where(Project.id == project.id))).scalars().one()
    )
    await db_session.refresh(fresh_project)
    assert fresh_project.journey_id is None
