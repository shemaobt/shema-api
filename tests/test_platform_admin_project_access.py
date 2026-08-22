import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.services import project_service
from tests.baker import (
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)


@pytest.mark.asyncio
async def test_grant_user_access_rejects_platform_admin(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id)

    with pytest.raises(ValidationError, match="Platform admins cannot be added"):
        await project_service.grant_user_access(db_session, project.id, admin.id)


@pytest.mark.asyncio
async def test_grant_user_access_rejects_unknown_user(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id)

    with pytest.raises(NotFoundError, match=r"User .* not found"):
        await project_service.grant_user_access(
            db_session, project.id, "00000000-0000-0000-0000-000000000000"
        )


@pytest.mark.asyncio
async def test_update_user_access_role_rejects_platform_admin(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id)

    with pytest.raises(ValidationError, match="Platform admins cannot receive a project role"):
        await project_service.update_user_access_role(db_session, project.id, admin.id, "manager")


@pytest.mark.asyncio
async def test_update_user_access_role_rejects_unknown_user(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id)

    with pytest.raises(NotFoundError, match=r"User .* not found"):
        await project_service.update_user_access_role(
            db_session, project.id, "00000000-0000-0000-0000-000000000000", "manager"
        )


@pytest.mark.asyncio
async def test_list_project_user_access_excludes_platform_admins(db_session) -> None:
    lang = await make_language(db_session, code="kos")
    project = await make_project(db_session, language_id=lang.id)
    member = await make_user(db_session, email="member@example.com")
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    await make_project_user_access(db_session, project.id, member.id)
    await make_project_user_access(db_session, project.id, admin.id)

    results = await project_service.list_project_user_access(db_session, project.id)

    assert len(results) == 1
    _, user_obj = results[0]
    assert user_obj.id == member.id


@pytest.mark.asyncio
async def test_create_project_admin_creator_gets_no_membership(db_session) -> None:
    from sqlalchemy import select

    from app.db.models.project import ProjectUserAccess

    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    lang = await make_language(db_session, code="kos")
    project = await project_service.create_project(
        db_session,
        name="Admin Project",
        language_id=lang.id,
        creator_user_id=str(admin.id),
    )

    stmt = select(ProjectUserAccess).where(ProjectUserAccess.project_id == project.id)
    rows = list((await db_session.execute(stmt)).scalars())
    assert rows == []
