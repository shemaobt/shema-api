from sqlalchemy import select

from app.db.models.phase import ProjectPhase
from tests.baker import (
    make_journey,
    make_language,
    make_phase,
    make_project,
    make_project_phase,
    make_project_user_access,
    make_user,
)
from tests.test_journeys.conftest import auth_header


async def _project_with_phase(db_session):
    journey = await make_journey(db_session)
    phase = await make_phase(db_session, journey_id=journey.id)
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id, journey_id=journey.id)
    return journey, phase, project


async def test_status_update_as_manager_upserts_row(client, db_session):
    _journey, phase, project = await _project_with_phase(db_session)
    manager = await make_user(db_session, email="manager@example.com")
    await make_project_user_access(db_session, project.id, manager.id, role="manager")
    headers = await auth_header(db_session, manager)
    resp = await client.patch(
        f"/api/projects/{project.id}/phases/{phase.id}",
        json={"status": "in_progress"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["phase_id"] == phase.id
    link = (
        (
            await db_session.execute(
                select(ProjectPhase).where(
                    ProjectPhase.project_id == project.id,
                    ProjectPhase.phase_id == phase.id,
                )
            )
        )
        .scalars()
        .one()
    )
    assert link.status == "in_progress"


async def test_status_update_as_member_forbidden(client, db_session):
    _journey, phase, project = await _project_with_phase(db_session)
    member = await make_user(db_session, email="member@example.com")
    await make_project_user_access(db_session, project.id, member.id, role="member")
    headers = await auth_header(db_session, member)
    resp = await client.patch(
        f"/api/projects/{project.id}/phases/{phase.id}",
        json={"status": "in_progress"},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_status_update_as_admin_allowed(client, db_session):
    _journey, phase, project = await _project_with_phase(db_session)
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    await make_project_phase(db_session, project.id, phase.id, status="in_progress")
    headers = await auth_header(db_session, admin)
    resp = await client.patch(
        f"/api/projects/{project.id}/phases/{phase.id}",
        json={"status": "completed"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


async def test_status_update_phase_not_in_project_journey(client, db_session):
    _journey, _phase, project = await _project_with_phase(db_session)
    other_journey = await make_journey(db_session, name="Other")
    foreign_phase = await make_phase(db_session, journey_id=other_journey.id)
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)
    resp = await client.patch(
        f"/api/projects/{project.id}/phases/{foreign_phase.id}",
        json={"status": "in_progress"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_status_update_invalid_status(client, db_session):
    _journey, phase, project = await _project_with_phase(db_session)
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)
    resp = await client.patch(
        f"/api/projects/{project.id}/phases/{phase.id}",
        json={"status": "on_fire"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_status_update_note_required_for_blocking_statuses(client, db_session):
    _journey, phase, project = await _project_with_phase(db_session)
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)
    for status_value in ("delayed", "blocked", "cancelled"):
        resp = await client.patch(
            f"/api/projects/{project.id}/phases/{phase.id}",
            json={"status": status_value},
            headers=headers,
        )
        assert resp.status_code == 422
    with_note = await client.patch(
        f"/api/projects/{project.id}/phases/{phase.id}",
        json={"status": "blocked", "note": "Waiting on vendor"},
        headers=headers,
    )
    assert with_note.status_code == 200
    assert with_note.json()["status"] == "blocked"


async def test_status_update_missing_project_or_phase_404(client, db_session):
    _journey, phase, project = await _project_with_phase(db_session)
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)
    missing_phase = await client.patch(
        f"/api/projects/{project.id}/phases/missing",
        json={"status": "in_progress"},
        headers=headers,
    )
    assert missing_phase.status_code == 404
    missing_project = await client.patch(
        f"/api/projects/missing/phases/{phase.id}",
        json={"status": "in_progress"},
        headers=headers,
    )
    assert missing_project.status_code == 404


async def test_status_log_entries_newest_first(client, db_session):
    _journey, phase, project = await _project_with_phase(db_session)
    admin = await make_user(
        db_session,
        email="admin@example.com",
        display_name="Admin One",
        is_platform_admin=True,
    )
    headers = await auth_header(db_session, admin)
    first = await client.patch(
        f"/api/projects/{project.id}/phases/{phase.id}",
        json={"status": "in_progress"},
        headers=headers,
    )
    assert first.status_code == 200
    second = await client.patch(
        f"/api/projects/{project.id}/phases/{phase.id}",
        json={"status": "delayed", "note": "Slipped a week"},
        headers=headers,
    )
    assert second.status_code == 200

    resp = await client.get(
        f"/api/projects/{project.id}/phases/status-log",
        params={"phase_id": phase.id},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["from_status"] == "in_progress"
    assert body[0]["to_status"] == "delayed"
    assert body[0]["note"] == "Slipped a week"
    assert body[0]["changed_by"] == admin.id
    assert body[0]["changed_by_name"] == "Admin One"
    assert body[0]["is_admin_author"] is True
    assert body[1]["from_status"] == "not_started"
    assert body[1]["to_status"] == "in_progress"
    assert body[1]["note"] is None


async def test_status_log_visible_to_project_member(client, db_session):
    _journey, phase, project = await _project_with_phase(db_session)
    manager = await make_user(db_session, email="manager@example.com")
    await make_project_user_access(db_session, project.id, manager.id, role="manager")
    member = await make_user(db_session, email="member@example.com")
    await make_project_user_access(db_session, project.id, member.id, role="member")
    manager_headers = await auth_header(db_session, manager)
    update = await client.patch(
        f"/api/projects/{project.id}/phases/{phase.id}",
        json={"status": "in_progress"},
        headers=manager_headers,
    )
    assert update.status_code == 200
    member_headers = await auth_header(db_session, member)
    resp = await client.get(
        f"/api/projects/{project.id}/phases/status-log",
        headers=member_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["is_admin_author"] is False
    assert body[0]["changed_by_name"] == "Test User"


async def test_status_log_forbidden_for_outsider(client, db_session):
    _journey, _phase, project = await _project_with_phase(db_session)
    outsider = await make_user(db_session, email="outsider@example.com")
    headers = await auth_header(db_session, outsider)
    resp = await client.get(
        f"/api/projects/{project.id}/phases/status-log",
        headers=headers,
    )
    assert resp.status_code == 403
