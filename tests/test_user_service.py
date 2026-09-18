import pytest

from app.core.exceptions import NotFoundError
from app.services import user_service
from tests.baker import make_app, make_role, make_user, make_user_app_role


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
    created = await make_user(db_session, email="toggle@example.com", is_active=True)
    assert created.is_active is True
    updated = await user_service.update_user(db_session, created.id, is_active=False)
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_update_user_toggles_is_platform_admin(db_session) -> None:
    created = await make_user(db_session, email="admin@example.com", is_platform_admin=False)
    assert created.is_platform_admin is False
    updated = await user_service.update_user(db_session, created.id, is_platform_admin=True)
    assert updated.is_platform_admin is True


@pytest.mark.asyncio
async def test_update_user_clears_avatar_when_explicitly_null(db_session) -> None:
    created = await make_user(db_session, email="clearnull@example.com")
    await user_service.update_user(db_session, created.id, avatar_url="https://x/a.png")

    updated = await user_service.update_user(db_session, created.id, avatar_url=None)

    assert updated.avatar_url is None


@pytest.mark.asyncio
async def test_update_user_clears_avatar_when_empty_string(db_session) -> None:
    created = await make_user(db_session, email="clearempty@example.com")
    await user_service.update_user(db_session, created.id, avatar_url="https://x/a.png")

    updated = await user_service.update_user(db_session, created.id, avatar_url="")

    assert updated.avatar_url is None


@pytest.mark.asyncio
async def test_update_user_keeps_avatar_when_field_is_omitted(db_session) -> None:
    created = await make_user(db_session, email="keepavatar@example.com")
    await user_service.update_user(db_session, created.id, avatar_url="https://x/a.png")

    updated = await user_service.update_user(db_session, created.id, is_active=False)

    assert updated.avatar_url == "https://x/a.png"
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_update_user_raises_not_found(db_session) -> None:
    with pytest.raises(NotFoundError, match="not found"):
        await user_service.update_user(
            db_session, "00000000-0000-0000-0000-000000000000", is_active=False
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
