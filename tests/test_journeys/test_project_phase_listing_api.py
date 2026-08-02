from tests.baker import (
    make_journey,
    make_language,
    make_phase,
    make_phase_dependency,
    make_project,
    make_project_phase,
    make_user,
)
from tests.test_journeys.conftest import auth_header


async def _journey_project(db_session, *, code: str = "tst"):
    journey = await make_journey(db_session)
    first = await make_phase(db_session, name="First", journey_id=journey.id, sort_order=0)
    second = await make_phase(db_session, name="Second", journey_id=journey.id, sort_order=1)
    third = await make_phase(db_session, name="Third", journey_id=journey.id, sort_order=2)
    lang = await make_language(db_session, code=code)
    project = await make_project(db_session, language_id=lang.id, journey_id=journey.id)
    return journey, [first, second, third], project


async def test_project_phases_cover_full_journey(client, db_session):
    _journey, phases, project = await _journey_project(db_session)
    await make_project_phase(db_session, project.id, phases[1].id, status="in_progress")
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)

    resp = await client.get(f"/api/projects/{project.id}/phases", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert [row["phase_id"] for row in body] == [p.id for p in phases]
    assert [row["status"] for row in body] == ["not_started", "in_progress", "not_started"]


async def test_project_phases_with_deps_cover_full_journey(client, db_session):
    _journey, phases, project = await _journey_project(db_session)
    await make_phase_dependency(db_session, phases[1].id, phases[0].id)
    await make_project_phase(db_session, project.id, phases[0].id, status="completed")
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)

    resp = await client.get(f"/api/projects/{project.id}/phases-with-deps", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert [row["phase_id"] for row in body["phases"]] == [p.id for p in phases]
    assert [row["status"] for row in body["phases"]] == [
        "completed",
        "not_started",
        "not_started",
    ]
    assert body["dependencies"][phases[1].id] == [phases[0].id]
    assert body["dependencies"][phases[2].id] == []


async def test_project_without_journey_lists_attached_rows_only(client, db_session):
    journey = await make_journey(db_session)
    phase = await make_phase(db_session, journey_id=journey.id)
    lang = await make_language(db_session, code="tsu")
    project = await make_project(db_session, language_id=lang.id)
    await make_project_phase(db_session, project.id, phase.id, status="in_progress")
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)

    resp = await client.get(f"/api/projects/{project.id}/phases", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert [row["phase_id"] for row in body] == [phase.id]
    assert body[0]["status"] == "in_progress"


async def test_phases_by_project_resolve_through_journey(client, db_session):
    _journey, phases, project = await _journey_project(db_session)
    other_journey = await make_journey(db_session, name="Other")
    await make_phase(db_session, name="Foreign", journey_id=other_journey.id)
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)

    resp = await client.get(f"/api/phases?project_id={project.id}", headers=headers)
    assert resp.status_code == 200
    assert [row["id"] for row in resp.json()] == [p.id for p in phases]
