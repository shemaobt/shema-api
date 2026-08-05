import pytest
from pydantic import ValidationError

from app.core.exceptions import ConflictError, NotFoundError
from app.models.app import AppCreate, AppUpdate
from app.services import app_service
from tests.baker import make_app, make_role, make_user, make_user_app_role


@pytest.mark.asyncio
async def test_list_apps(db_session) -> None:
    await make_app(db_session, app_key="alpha-app", name="Alpha App")
    await make_app(db_session, app_key="beta-app", name="Beta App")
    apps = await app_service.list_apps(db_session)
    keys = [a.app_key for a in apps]
    assert "alpha-app" in keys
    assert "beta-app" in keys

    assert "meaning-map-generator" in keys


@pytest.mark.asyncio
async def test_create_app_with_all_fields(db_session) -> None:
    app = await app_service.create_app(
        db_session,
        app_key="full-app",
        name="Full App",
        description="A full-featured app",
        icon_url="https://example.com/icon.png",
        app_url="https://example.com",
        ios_url="https://apps.apple.com/app",
        android_url="https://play.google.com/app",
        platforms=["web", "android", "ios"],
        is_active=True,
    )
    assert app.app_key == "full-app"
    assert app.name == "Full App"
    assert app.description == "A full-featured app"
    assert app.icon_url == "https://example.com/icon.png"
    assert app.app_url == "https://example.com"
    assert app.ios_url == "https://apps.apple.com/app"
    assert app.android_url == "https://play.google.com/app"
    assert app.platforms == ["web", "android", "ios"]
    assert app.is_active is True
    assert app.id is not None


@pytest.mark.asyncio
async def test_create_app_defaults_platforms_to_web(db_session) -> None:
    app = await app_service.create_app(db_session, app_key="def-app", name="Default App")
    assert app.platforms == ["web"]


def test_app_platforms_reject_empty() -> None:
    with pytest.raises(ValidationError):
        AppCreate(app_key="x", name="X", platforms=[])
    with pytest.raises(ValidationError):
        AppUpdate(platforms=[])


def test_app_platforms_reject_duplicates() -> None:
    with pytest.raises(ValidationError):
        AppCreate(app_key="x", name="X", platforms=["web", "web"])
    with pytest.raises(ValidationError):
        AppUpdate(platforms=["ios", "ios"])


@pytest.mark.asyncio
async def test_update_app_platforms(db_session) -> None:
    created = await make_app(db_session, app_key="plat-app", name="Plat App")
    updated = await app_service.update_app(db_session, created.id, platforms=["android", "ios"])
    assert updated.platforms == ["android", "ios"]


@pytest.mark.asyncio
async def test_create_app_raises_conflict_on_duplicate_key(db_session) -> None:
    await make_app(db_session, app_key="dup-app", name="First")
    with pytest.raises(ConflictError, match="already exists"):
        await app_service.create_app(db_session, app_key="dup-app", name="Second")


@pytest.mark.asyncio
async def test_get_app_or_404(db_session) -> None:
    created = await make_app(db_session, app_key="findme-app", name="Find Me")
    app = await app_service.get_app_or_404(db_session, created.id)
    assert app.id == created.id
    assert app.app_key == "findme-app"


@pytest.mark.asyncio
async def test_get_app_or_404_raises_not_found(db_session) -> None:
    with pytest.raises(NotFoundError, match="not found"):
        await app_service.get_app_or_404(db_session, "00000000-0000-0000-0000-000000000000")


@pytest.mark.asyncio
async def test_update_app_name_and_description(db_session) -> None:
    created = await make_app(db_session, app_key="upd-app", name="Old Name")
    updated = await app_service.update_app(
        db_session, created.id, name="New Name", description="New desc"
    )
    assert updated.name == "New Name"
    assert updated.description == "New desc"


@pytest.mark.asyncio
async def test_update_app_raises_not_found(db_session) -> None:
    with pytest.raises(NotFoundError, match="not found"):
        await app_service.update_app(db_session, "00000000-0000-0000-0000-000000000000", name="X")


@pytest.mark.asyncio
async def test_list_user_apps_returns_apps_with_roles(db_session) -> None:
    user = await make_user(db_session, email="appuser@example.com")
    app = await make_app(db_session, app_key="user-app", name="User App")
    role_admin = await make_role(db_session, app.id, role_key="admin", label="Admin")
    role_member = await make_role(db_session, app.id, role_key="member", label="Member")
    await make_user_app_role(db_session, user.id, app.id, role_admin.id)
    await make_user_app_role(db_session, user.id, app.id, role_member.id)

    results = await app_service.list_user_apps(db_session, user.id)
    assert len(results) == 1
    result_app, role_keys = results[0]
    assert result_app.app_key == "user-app"
    assert sorted(role_keys) == ["admin", "member"]


@pytest.mark.asyncio
async def test_list_user_apps_returns_empty_for_no_roles(db_session) -> None:
    user = await make_user(db_session, email="noroleapp@example.com")
    results = await app_service.list_user_apps(db_session, user.id)
    assert results == []


@pytest.mark.asyncio
async def test_list_app_roles(db_session) -> None:
    app = await make_app(db_session, app_key="roles-app", name="Roles App")
    await make_role(db_session, app.id, role_key="admin", label="Admin")
    await make_role(db_session, app.id, role_key="editor", label="Editor")
    roles = await app_service.list_app_roles(db_session, app.id)
    role_keys = [r.role_key for r in roles]
    assert "admin" in role_keys
    assert "editor" in role_keys
    assert len(role_keys) == 2
