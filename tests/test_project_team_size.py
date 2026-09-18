import pytest

from app.services import project_service
from tests.baker import (
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)


@pytest.mark.asyncio
async def test_count_team_sizes_counts_distinct_users(db_session) -> None:
    lang = await make_language(db_session, code="tsa")
    project = await make_project(db_session, language_id=lang.id)
    u1 = await make_user(db_session, email="a@example.com")
    u2 = await make_user(db_session, email="b@example.com")
    await make_project_user_access(db_session, project.id, u1.id)
    await make_project_user_access(db_session, project.id, u2.id)

    sizes = await project_service.count_project_team_sizes(db_session, [project.id])
    assert sizes == {project.id: 2}


@pytest.mark.asyncio
async def test_count_team_sizes_zero_for_project_without_access(db_session) -> None:
    lang = await make_language(db_session, code="tsb")
    project = await make_project(db_session, language_id=lang.id)

    sizes = await project_service.count_project_team_sizes(db_session, [project.id])
    assert sizes == {project.id: 0}


@pytest.mark.asyncio
async def test_count_team_sizes_isolates_projects(db_session) -> None:
    lang = await make_language(db_session, code="tsc")
    p1 = await make_project(db_session, language_id=lang.id, name="P1")
    p2 = await make_project(db_session, language_id=lang.id, name="P2")
    u1 = await make_user(db_session, email="c@example.com")
    u2 = await make_user(db_session, email="d@example.com")
    await make_project_user_access(db_session, p1.id, u1.id)
    await make_project_user_access(db_session, p1.id, u2.id)
    await make_project_user_access(db_session, p2.id, u1.id)

    sizes = await project_service.count_project_team_sizes(db_session, [p1.id, p2.id])
    assert sizes == {p1.id: 2, p2.id: 1}


@pytest.mark.asyncio
async def test_count_team_sizes_empty_input(db_session) -> None:
    assert await project_service.count_project_team_sizes(db_session, []) == {}


@pytest.mark.asyncio
async def test_count_team_sizes_excludes_platform_admins(db_session) -> None:
    lang = await make_language(db_session, code="tsp")
    project = await make_project(db_session, language_id=lang.id)
    member = await make_user(db_session, email="member@example.com")
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    await make_project_user_access(db_session, project.id, member.id)
    await make_project_user_access(db_session, project.id, admin.id)

    sizes = await project_service.count_project_team_sizes(db_session, [project.id])
    assert sizes == {project.id: 1}


@pytest.mark.asyncio
async def test_members_preview_excludes_platform_admins(db_session) -> None:
    lang = await make_language(db_session, code="tsq")
    project = await make_project(db_session, language_id=lang.id)
    member = await make_user(db_session, email="member@example.com", display_name="Member One")
    admin = await make_user(
        db_session,
        email="admin@example.com",
        display_name="Admin One",
        is_platform_admin=True,
    )
    await make_project_user_access(db_session, project.id, member.id)
    await make_project_user_access(db_session, project.id, admin.id)

    (response,) = await project_service.serialize_projects(db_session, [project])
    assert response.team_size == 1
    assert [m.user_id for m in response.members_preview] == [member.id]
