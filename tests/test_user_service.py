import pytest

from app.core.exceptions import AuthorizationError, NotFoundError
from app.services import user_service
from tests.baker import (
    make_app,
    make_language,
    make_project,
    make_project_user_access,
    make_role,
    make_user,
    make_user_app_role,
)


@pytest.mark.asyncio
async def test_list_users(db_session) -> None:
    await make_user(db_session, email="alice@example.com", display_name="Alice")
    await make_user(db_session, email="bob@example.com", display_name="Bob")
    users = await user_service.list_users(db_session)
    emails = [u.email for u in users]
    assert "alice@example.com" in emails
    assert "bob@example.com" in emails


@pytest.mark.asyncio
async def test_get_user_by_id(db_session) -> None:
    created = await make_user(db_session, email="findme@example.com")
    user = await user_service.get_user_by_id(db_session, created.id)
    assert user.id == created.id
    assert user.email == "findme@example.com"


@pytest.mark.asyncio
async def test_get_user_by_id_raises_not_found(db_session) -> None:
    with pytest.raises(NotFoundError, match="not found"):
        await user_service.get_user_by_id(db_session, "00000000-0000-0000-0000-000000000000")


@pytest.mark.asyncio
async def test_update_user_toggles_is_active(db_session) -> None:
    admin = await make_user(db_session, email="acting@example.com", is_platform_admin=True)
    created = await make_user(db_session, email="toggle@example.com", is_active=True)
    assert created.is_active is True
    updated = await user_service.update_user(db_session, created.id, admin, is_active=False)
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_update_user_toggles_is_platform_admin(db_session) -> None:
    admin = await make_user(db_session, email="acting@example.com", is_platform_admin=True)
    created = await make_user(db_session, email="admin@example.com", is_platform_admin=False)
    assert created.is_platform_admin is False
    updated = await user_service.update_user(db_session, created.id, admin, is_platform_admin=True)
    assert updated.is_platform_admin is True


@pytest.mark.asyncio
async def test_update_user_rejects_self_admin_flag_change(db_session) -> None:
    admin = await make_user(db_session, email="acting@example.com", is_platform_admin=True)

    with pytest.raises(AuthorizationError):
        await user_service.update_user(db_session, admin.id, admin, is_platform_admin=False)

    await db_session.refresh(admin)
    assert admin.is_platform_admin is True


@pytest.mark.asyncio
async def test_update_user_rejects_self_deactivation(db_session) -> None:
    admin = await make_user(db_session, email="acting@example.com", is_platform_admin=True)

    with pytest.raises(AuthorizationError):
        await user_service.update_user(db_session, admin.id, admin, is_active=False)

    await db_session.refresh(admin)
    assert admin.is_active is True


@pytest.mark.asyncio
async def test_update_user_allows_self_profile_fields(db_session) -> None:
    admin = await make_user(db_session, email="acting@example.com", is_platform_admin=True)

    updated = await user_service.update_user(
        db_session, admin.id, admin, avatar_url="https://example.com/a.png", locale="pt-BR"
    )

    assert updated.avatar_url == "https://example.com/a.png"
    assert updated.locale == "pt-BR"


@pytest.mark.asyncio
async def test_update_user_raises_not_found(db_session) -> None:
    admin = await make_user(db_session, email="acting@example.com", is_platform_admin=True)
    with pytest.raises(NotFoundError, match="not found"):
        await user_service.update_user(
            db_session, "00000000-0000-0000-0000-000000000000", admin, is_active=False
        )


@pytest.mark.asyncio
async def test_list_user_roles_returns_roles(db_session) -> None:
    user = await make_user(db_session, email="roled@example.com")
    app = await make_app(db_session, app_key="my-app", name="My App")
    role = await make_role(db_session, app.id, role_key="admin", label="Admin")
    await make_user_app_role(db_session, user.id, app.id, role.id)
    roles = await user_service.list_user_roles(db_session, user.id)
    assert len(roles) == 1
    app_key, role_key, granted_at = roles[0]
    assert app_key == "my-app"
    assert role_key == "admin"
    assert granted_at is not None


@pytest.mark.asyncio
async def test_list_user_roles_returns_empty_for_no_roles(db_session) -> None:
    user = await make_user(db_session, email="noroles@example.com")
    roles = await user_service.list_user_roles(db_session, user.id)
    assert roles == []


async def _derive_role(db_session, user) -> str:
    manager_ids = await user_service.get_manager_user_ids(db_session, [user.id])
    return user_service.build_user_list_response(user, is_manager=user.id in manager_ids).role


@pytest.mark.asyncio
async def test_derived_role_member_without_access(db_session) -> None:
    user = await make_user(db_session, email="plain@example.com")
    assert await _derive_role(db_session, user) == "member"


@pytest.mark.asyncio
async def test_derived_role_member_with_non_manager_access(db_session) -> None:
    user = await make_user(db_session, email="member-access@example.com")
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await make_project_user_access(db_session, project.id, user.id, role="member")
    assert await _derive_role(db_session, user) == "member"


@pytest.mark.asyncio
async def test_derived_role_manager_with_manager_access(db_session) -> None:
    user = await make_user(db_session, email="manages@example.com")
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await make_project_user_access(db_session, project.id, user.id, role="manager")
    assert await _derive_role(db_session, user) == "manager"


@pytest.mark.asyncio
async def test_derived_role_platform_admin_prevails_over_manager(db_session) -> None:
    user = await make_user(db_session, email="admin-manager@example.com", is_platform_admin=True)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await make_project_user_access(db_session, project.id, user.id, role="manager")
    assert await _derive_role(db_session, user) == "platform_admin"


@pytest.mark.asyncio
async def test_list_users_derives_mixed_roles(db_session) -> None:
    member = await make_user(db_session, email="mix-member@example.com")
    manager = await make_user(db_session, email="mix-manager@example.com")
    admin = await make_user(db_session, email="mix-admin@example.com", is_platform_admin=True)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await make_project_user_access(db_session, project.id, manager.id, role="manager")

    users = await user_service.list_users(db_session)
    manager_ids = await user_service.get_manager_user_ids(db_session, [u.id for u in users])
    roles = {
        u.email: user_service.build_user_list_response(u, is_manager=u.id in manager_ids).role
        for u in users
    }
    assert roles[member.email] == "member"
    assert roles[manager.email] == "manager"
    assert roles[admin.email] == "platform_admin"
