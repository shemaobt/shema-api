import httpx
import pytest
from httpx import ASGITransport

from app.db.models.phase import PhaseStatus
from app.services import project_service
from tests.baker import (
    make_language,
    make_phase,
    make_project,
    make_project_phase,
    make_project_user_access,
    make_user,
)


@pytest.fixture()
async def client(db_session):
    from fastapi import FastAPI

    from app.api.phases import router as phases_router
    from app.api.projects.phases import router as project_phases_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(phases_router, prefix="/api/phases")
    test_app.include_router(project_phases_router, prefix="/api/projects")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def auth_header(db_session, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


@pytest.fixture()
async def admin(db_session):
    return await make_user(db_session, email="admin@example.com", is_platform_admin=True)


@pytest.fixture()
async def manager(db_session):
    return await make_user(db_session, email="manager@example.com")


@pytest.fixture()
async def managed_project(db_session, manager):
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id, name="Managed")
    await project_service.grant_user_access(db_session, project.id, manager.id, role="manager")
    return project


# ── the phase catalog is platform-admin only ─────────────────────────────────


@pytest.mark.asyncio
async def test_manager_cannot_create_phase(client, db_session, manager) -> None:
    res = await client.post(
        "/api/phases", json={"name": "Sneaky"}, headers=await auth_header(db_session, manager)
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_update_phase(client, db_session, manager) -> None:
    phase = await make_phase(db_session, name="Owned by platform")
    res = await client.patch(
        f"/api/phases/{phase.id}",
        json={"name": "Renamed"},
        headers=await auth_header(db_session, manager),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_delete_phase(client, db_session, manager) -> None:
    phase = await make_phase(db_session, name="Owned by platform")
    res = await client.delete(
        f"/api/phases/{phase.id}", headers=await auth_header(db_session, manager)
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_add_dependency(client, db_session, manager) -> None:
    a = await make_phase(db_session, name="A")
    b = await make_phase(db_session, name="B")
    res = await client.post(
        f"/api/phases/{a.id}/dependencies",
        json={"depends_on_id": b.id},
        headers=await auth_header(db_session, manager),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_remove_dependency(client, db_session, manager) -> None:
    a = await make_phase(db_session, name="A")
    b = await make_phase(db_session, name="B")
    res = await client.delete(
        f"/api/phases/{a.id}/dependencies/{b.id}",
        headers=await auth_header(db_session, manager),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_creates_phase_and_it_lands_on_every_project(
    client, db_session, admin, managed_project
) -> None:
    res = await client.post(
        "/api/phases",
        json={"name": "Data Collection"},
        headers=await auth_header(db_session, admin),
    )
    assert res.status_code == 201
    phase_id = res.json()["id"]

    res = await client.get(
        f"/api/projects/{managed_project.id}/phases",
        headers=await auth_header(db_session, admin),
    )
    assert res.status_code == 200
    assert [p["phase_id"] for p in res.json()] == [phase_id]


@pytest.mark.asyncio
async def test_admin_manages_dependencies(client, db_session, admin) -> None:
    a = await make_phase(db_session, name="A")
    b = await make_phase(db_session, name="B")
    headers = await auth_header(db_session, admin)

    res = await client.post(
        f"/api/phases/{a.id}/dependencies", json={"depends_on_id": b.id}, headers=headers
    )
    assert res.status_code == 201

    res = await client.delete(f"/api/phases/{a.id}/dependencies/{b.id}", headers=headers)
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_manager_can_read_the_catalog(client, db_session, manager) -> None:
    await make_phase(db_session, name="A")
    res = await client.get("/api/phases", headers=await auth_header(db_session, manager))
    assert res.status_code == 200
    assert [p["name"] for p in res.json()] == ["A"]


# ── status is the manager's only write ───────────────────────────────────────


@pytest.mark.asyncio
async def test_manager_updates_status_on_own_project(
    client, db_session, manager, managed_project
) -> None:
    phase = await make_phase(db_session, name="Phase")
    await make_project_phase(db_session, managed_project.id, phase.id)

    res = await client.patch(
        f"/api/projects/{managed_project.id}/phases/{phase.id}",
        json={"status": PhaseStatus.IN_PROGRESS},
        headers=await auth_header(db_session, manager),
    )
    assert res.status_code == 200
    assert res.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_manager_cannot_update_status_on_another_project(client, db_session, manager) -> None:
    lang = await make_language(db_session, code="oth")
    other = await make_project(db_session, language_id=lang.id, name="Other")
    phase = await make_phase(db_session, name="Phase")
    await make_project_phase(db_session, other.id, phase.id)

    res = await client.patch(
        f"/api/projects/{other.id}/phases/{phase.id}",
        json={"status": PhaseStatus.COMPLETED},
        headers=await auth_header(db_session, manager),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_project_member_cannot_update_status(client, db_session, managed_project) -> None:
    member = await make_user(db_session, email="member@example.com")
    await make_project_user_access(db_session, managed_project.id, member.id)
    phase = await make_phase(db_session, name="Phase")
    await make_project_phase(db_session, managed_project.id, phase.id)

    res = await client.patch(
        f"/api/projects/{managed_project.id}/phases/{phase.id}",
        json={"status": PhaseStatus.COMPLETED},
        headers=await auth_header(db_session, member),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_unknown_status_is_rejected(client, db_session, manager, managed_project) -> None:
    phase = await make_phase(db_session, name="Phase")
    await make_project_phase(db_session, managed_project.id, phase.id)

    res = await client.patch(
        f"/api/projects/{managed_project.id}/phases/{phase.id}",
        json={"status": "banana"},
        headers=await auth_header(db_session, manager),
    )
    assert res.status_code == 422


# ── attach/detach are gone: phases are global ────────────────────────────────


@pytest.mark.asyncio
async def test_attach_and_detach_endpoints_are_gone(
    client, db_session, admin, managed_project
) -> None:
    phase = await make_phase(db_session, name="Phase")
    headers = await auth_header(db_session, admin)

    res = await client.post(
        f"/api/projects/{managed_project.id}/phases",
        json={"phase_id": phase.id},
        headers=headers,
    )
    assert res.status_code == 405

    res = await client.delete(
        f"/api/projects/{managed_project.id}/phases/{phase.id}", headers=headers
    )
    assert res.status_code == 405
