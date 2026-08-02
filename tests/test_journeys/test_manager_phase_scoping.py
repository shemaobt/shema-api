from app.services import phase_service
from tests.baker import (
    make_journey,
    make_language,
    make_phase,
    make_project,
    make_project_phase,
)


async def test_list_phases_by_projects_returns_full_journey(db_session):
    lang = await make_language(db_session, code="mps")
    journey = await make_journey(db_session, name="Scoped Journey")
    managed = await make_project(
        db_session, language_id=lang.id, name="Managed", journey_id=journey.id
    )
    ph_a = await make_phase(db_session, name="A", journey_id=journey.id, sort_order=0)
    ph_b = await make_phase(db_session, name="B", journey_id=journey.id, sort_order=1)
    ph_c = await make_phase(db_session, name="C", journey_id=journey.id, sort_order=2)
    await make_phase(db_session, name="Elsewhere")
    await make_project_phase(db_session, managed.id, ph_b.id, status="in_progress")

    phases = await phase_service.list_phases_by_projects(db_session, [managed.id])

    assert [p.id for p in phases] == [ph_a.id, ph_b.id, ph_c.id]

    with_deps = await phase_service.list_phases_with_deps_by_projects(db_session, [managed.id])

    assert [p.id for p in with_deps.phases] == [ph_a.id, ph_b.id, ph_c.id]


async def test_list_phases_by_projects_link_fallback_without_journey(db_session):
    lang = await make_language(db_session, code="mpf")
    managed = await make_project(db_session, language_id=lang.id, name="Managed")
    other = await make_project(db_session, language_id=lang.id, name="Other")
    ph_managed = await make_phase(db_session, name="Managed Phase")
    ph_other = await make_phase(db_session, name="Other Phase")
    await make_project_phase(db_session, managed.id, ph_managed.id)
    await make_project_phase(db_session, other.id, ph_other.id)

    phases = await phase_service.list_phases_by_projects(db_session, [managed.id])

    assert [p.name for p in phases] == ["Managed Phase"]
    assert await phase_service.list_phases_by_projects(db_session, []) == []


async def test_list_phases_by_projects_filter_outside_scope_is_empty(db_session):
    lang = await make_language(db_session, code="mpo")
    managed = await make_project(db_session, language_id=lang.id, name="Managed")
    other = await make_project(db_session, language_id=lang.id, name="Other")
    ph = await make_phase(db_session, name="Phase")
    await make_project_phase(db_session, other.id, ph.id)

    result = await phase_service.list_phases_by_projects(
        db_session, [managed.id], project_id=other.id
    )

    assert result == []
