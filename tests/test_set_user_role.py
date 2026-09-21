import pytest
from sqlalchemy import select

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.db.models.project import ProjectUserAccess
from app.services import user_service
from tests.baker import make_language, make_project, make_project_user_access, make_user


async def _access_rows(db_session, user_id: str) -> dict[str, str]:
    stmt = select(ProjectUserAccess).where(ProjectUserAccess.user_id == user_id)
    result = await db_session.execute(stmt)
    return {access.project_id: access.role for access in result.scalars()}


@pytest.mark.asyncio
async def test_set_user_role_promotes_to_platform_admin(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    target = await make_user(db_session, email="target@example.com")
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await make_project_user_access(db_session, project.id, target.id, role="member")

    updated = await user_service.set_user_role(db_session, target.id, admin, "platform_admin")

    assert updated.role == "platform_admin"
    assert updated.is_platform_admin is True
    assert await _access_rows(db_session, target.id) == {project.id: "member"}


@pytest.mark.asyncio
async def test_set_user_role_manager_with_project_ids_upserts_access(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    target = await make_user(db_session, email="target@example.com")
    lang = await make_language(db_session)
    existing_project = await make_project(db_session, lang.id, name="Existing")
    new_project = await make_project(db_session, lang.id, name="New")
    await make_project_user_access(db_session, existing_project.id, target.id, role="member")

    updated = await user_service.set_user_role(
        db_session,
        target.id,
        admin,
        "manager",
        project_ids=[existing_project.id, new_project.id],
    )

    assert updated.role == "manager"
    assert updated.is_platform_admin is False
    assert await _access_rows(db_session, target.id) == {
        existing_project.id: "manager",
        new_project.id: "manager",
    }
    count_stmt = select(ProjectUserAccess).where(ProjectUserAccess.user_id == target.id)
    rows = list((await db_session.execute(count_stmt)).scalars())
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_set_user_role_manager_deduplicates_repeated_project_ids(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    target = await make_user(db_session, email="target@example.com")
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)

    updated = await user_service.set_user_role(
        db_session,
        target.id,
        admin,
        "manager",
        project_ids=[project.id, project.id],
    )

    assert updated.role == "manager"
    rows_stmt = select(ProjectUserAccess).where(ProjectUserAccess.user_id == target.id)
    rows = list((await db_session.execute(rows_stmt)).scalars())
    assert len(rows) == 1
    assert rows[0].role == "manager"


@pytest.mark.asyncio
async def test_set_user_role_manager_without_project_ids_keeps_existing(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    target = await make_user(db_session, email="target@example.com", is_platform_admin=True)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await make_project_user_access(db_session, project.id, target.id, role="manager")

    updated = await user_service.set_user_role(db_session, target.id, admin, "manager")

    assert updated.role == "manager"
    assert updated.is_platform_admin is False
    assert await _access_rows(db_session, target.id) == {project.id: "manager"}


@pytest.mark.asyncio
async def test_set_user_role_manager_without_project_ids_requires_managed_project(
    db_session,
) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    target = await make_user(db_session, email="target@example.com")

    with pytest.raises(
        ValidationError,
        match="project_ids is required when promoting a user who manages no projects",
    ):
        await user_service.set_user_role(db_session, target.id, admin, "manager")


@pytest.mark.asyncio
async def test_set_user_role_demotes_manager_access_to_member(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    target = await make_user(db_session, email="target@example.com", is_platform_admin=True)
    other = await make_user(db_session, email="other@example.com")
    lang = await make_language(db_session)
    managed = await make_project(db_session, lang.id, name="Managed")
    joined = await make_project(db_session, lang.id, name="Joined")
    await make_project_user_access(db_session, managed.id, target.id, role="manager")
    await make_project_user_access(db_session, joined.id, target.id, role="member")
    await make_project_user_access(db_session, managed.id, other.id, role="manager")

    updated = await user_service.set_user_role(db_session, target.id, admin, "member")

    assert updated.role == "member"
    assert updated.is_platform_admin is False
    assert await _access_rows(db_session, target.id) == {
        managed.id: "member",
        joined.id: "member",
    }
    assert await _access_rows(db_session, other.id) == {managed.id: "manager"}


@pytest.mark.asyncio
async def test_set_user_role_user_not_found(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)

    with pytest.raises(NotFoundError, match=r"User .* not found"):
        await user_service.set_user_role(
            db_session, "00000000-0000-0000-0000-000000000000", admin, "manager"
        )


@pytest.mark.asyncio
async def test_set_user_role_project_not_found(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    target = await make_user(db_session, email="target@example.com")

    with pytest.raises(NotFoundError, match=r"Project .* not found"):
        await user_service.set_user_role(
            db_session,
            target.id,
            admin,
            "manager",
            project_ids=["00000000-0000-0000-0000-000000000000"],
        )


@pytest.mark.asyncio
async def test_set_user_role_rejects_self_change(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)

    with pytest.raises(AuthorizationError):
        await user_service.set_user_role(db_session, admin.id, admin, "member")
