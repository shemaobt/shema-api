import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.phase import PhaseStatus
from app.models.phase import PhaseCreate, PhaseUpdate
from app.services import phase_service, project_service
from tests.baker import (
    make_language,
    make_phase,
    make_phase_dependency,
    make_project,
    make_project_phase,
)


@pytest.mark.asyncio
async def test_create_phase_without_project(db_session) -> None:
    payload = PhaseCreate(name="Acoustemes Training", description="Phase 1")
    phase = await phase_service.create_phase(db_session, payload)
    assert phase.name == "Acoustemes Training"
    assert phase.description == "Phase 1"
    assert phase.id is not None


@pytest.mark.asyncio
async def test_create_phase_attaches_it_to_every_existing_project(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    p1 = await make_project(db_session, language_id=lang.id, name="Proj1")
    p2 = await make_project(db_session, language_id=lang.id, name="Proj2")

    phase = await phase_service.create_phase(db_session, PhaseCreate(name="Global"))

    project_ids = await phase_service.list_projects_for_phase(db_session, phase.id)
    assert set(project_ids) == {p1.id, p2.id}


@pytest.mark.asyncio
async def test_create_project_attaches_every_existing_phase(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    a = await make_phase(db_session, name="A")
    b = await make_phase(db_session, name="B")

    project = await project_service.create_project(db_session, name="New", language_id=lang.id)

    phases = await phase_service.list_phases(db_session, project_id=project.id)
    assert {p.id for p in phases} == {a.id, b.id}


@pytest.mark.asyncio
async def test_new_project_phases_start_not_started(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    await make_phase(db_session, name="A")

    project = await project_service.create_project(db_session, name="New", language_id=lang.id)

    links = await phase_service.list_project_phases_with_details(db_session, project.id)
    assert [link.status for link in links] == [PhaseStatus.NOT_STARTED]


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
async def test_list_phases_by_project_id(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id, name="P1")
    phase = await make_phase(db_session, name="Phase One")
    await make_project_phase(db_session, project.id, phase.id)
    phases = await phase_service.list_phases(db_session, project_id=project.id)
    assert len(phases) == 1
    assert phases[0].id == phase.id
    assert phases[0].name == "Phase One"


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
async def test_update_project_phase_status(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id)
    phase = await make_phase(db_session, name="Phase")
    await make_project_phase(db_session, project.id, phase.id)

    link = await phase_service.update_project_phase_status(
        db_session, project.id, phase.id, PhaseStatus.IN_PROGRESS
    )
    assert link.status == PhaseStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_update_project_phase_status_raises_when_pair_missing(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    project = await make_project(db_session, language_id=lang.id)
    phase = await make_phase(db_session, name="Phase")

    with pytest.raises(NotFoundError, match="not attached"):
        await phase_service.update_project_phase_status(
            db_session, project.id, phase.id, PhaseStatus.COMPLETED
        )


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
