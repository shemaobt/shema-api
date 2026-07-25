import pytest

from app.core.exceptions import AuthorizationError, NotFoundError
from app.services import project_service
from tests.baker import (
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)


async def _project(db):
    lang = await make_language(db, code="prj")
    return await make_project(db, language_id=lang.id)


@pytest.mark.asyncio
async def test_is_project_manager(db_session) -> None:
    project = await _project(db_session)
    manager = await make_user(db_session, email="m@example.com")
    member = await make_user(db_session, email="u@example.com")
    await make_project_user_access(db_session, project.id, manager.id, role="manager")
    await make_project_user_access(db_session, project.id, member.id, role="member")

    assert await project_service.is_project_manager(db_session, manager.id, project.id) is True
    assert await project_service.is_project_manager(db_session, member.id, project.id) is False


@pytest.mark.asyncio
async def test_grant_access_allows_admin_and_manager(db_session) -> None:
    project = await _project(db_session)
    admin = await make_user(db_session, email="a@example.com", is_platform_admin=True)
    manager = await make_user(db_session, email="m@example.com")
    await make_project_user_access(db_session, project.id, manager.id, role="manager")

    await project_service.assert_can_grant_access(db_session, admin, project.id)
    await project_service.assert_can_grant_access(db_session, manager, project.id)


@pytest.mark.asyncio
async def test_grant_access_forbidden_for_member(db_session) -> None:
    project = await _project(db_session)
    member = await make_user(db_session, email="u@example.com")
    await make_project_user_access(db_session, project.id, member.id, role="member")

    with pytest.raises(AuthorizationError, match="manager of this project"):
        await project_service.assert_can_grant_access(db_session, member, project.id)


@pytest.mark.asyncio
async def test_manager_can_modify_a_member(db_session) -> None:
    project = await _project(db_session)
    manager = await make_user(db_session, email="m@example.com")
    member = await make_user(db_session, email="u@example.com")
    await make_project_user_access(db_session, project.id, manager.id, role="manager")
    await make_project_user_access(db_session, project.id, member.id, role="member")

    await project_service.assert_can_modify_member_role(db_session, manager, project.id, member.id)


@pytest.mark.asyncio
async def test_manager_cannot_modify_another_manager(db_session) -> None:
    project = await _project(db_session)
    manager = await make_user(db_session, email="m@example.com")
    other_manager = await make_user(db_session, email="m2@example.com")
    await make_project_user_access(db_session, project.id, manager.id, role="manager")
    await make_project_user_access(db_session, project.id, other_manager.id, role="manager")

    with pytest.raises(AuthorizationError, match="another manager"):
        await project_service.assert_can_modify_member_role(
            db_session, manager, project.id, other_manager.id
        )


@pytest.mark.asyncio
async def test_admin_can_modify_a_manager(db_session) -> None:
    project = await _project(db_session)
    admin = await make_user(db_session, email="a@example.com", is_platform_admin=True)
    manager = await make_user(db_session, email="m@example.com")
    await make_project_user_access(db_session, project.id, manager.id, role="manager")

    await project_service.assert_can_modify_member_role(db_session, admin, project.id, manager.id)


@pytest.mark.asyncio
async def test_non_manager_cannot_modify_roles(db_session) -> None:
    project = await _project(db_session)
    member = await make_user(db_session, email="u@example.com")
    target = await make_user(db_session, email="t@example.com")
    await make_project_user_access(db_session, project.id, member.id, role="member")
    await make_project_user_access(db_session, project.id, target.id, role="member")

    with pytest.raises(AuthorizationError, match="manager of this project"):
        await project_service.assert_can_modify_member_role(
            db_session, member, project.id, target.id
        )


@pytest.mark.asyncio
async def test_modify_missing_target_raises_not_found(db_session) -> None:
    project = await _project(db_session)
    manager = await make_user(db_session, email="m@example.com")
    ghost = await make_user(db_session, email="g@example.com")
    await make_project_user_access(db_session, project.id, manager.id, role="manager")

    with pytest.raises(NotFoundError, match="access not found"):
        await project_service.assert_can_modify_member_role(
            db_session, manager, project.id, ghost.id
        )
