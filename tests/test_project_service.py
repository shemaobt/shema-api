from datetime import UTC, datetime

import pytest

from app.core.exceptions import NotFoundError
from app.db.models.project import ProjectUserAccess
from app.models.oc_project import OCProjectListResponse
from app.models.project import ProjectUpdate
from app.services import phase_service, project_service
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


async def _grant_access_at(db_session, project_id, user_id, granted_at) -> ProjectUserAccess:
    access = ProjectUserAccess(project_id=project_id, user_id=user_id, granted_at=granted_at)
    db_session.add(access)
    await db_session.commit()
    await db_session.refresh(access)
    return access


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


@pytest.mark.asyncio
async def test_serialize_project_responses_with_phases_and_members(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    rich = await make_project(db_session, language_id=lang.id, name="Rich")
    bare = await make_project(db_session, language_id=lang.id, name="Bare")
    phase1 = await make_phase(db_session, name="Drafting")
    phase2 = await make_phase(db_session, name="Checking")
    phase3 = await make_phase(db_session, name="Publishing")
    await make_project_phase(db_session, rich.id, phase1.id)
    await make_project_phase(db_session, rich.id, phase2.id)
    await make_project_phase(db_session, rich.id, phase3.id)
    await phase_service.update_project_phase_status(db_session, rich.id, phase1.id, "completed")
    await phase_service.update_project_phase_status(db_session, rich.id, phase2.id, "in_progress")
    user1 = await make_user(db_session, email="sp1@example.com", display_name="Member One")
    user2 = await make_user(db_session, email="sp2@example.com", display_name="Member Two")
    await _grant_access_at(
        db_session, rich.id, user1.id, datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)
    )
    await _grant_access_at(
        db_session, rich.id, user2.id, datetime(2026, 7, 1, 12, 0, 1, tzinfo=UTC)
    )
    responses = await project_service.serialize_projects(db_session, [rich, bare])
    by_id = {r.id: r for r in responses}
    assert by_id[rich.id].phases_completed == 1
    assert by_id[rich.id].phases_total == 3
    assert [m.user_id for m in by_id[rich.id].members_preview] == [user1.id, user2.id]
    assert by_id[rich.id].members_preview[0].display_name == "Member One"
    assert by_id[bare.id].phases_completed == 0
    assert by_id[bare.id].phases_total == 0
    assert by_id[bare.id].members_preview == []


@pytest.mark.asyncio
async def test_serialize_project_response_detail(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id, name="Detail")
    phase = await make_phase(db_session, name="Drafting")
    await make_project_phase(db_session, project.id, phase.id)
    await phase_service.update_project_phase_status(db_session, project.id, phase.id, "completed")
    user = await make_user(db_session, email="detail@example.com", display_name="Detail User")
    await _grant_access_at(
        db_session, project.id, user.id, datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)
    )
    response = await project_service.serialize_project(db_session, project)
    assert response.id == project.id
    assert response.phases_completed == 1
    assert response.phases_total == 1
    assert len(response.members_preview) == 1
    assert response.members_preview[0].user_id == user.id
    assert response.members_preview[0].display_name == "Detail User"
    assert response.members_preview[0].avatar_url is None
    assert response.image_url is None


@pytest.mark.asyncio
async def test_serialize_members_preview_capped_at_four_ordered_by_granted_at(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id, name="Crowded")
    users = [
        await make_user(db_session, email=f"cap{i}@example.com", display_name=f"Member {i}")
        for i in range(6)
    ]
    for i, user in enumerate(reversed(users)):
        await _grant_access_at(
            db_session,
            project.id,
            user.id,
            datetime(2026, 7, 1, 12, 0, 5 - i, tzinfo=UTC),
        )
    response = await project_service.serialize_project(db_session, project)
    assert [m.user_id for m in response.members_preview] == [u.id for u in users[:4]]


@pytest.mark.asyncio
async def test_serialize_members_preview_capped_per_project_not_globally(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    first = await make_project(db_session, language_id=lang.id, name="Crowded A")
    second = await make_project(db_session, language_id=lang.id, name="Crowded B")
    sparse = await make_project(db_session, language_id=lang.id, name="Sparse")
    first_users = [
        await make_user(db_session, email=f"multia{i}@example.com", display_name=f"A {i}")
        for i in range(5)
    ]
    second_users = [
        await make_user(db_session, email=f"multib{i}@example.com", display_name=f"B {i}")
        for i in range(5)
    ]
    sparse_user = await make_user(db_session, email="multic@example.com", display_name="C")
    for i in range(5):
        await _grant_access_at(
            db_session,
            first.id,
            first_users[i].id,
            datetime(2026, 7, 1, 12, 0, i * 2, tzinfo=UTC),
        )
        await _grant_access_at(
            db_session,
            second.id,
            second_users[i].id,
            datetime(2026, 7, 1, 12, 0, i * 2 + 1, tzinfo=UTC),
        )
    await _grant_access_at(
        db_session, sparse.id, sparse_user.id, datetime(2026, 7, 1, 12, 0, 30, tzinfo=UTC)
    )
    responses = await project_service.serialize_projects(db_session, [first, second, sparse])
    by_id = {r.id: r for r in responses}
    assert [m.user_id for m in by_id[first.id].members_preview] == [u.id for u in first_users[:4]]
    assert [m.user_id for m in by_id[second.id].members_preview] == [u.id for u in second_users[:4]]
    assert [m.user_id for m in by_id[sparse.id].members_preview] == [sparse_user.id]


def test_oc_project_list_response_excludes_console_only_fields() -> None:
    fields = set(OCProjectListResponse.model_fields)
    assert "phases_completed" not in fields
    assert "phases_total" not in fields
    assert "members_preview" not in fields
    assert "image_url" in fields
    assert "member_count" in fields


@pytest.mark.asyncio
async def test_update_project_sets_image_url(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id, name="Image")
    updated = await project_service.update_project(
        db_session, project.id, image_url="https://example.com/cover.png"
    )
    assert updated.image_url == "https://example.com/cover.png"
    assert updated.name == "Image"


@pytest.mark.asyncio
async def test_update_project_clears_image_url(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id, name="Image")
    await project_service.update_project(
        db_session, project.id, image_url="https://example.com/cover.png"
    )
    payload = ProjectUpdate.model_validate({"image_url": None})
    updated = await project_service.update_project(
        db_session, project.id, **payload.model_dump(exclude_unset=True)
    )
    assert updated.image_url is None


@pytest.mark.asyncio
async def test_update_project_keeps_image_url_when_not_provided(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id, name="Image")
    await project_service.update_project(
        db_session, project.id, image_url="https://example.com/cover.png"
    )
    payload = ProjectUpdate.model_validate({"name": "Renamed"})
    updated = await project_service.update_project(
        db_session, project.id, **payload.model_dump(exclude_unset=True)
    )
    assert updated.name == "Renamed"
    assert updated.image_url == "https://example.com/cover.png"
