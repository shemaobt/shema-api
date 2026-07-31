import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.models.phase import PhaseCreate, PhaseUpdate
from app.services import phase_service
from tests.baker import (
    make_journey,
    make_language,
    make_phase,
    make_phase_dependency,
    make_project,
    make_project_phase,
)


@pytest.mark.asyncio
async def test_create_phase_without_project(db_session) -> None:
    journey = await make_journey(db_session)
    payload = PhaseCreate(name="Acoustemes Training", description="Phase 1", journey_id=journey.id)
    phase = await phase_service.create_phase(db_session, payload)
    assert phase.name == "Acoustemes Training"
    assert phase.description == "Phase 1"
    assert phase.journey_id == journey.id
    assert phase.sort_order == 0
    assert phase.id is not None


@pytest.mark.asyncio
async def test_list_phases_empty(db_session) -> None:
    phases = await phase_service.list_phases(db_session)
    assert phases == []


@pytest.mark.asyncio
async def test_list_phases_all(db_session) -> None:
    await make_phase(db_session, name="A")
    await make_phase(db_session, name="B")
    phases = await phase_service.list_phases(db_session)
    assert len(phases) == 2
    names = {p.name for p in phases}
    assert names == {"A", "B"}


@pytest.mark.asyncio
async def test_list_phases_by_project_id_after_attach(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id, name="P1")
    phase = await make_phase(db_session, name="Phase One")
    await make_project_phase(db_session, project.id, phase.id)
    phases = await phase_service.list_phases(db_session, project_id=project.id)
    assert len(phases) == 1
    assert phases[0].id == phase.id
    assert phases[0].name == "Phase One"


@pytest.mark.asyncio
async def test_attach_phase_to_project(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id)
    phase = await make_phase(db_session, name="Shared Phase")
    link = await phase_service.attach_phase_to_project(db_session, project.id, phase.id)
    assert link.project_id == project.id
    assert link.phase_id == phase.id


@pytest.mark.asyncio
async def test_attach_same_phase_to_multiple_projects(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    p1 = await make_project(db_session, language_id=lang.id, name="Proj1")
    p2 = await make_project(db_session, language_id=lang.id, name="Proj2")
    phase = await make_phase(db_session, name="Shared")
    await phase_service.attach_phase_to_project(db_session, p1.id, phase.id)
    await phase_service.attach_phase_to_project(db_session, p2.id, phase.id)
    project_ids = await phase_service.list_projects_for_phase(db_session, phase.id)
    assert set(project_ids) == {p1.id, p2.id}


@pytest.mark.asyncio
async def test_attach_phase_already_attached_raises(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id)
    phase = await make_phase(db_session, name="Phase")
    await phase_service.attach_phase_to_project(db_session, project.id, phase.id)
    with pytest.raises(ConflictError, match="already attached"):
        await phase_service.attach_phase_to_project(db_session, project.id, phase.id)


@pytest.mark.asyncio
async def test_detach_phase_from_project(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id)
    phase = await make_phase(db_session, name="Phase")
    await make_project_phase(db_session, project.id, phase.id)
    await phase_service.detach_phase_from_project(db_session, project.id, phase.id)
    project_ids = await phase_service.list_projects_for_phase(db_session, phase.id)
    assert project_ids == []


@pytest.mark.asyncio
async def test_get_phase_or_404_raises_when_missing(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Phase .* not found"):
        await phase_service.get_phase_or_404(db_session, "00000000-0000-0000-0000-000000000000")


@pytest.mark.asyncio
async def test_update_phase(db_session) -> None:
    phase = await make_phase(db_session, name="Old")
    updated = await phase_service.update_phase(
        db_session, phase.id, PhaseUpdate(name="New", description="Updated desc")
    )
    assert updated.name == "New"
    assert updated.description == "Updated desc"


@pytest.mark.asyncio
async def test_delete_phase_cascades_links_and_dependencies(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id)
    phase = await make_phase(db_session, name="To Delete")
    await make_project_phase(db_session, project.id, phase.id)
    other = await make_phase(db_session, name="Other")
    await make_phase_dependency(db_session, phase.id, other.id)
    await phase_service.delete_phase(db_session, phase.id)
    phases = await phase_service.list_phases(db_session)
    assert len(phases) == 1
    assert phases[0].id == other.id
    project_ids = await phase_service.list_projects_for_phase(db_session, other.id)
    assert project_ids == []


@pytest.mark.asyncio
async def test_add_dependency(db_session) -> None:
    a = await make_phase(db_session, name="A")
    b = await make_phase(db_session, name="B")
    dep = await phase_service.add_dependency(db_session, a.id, b.id)
    assert dep.phase_id == a.id
    assert dep.depends_on_id == b.id


@pytest.mark.asyncio
async def test_list_dependencies(db_session) -> None:
    a = await make_phase(db_session, name="A")
    b = await make_phase(db_session, name="B")
    c = await make_phase(db_session, name="C")
    await make_phase_dependency(db_session, a.id, b.id)
    await make_phase_dependency(db_session, a.id, c.id)
    deps = await phase_service.list_dependencies(db_session, a.id)
    assert len(deps) == 2
    depends_on_ids = {d.depends_on_id for d in deps}
    assert depends_on_ids == {b.id, c.id}


@pytest.mark.asyncio
async def test_add_self_dependency_raises(db_session) -> None:
    phase = await make_phase(db_session, name="Self")
    with pytest.raises(ConflictError, match="cannot depend on itself"):
        await phase_service.add_dependency(db_session, phase.id, phase.id)


@pytest.mark.asyncio
async def test_add_duplicate_dependency_raises(db_session) -> None:
    a = await make_phase(db_session, name="A")
    b = await make_phase(db_session, name="B")
    await phase_service.add_dependency(db_session, a.id, b.id)
    with pytest.raises(ConflictError, match="Dependency already exists"):
        await phase_service.add_dependency(db_session, a.id, b.id)


@pytest.mark.asyncio
async def test_remove_dependency(db_session) -> None:
    a = await make_phase(db_session, name="A")
    b = await make_phase(db_session, name="B")
    await make_phase_dependency(db_session, a.id, b.id)
    await phase_service.remove_dependency(db_session, a.id, b.id)
    deps = await phase_service.list_dependencies(db_session, a.id)
    assert deps == []


@pytest.mark.asyncio
async def test_attach_phase_to_project_raises_when_project_not_found(db_session) -> None:
    phase = await make_phase(db_session, name="Phase")
    with pytest.raises(NotFoundError, match=r"Project .* not found"):
        await phase_service.attach_phase_to_project(
            db_session, "00000000-0000-0000-0000-000000000000", phase.id
        )


@pytest.mark.asyncio
async def test_attach_phase_to_project_raises_when_phase_not_found(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id)
    with pytest.raises(NotFoundError, match=r"Phase .* not found"):
        await phase_service.attach_phase_to_project(
            db_session, project.id, "00000000-0000-0000-0000-000000000000"
        )
