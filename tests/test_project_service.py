import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.services import project_service
from tests.baker import (
    make_language,
    make_organization,
    make_organization_member,
    make_project,
    make_project_organization_access,
    make_project_user_access,
    make_user,
)


@pytest.mark.asyncio
async def test_create_project(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await project_service.create_project(
        db_session, name="Kokama Bible", language_id=lang.id, description="Kokama project"
    )
    assert project.name == "Kokama Bible"
    assert project.language_id == lang.id
    assert project.description == "Kokama project"


@pytest.mark.asyncio
async def test_create_project_assigns_creator_as_manager(db_session) -> None:
    from sqlalchemy import select

    from app.db.models.project import ProjectUserAccess

    lang = await make_language(db_session, code="kos")
    user = await make_user(db_session)
    project = await project_service.create_project(
        db_session,
        name="Creator Project",
        language_id=lang.id,
        creator_user_id=str(user.id),
    )
    stmt = select(ProjectUserAccess).where(
        ProjectUserAccess.project_id == project.id,
        ProjectUserAccess.user_id == str(user.id),
    )
    access = (await db_session.execute(stmt)).scalar_one()
    assert access.role == "manager"


@pytest.mark.asyncio
async def test_create_project_with_location(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await project_service.create_project(
        db_session,
        name="São Paulo Project",
        language_id=lang.id,
        latitude=-23.5505,
        longitude=-46.6333,
        location_display_name="São Paulo, Brazil",
    )
    assert project.latitude == -23.5505
    assert project.longitude == -46.6333
    assert project.location_display_name == "São Paulo, Brazil"


@pytest.mark.asyncio
async def test_update_project_location(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id, name="No Location")
    assert project.latitude is None
    assert project.longitude is None
    updated = await project_service.update_project_location(
        db_session,
        project.id,
        latitude=-23.5505,
        longitude=-46.6333,
        location_display_name="São Paulo, Brazil",
    )
    assert updated.latitude == -23.5505
    assert updated.longitude == -46.6333
    assert updated.location_display_name == "São Paulo, Brazil"


@pytest.mark.asyncio
async def test_update_project_location_partial(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(
        db_session,
        language_id=lang.id,
        name="Partial",
        latitude=-23.0,
        longitude=-46.0,
        location_display_name="Somewhere",
    )
    updated = await project_service.update_project_location(
        db_session, project.id, location_display_name="Updated Place Name"
    )
    assert updated.latitude == -23.0
    assert updated.longitude == -46.0
    assert updated.location_display_name == "Updated Place Name"


@pytest.mark.asyncio
async def test_update_project_location_raises_when_not_found(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Project .* not found"):
        await project_service.update_project_location(
            db_session,
            "00000000-0000-0000-0000-000000000000",
            latitude=0.0,
            longitude=0.0,
        )


@pytest.mark.asyncio
async def test_get_project_by_id(db_session) -> None:
    lang = await make_language(db_session, code="tst")
    created = await make_project(db_session, language_id=lang.id, name="P1")
    project = await project_service.get_project_by_id(db_session, created.id)
    assert project is not None
    assert project.id == created.id


@pytest.mark.asyncio
async def test_get_project_or_404_raises_when_missing(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Project .* not found"):
        await project_service.get_project_or_404(db_session, "00000000-0000-0000-0000-000000000000")


@pytest.mark.asyncio
async def test_can_access_project_true_via_direct_user(db_session) -> None:
    user = await make_user(db_session, email="u@example.com")
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id)
    await make_project_user_access(db_session, project.id, user.id)
    result = await project_service.can_access_project(db_session, user.id, project.id)
    assert result is True


@pytest.mark.asyncio
async def test_can_access_project_true_via_organization(db_session) -> None:
    user = await make_user(db_session, email="orguser@example.com")
    org = await make_organization(db_session, slug="org")
    await make_organization_member(db_session, user.id, org.id)
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id)
    await make_project_organization_access(db_session, project.id, org.id)
    result = await project_service.can_access_project(db_session, user.id, project.id)
    assert result is True


@pytest.mark.asyncio
async def test_can_access_project_false(db_session) -> None:
    user = await make_user(db_session, email="nobody@example.com")
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id)
    result = await project_service.can_access_project(db_session, user.id, project.id)
    assert result is False


@pytest.mark.asyncio
async def test_list_projects_accessible_to_user_includes_direct(db_session) -> None:
    user = await make_user(db_session, email="direct@example.com")
    lang = await make_language(db_session, code="kos")
    p1 = await make_project(db_session, language_id=lang.id, name="Alpha")
    await make_project_user_access(db_session, p1.id, user.id)
    projects = await project_service.list_projects_accessible_to_user(db_session, user.id)
    assert len(projects) == 1
    assert projects[0].id == p1.id


@pytest.mark.asyncio
async def test_list_projects_accessible_to_user_includes_via_org(db_session) -> None:
    user = await make_user(db_session, email="viaorg@example.com")
    org = await make_organization(db_session, slug="team")
    await make_organization_member(db_session, user.id, org.id)
    lang = await make_language(db_session, code="kos")
    p1 = await make_project(db_session, language_id=lang.id, name="Team Project")
    await make_project_organization_access(db_session, p1.id, org.id)
    projects = await project_service.list_projects_accessible_to_user(db_session, user.id)
    assert len(projects) == 1
    assert projects[0].id == p1.id


@pytest.mark.asyncio
async def test_list_projects_accessible_to_user_empty_when_no_access(db_session) -> None:
    user = await make_user(db_session, email="noaccess@example.com")
    lang = await make_language(db_session, code="kos")
    await make_project(db_session, language_id=lang.id, name="Other Project")
    projects = await project_service.list_projects_accessible_to_user(db_session, user.id)
    assert projects == []


@pytest.mark.asyncio
async def test_grant_user_access_creates_access(db_session) -> None:
    user = await make_user(db_session, email="grant@example.com")
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id)
    access = await project_service.grant_user_access(db_session, project.id, user.id)
    assert access.project_id == project.id
    assert access.user_id == user.id


@pytest.mark.asyncio
async def test_grant_user_access_idempotent(db_session) -> None:
    user = await make_user(db_session, email="idem@example.com")
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id)
    await make_project_user_access(db_session, project.id, user.id)
    access = await project_service.grant_user_access(db_session, project.id, user.id)
    assert access.project_id == project.id
    assert access.user_id == user.id


@pytest.mark.asyncio
async def test_grant_organization_access_creates_access(db_session) -> None:
    org = await make_organization(db_session, slug="new-org")
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id)
    access = await project_service.grant_organization_access(db_session, project.id, org.id)
    assert access.project_id == project.id
    assert access.organization_id == org.id


@pytest.mark.asyncio
async def test_update_project_name_and_description(db_session) -> None:
    lang = await make_language(db_session, name="English", code="eng")
    project = await make_project(db_session, lang.id, name="Old Name", description="Old desc")
    updated = await project_service.update_project(
        db_session, project.id, name="New Name", description="New desc"
    )
    assert updated.name == "New Name"
    assert updated.description == "New desc"
    assert updated.language_id == lang.id


@pytest.mark.asyncio
async def test_update_project_changes_language(db_session) -> None:
    lang1 = await make_language(db_session, name="English", code="eng")
    lang2 = await make_language(db_session, name="French", code="fra")
    project = await make_project(db_session, lang1.id, name="Project")
    updated = await project_service.update_project(db_session, project.id, language_id=lang2.id)
    assert updated.language_id == lang2.id


@pytest.mark.asyncio
async def test_update_project_raises_not_found_for_missing_project(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Project .* not found"):
        await project_service.update_project(
            db_session, "00000000-0000-0000-0000-000000000000", name="X"
        )


@pytest.mark.asyncio
async def test_update_project_raises_not_found_for_invalid_language(db_session) -> None:
    lang = await make_language(db_session, name="English", code="eng")
    project = await make_project(db_session, lang.id, name="Project")
    with pytest.raises(NotFoundError, match="Language not found"):
        await project_service.update_project(
            db_session,
            project.id,
            language_id="00000000-0000-0000-0000-000000000000",
        )


@pytest.mark.asyncio
async def test_create_project_rejects_inactive_language(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    lang.is_active = False
    await db_session.commit()
    with pytest.raises(ValidationError, match="not active"):
        await project_service.create_project(db_session, name="X", language_id=lang.id)


@pytest.mark.asyncio
async def test_update_project_rejects_inactive_language(db_session) -> None:
    active = await make_language(db_session, code="act")
    inactive = await make_language(db_session, code="ina")
    project = await make_project(db_session, active.id, name="P")
    inactive.is_active = False
    await db_session.commit()
    with pytest.raises(ValidationError, match="not active"):
        await project_service.update_project(db_session, project.id, language_id=inactive.id)


@pytest.mark.asyncio
async def test_list_project_user_access_returns_users(db_session) -> None:
    lang = await make_language(db_session, name="English", code="eng")
    project = await make_project(db_session, lang.id, name="Project")
    user1 = await make_user(db_session, email="ua1@example.com", display_name="User One")
    user2 = await make_user(db_session, email="ua2@example.com", display_name="User Two")
    await make_project_user_access(db_session, project.id, user1.id)
    await make_project_user_access(db_session, project.id, user2.id)
    results = await project_service.list_project_user_access(db_session, project.id)
    assert len(results) == 2
    access_obj, user_obj = results[0]
    assert access_obj.project_id == project.id
    assert user_obj.email in ("ua1@example.com", "ua2@example.com")


@pytest.mark.asyncio
async def test_list_project_user_access_returns_empty_when_none(db_session) -> None:
    lang = await make_language(db_session, name="English", code="eng")
    project = await make_project(db_session, lang.id, name="Empty Project")
    results = await project_service.list_project_user_access(db_session, project.id)
    assert results == []


@pytest.mark.asyncio
async def test_list_project_organization_access_returns_orgs(db_session) -> None:
    lang = await make_language(db_session, name="English", code="eng")
    project = await make_project(db_session, lang.id, name="Project")
    org1 = await make_organization(db_session, name="Org One", slug="org-one")
    org2 = await make_organization(db_session, name="Org Two", slug="org-two")
    await make_project_organization_access(db_session, project.id, org1.id)
    await make_project_organization_access(db_session, project.id, org2.id)
    results = await project_service.list_project_organization_access(db_session, project.id)
    assert len(results) == 2
    access_obj, org_obj = results[0]
    assert access_obj.project_id == project.id
    assert org_obj.slug in ("org-one", "org-two")


@pytest.mark.asyncio
async def test_list_project_organization_access_returns_empty_when_none(
    db_session,
) -> None:
    lang = await make_language(db_session, name="English", code="eng")
    project = await make_project(db_session, lang.id, name="Empty Project")
    results = await project_service.list_project_organization_access(db_session, project.id)
    assert results == []


@pytest.mark.asyncio
async def test_revoke_user_access_removes_grant(db_session) -> None:
    lang = await make_language(db_session, name="English", code="eng")
    project = await make_project(db_session, lang.id, name="Project")
    user = await make_user(db_session, email="revoke@example.com")
    await make_project_user_access(db_session, project.id, user.id)
    await project_service.revoke_user_access(db_session, project.id, user.id)
    results = await project_service.list_project_user_access(db_session, project.id)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_revoke_user_access_raises_not_found(db_session) -> None:
    lang = await make_language(db_session, name="English", code="eng")
    project = await make_project(db_session, lang.id, name="Project")
    user = await make_user(db_session, email="norv@example.com")
    with pytest.raises(NotFoundError, match="User access not found"):
        await project_service.revoke_user_access(db_session, project.id, user.id)


@pytest.mark.asyncio
async def test_revoke_organization_access_removes_grant(db_session) -> None:
    lang = await make_language(db_session, name="English", code="eng")
    project = await make_project(db_session, lang.id, name="Project")
    org = await make_organization(db_session, name="Org", slug="org-rev")
    await make_project_organization_access(db_session, project.id, org.id)
    await project_service.revoke_organization_access(db_session, project.id, org.id)
    results = await project_service.list_project_organization_access(db_session, project.id)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_revoke_organization_access_raises_not_found(db_session) -> None:
    lang = await make_language(db_session, name="English", code="eng")
    project = await make_project(db_session, lang.id, name="Project")
    org = await make_organization(db_session, name="Org", slug="org-norv")
    with pytest.raises(NotFoundError, match="Organization access not found"):
        await project_service.revoke_organization_access(db_session, project.id, org.id)
