import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.org_scope import get_managed_org_ids, get_managed_project_ids
from app.services import language_service, organization_service, phase_service
from tests.baker import (
    make_language,
    make_organization,
    make_organization_member,
    make_phase,
    make_project,
    make_project_organization_access,
    make_project_phase,
    make_project_user_access,
    make_user,
)


@pytest.fixture()
async def client(db_session: AsyncSession):
    """The real application, because where the console gate is mounted is the thing under test."""
    from app.core.database import get_db
    from app.main import app

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


async def _headers(db_session: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


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
async def test_list_organizations_includes_the_ones_managed_directly(db_session) -> None:
    """An organization manager with no project still sees the organization they run."""
    owner = await make_user(db_session, email="org-owner@example.com")
    member_manager = await make_user(db_session, email="org-member-manager@example.com")
    await make_organization(db_session, slug="owned-org", name="Owned", manager_id=owner.id)
    joined = await make_organization(db_session, slug="joined-org", name="Joined")
    await make_organization(db_session, slug="stranger-org", name="Stranger")
    await make_organization_member(db_session, member_manager.id, joined.id, role="manager")

    owner_scope = await get_managed_org_ids(db_session, owner.id)
    orgs = await organization_service.list_organizations_by_projects(db_session, [], owner_scope)
    assert [o.slug for o in orgs] == ["owned-org"]

    member_scope = await get_managed_org_ids(db_session, member_manager.id)
    orgs = await organization_service.list_organizations_by_projects(db_session, [], member_scope)
    assert [o.slug for o in orgs] == ["joined-org"]


@pytest.mark.asyncio
async def test_list_organizations_unions_project_and_direct_scopes(db_session) -> None:
    """The two scopes add up instead of one replacing the other."""
    owner = await make_user(db_session, email="both-scopes@example.com")
    lang = await make_language(db_session, code="lou")
    managed = await make_project(db_session, language_id=lang.id, name="Managed")
    via_project = await make_organization(db_session, slug="via-project", name="A Via Project")
    await make_project_organization_access(db_session, managed.id, via_project.id)
    await make_organization(
        db_session, slug="via-manager", name="B Via Manager", manager_id=owner.id
    )

    scope = await get_managed_org_ids(db_session, owner.id)
    orgs = await organization_service.list_organizations_by_projects(
        db_session, [managed.id], scope
    )

    assert [o.slug for o in orgs] == ["via-project", "via-manager"]


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
async def test_list_languages_by_projects_leaves_out_the_deactivated(db_session) -> None:
    """A manager's list agrees with a direct read: a deactivated language is absent from both."""
    active = await make_language(db_session, code="lac")
    retired = await make_language(db_session, code="lrt")
    retired.is_active = False
    await db_session.commit()
    managed = await make_project(db_session, language_id=active.id, name="Active")
    also_managed = await make_project(db_session, language_id=retired.id, name="Retired")

    languages = await language_service.list_languages_by_projects(
        db_session, [managed.id, also_managed.id]
    )

    assert [lng.code for lng in languages] == ["lac"]


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


@pytest.mark.asyncio
async def test_console_gate_refuses_a_plain_member_on_the_project_list(db_session, client) -> None:
    lang = await make_language(db_session, code="cgl")
    user = await make_user(db_session, email="member@gate.com")
    project = await make_project(db_session, language_id=lang.id, name="Member Project")
    await make_project_user_access(db_session, project.id, user.id, role="member")

    response = await client.get("/api/projects", headers=await _headers(db_session, user))

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_console_gate_does_not_shadow_the_per_project_read(db_session, client) -> None:
    """The gate belongs to the console's collections, not to the routes ``assert_project_access``
    already answers for: a member of a project still reads that project and its phases."""
    lang = await make_language(db_session, code="cgr")
    user = await make_user(db_session, email="reader@gate.com")
    project = await make_project(db_session, language_id=lang.id, name="Member Project")
    await make_project_user_access(db_session, project.id, user.id, role="member")
    headers = await _headers(db_session, user)

    read = await client.get(f"/api/projects/{project.id}", headers=headers)
    phases = await client.get(f"/api/projects/{project.id}/phases", headers=headers)

    assert read.status_code == 200
    assert read.json()["name"] == "Member Project"
    assert phases.status_code == 200


@pytest.mark.asyncio
async def test_per_project_read_still_refuses_a_stranger(db_session, client) -> None:
    lang = await make_language(db_session, code="cgs")
    user = await make_user(db_session, email="stranger@gate.com")
    mine = await make_project(db_session, language_id=lang.id, name="Mine")
    theirs = await make_project(db_session, language_id=lang.id, name="Theirs")
    await make_project_user_access(db_session, mine.id, user.id, role="member")

    response = await client.get(
        f"/api/projects/{theirs.id}", headers=await _headers(db_session, user)
    )

    assert response.status_code == 403
