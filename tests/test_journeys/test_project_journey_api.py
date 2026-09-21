from sqlalchemy import select

from app.db.models.phase import PhaseStatusLog, ProjectPhase
from tests.baker import (
    make_journey,
    make_language,
    make_phase,
    make_phase_status_log,
    make_project,
    make_project_phase,
    make_project_user_access,
    make_user,
)
from tests.test_journeys.conftest import auth_header


async def test_assign_journey_as_admin(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session)
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id)
    headers = await auth_header(db_session, admin)
    resp = await client.put(
        f"/api/projects/{project.id}/journey",
        json={"journey_id": journey.id},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["journey_id"] == journey.id


async def test_assign_journey_as_non_admin_forbidden(client, db_session):
    user = await make_user(db_session, email="user@example.com")
    journey = await make_journey(db_session)
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id)
    await make_project_user_access(db_session, project.id, user.id, role="manager")
    headers = await auth_header(db_session, user)
    resp = await client.put(
        f"/api/projects/{project.id}/journey",
        json={"journey_id": journey.id},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_assign_journey_prunes_foreign_statuses_keeps_shared(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    old_journey = await make_journey(db_session, name="Old")
    new_journey = await make_journey(db_session, name="New")
    old_phase = await make_phase(db_session, name="Old phase", journey_id=old_journey.id)
    new_phase = await make_phase(db_session, name="New phase", journey_id=new_journey.id)
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id, journey_id=old_journey.id)
    await make_project_phase(db_session, project.id, old_phase.id, status="in_progress")
    kept_link = await make_project_phase(db_session, project.id, new_phase.id, status="completed")
    await make_phase_status_log(
        db_session,
        project.id,
        old_phase.id,
        to_status="in_progress",
        changed_by=admin.id,
    )

    headers = await auth_header(db_session, admin)
    resp = await client.put(
        f"/api/projects/{project.id}/journey",
        json={"journey_id": new_journey.id},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["journey_id"] == new_journey.id

    links = (
        (
            await db_session.execute(
                select(ProjectPhase).where(ProjectPhase.project_id == project.id)
            )
        )
        .scalars()
        .all()
    )
    assert [link.id for link in links] == [kept_link.id]
    assert links[0].status == "completed"
    logs = (
        (
            await db_session.execute(
                select(PhaseStatusLog).where(PhaseStatusLog.project_id == project.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(logs) == 1


async def test_assign_journey_null_clears_and_prunes_all(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session)
    phase = await make_phase(db_session, journey_id=journey.id)
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id, journey_id=journey.id)
    await make_project_phase(db_session, project.id, phase.id, status="in_progress")
    headers = await auth_header(db_session, admin)
    resp = await client.put(
        f"/api/projects/{project.id}/journey",
        json={"journey_id": None},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["journey_id"] is None
    links = (
        (
            await db_session.execute(
                select(ProjectPhase).where(ProjectPhase.project_id == project.id)
            )
        )
        .scalars()
        .all()
    )
    assert links == []


async def test_assign_unknown_journey_unknown_reference(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id)
    headers = await auth_header(db_session, admin)
    resp = await client.put(
        f"/api/projects/{project.id}/journey",
        json={"journey_id": "missing"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "UNKNOWN_REFERENCE"


async def test_assign_journey_empty_body_rejected(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session)
    phase = await make_phase(db_session, journey_id=journey.id)
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id, journey_id=journey.id)
    link = await make_project_phase(db_session, project.id, phase.id, status="in_progress")
    headers = await auth_header(db_session, admin)
    resp = await client.put(f"/api/projects/{project.id}/journey", json={}, headers=headers)
    assert resp.status_code == 422
    refreshed = (
        (
            await db_session.execute(
                select(ProjectPhase).where(ProjectPhase.project_id == project.id)
            )
        )
        .scalars()
        .all()
    )
    assert [row.id for row in refreshed] == [link.id]


async def test_project_response_includes_journey_id(client, db_session):
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    journey = await make_journey(db_session)
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id, journey_id=journey.id)
    headers = await auth_header(db_session, admin)
    resp = await client.get(f"/api/projects/{project.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["journey_id"] == journey.id
