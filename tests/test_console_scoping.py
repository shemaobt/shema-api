import pytest

from app.core.org_scope import get_managed_project_ids
from app.services import language_service, organization_service, phase_service
from tests.baker import (
    make_language,
    make_organization,
    make_phase,
    make_project,
    make_project_organization_access,
    make_project_phase,
    make_project_user_access,
    make_user,
)


@pytest.mark.asyncio
async def test_get_managed_project_ids_only_manager_role(db_session) -> None:
    lang = await make_language(db_session, code="gmp")
    user = await make_user(db_session, email="gmp@scope.com")
    managed = await make_project(db_session, language_id=lang.id, name="Managed")
    member = await make_project(db_session, language_id=lang.id, name="MemberOnly")
    await make_project(db_session, language_id=lang.id, name="Unrelated")
    await make_project_user_access(db_session, managed.id, user.id, role="manager")
    await make_project_user_access(db_session, member.id, user.id, role="member")

    ids = await get_managed_project_ids(db_session, user.id)

    assert ids == [managed.id]


@pytest.mark.asyncio
async def test_list_organizations_by_projects(db_session) -> None:
    lang = await make_language(db_session, code="lob")
    managed = await make_project(db_session, language_id=lang.id, name="Managed")
    other = await make_project(db_session, language_id=lang.id, name="Other")
    org_a = await make_organization(db_session, slug="org-a")
    org_b = await make_organization(db_session, slug="org-b")
    await make_project_organization_access(db_session, managed.id, org_a.id)
    await make_project_organization_access(db_session, other.id, org_b.id)

    orgs = await organization_service.list_organizations_by_projects(db_session, [managed.id])

    assert [o.slug for o in orgs] == ["org-a"]
    assert await organization_service.list_organizations_by_projects(db_session, []) == []


@pytest.mark.asyncio
async def test_list_languages_by_projects(db_session) -> None:
    lang_a = await make_language(db_session, code="laa")
    lang_b = await make_language(db_session, code="lbb")
    managed = await make_project(db_session, language_id=lang_a.id, name="Managed")
    await make_project(db_session, language_id=lang_b.id, name="Other")

    languages = await language_service.list_languages_by_projects(db_session, [managed.id])

    assert [lng.code for lng in languages] == ["laa"]
    assert await language_service.list_languages_by_projects(db_session, []) == []


@pytest.mark.asyncio
async def test_list_phases_by_projects(db_session) -> None:
    lang = await make_language(db_session, code="lpp")
    managed = await make_project(db_session, language_id=lang.id, name="Managed")
    other = await make_project(db_session, language_id=lang.id, name="Other")
    ph_managed = await make_phase(db_session, name="Managed Phase")
    ph_other = await make_phase(db_session, name="Other Phase")
    await make_project_phase(db_session, managed.id, ph_managed.id)
    await make_project_phase(db_session, other.id, ph_other.id)

    phases = await phase_service.list_phases_by_projects(db_session, [managed.id])

    assert [p.name for p in phases] == ["Managed Phase"]
    assert await phase_service.list_phases_by_projects(db_session, []) == []


@pytest.mark.asyncio
async def test_list_phases_by_projects_filter_outside_scope_is_empty(db_session) -> None:
    lang = await make_language(db_session, code="lpf")
    managed = await make_project(db_session, language_id=lang.id, name="Managed")
    other = await make_project(db_session, language_id=lang.id, name="Other")
    ph = await make_phase(db_session, name="Phase")
    await make_project_phase(db_session, other.id, ph.id)

    result = await phase_service.list_phases_by_projects(
        db_session, [managed.id], project_id=other.id
    )

    assert result == []
