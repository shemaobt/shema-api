from datetime import UTC, datetime

import pytest

from app.core.exceptions import RoleError
from app.services import authorization_service
from tests.baker import make_app, make_role, make_user, make_user_app_role


async def test_has_role_true_when_assignment_exists(db_session) -> None:
    user = await make_user(db_session, email="has-role@example.com")
    app = await make_app(db_session, app_key="my-app")
    role = await make_role(db_session, app.id, role_key="admin")
    await make_user_app_role(db_session, user.id, app.id, role.id, granted_by=user.id)
    result = await authorization_service.has_role(db_session, user.id, "my-app", "admin")
    assert result is True


async def test_has_role_false_when_no_assignment(db_session) -> None:
    user = await make_user(db_session, email="no-role@example.com")
    app = await make_app(db_session, app_key="other-app")
    await make_role(db_session, app.id, role_key="admin")
    result = await authorization_service.has_role(db_session, user.id, "other-app", "admin")
    assert result is False


async def test_has_role_false_when_app_missing(db_session) -> None:
    user = await make_user(db_session, email="user@example.com")
    result = await authorization_service.has_role(db_session, user.id, "nonexistent-app", "admin")
    assert result is False


async def test_assert_can_manage_roles_passes_for_platform_admin(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    await authorization_service.assert_can_manage_roles(db_session, admin, "any-app")


async def test_assert_can_manage_roles_passes_for_app_admin(db_session) -> None:
    user = await make_user(db_session, email="app-admin@example.com")
    app = await make_app(db_session, app_key="studio")
    role = await make_role(db_session, app.id, role_key="admin")
    await make_user_app_role(db_session, user.id, app.id, role.id)
    await authorization_service.assert_can_manage_roles(db_session, user, "studio")


async def test_assert_can_manage_roles_raises_for_regular_user(db_session) -> None:
    user = await make_user(db_session, email="regular@example.com")
    app = await make_app(db_session, app_key="studio")
    await make_role(db_session, app.id, role_key="member")
    with pytest.raises(RoleError, match="cannot manage roles"):
        await authorization_service.assert_can_manage_roles(db_session, user, "studio")


async def test_assign_role_creates_assignment(db_session) -> None:
    actor = await make_user(db_session, email="actor@example.com")
    target = await make_user(db_session, email="target@example.com")
    app = await make_app(db_session, app_key="tripod-studio")
    admin_role = await make_role(db_session, app.id, role_key="admin")
    member_role = await make_role(db_session, app.id, role_key="member")
    await make_user_app_role(db_session, actor.id, app.id, admin_role.id)

    assignment = await authorization_service.assign_role(
        db_session, actor, target.id, "tripod-studio", "member"
    )
    assert assignment.user_id == target.id
    assert assignment.app_id == app.id
    assert assignment.role_id == member_role.id
    assert assignment.revoked_at is None


async def test_assign_role_returns_existing_when_already_assigned(db_session) -> None:
    actor = await make_user(db_session, email="actor2@example.com")
    target = await make_user(db_session, email="target2@example.com")
    app = await make_app(db_session, app_key="tripod-studio")
    admin_role = await make_role(db_session, app.id, role_key="admin")
    member_role = await make_role(db_session, app.id, role_key="member")
    await make_user_app_role(db_session, actor.id, app.id, admin_role.id)
    existing = await make_user_app_role(
        db_session, target.id, app.id, member_role.id, granted_by=actor.id
    )

    assignment = await authorization_service.assign_role(
        db_session, actor, target.id, "tripod-studio", "member"
    )
    assert assignment.id == existing.id


async def test_assign_role_raises_when_app_not_found(db_session) -> None:
    actor = await make_user(db_session, email="actor3@example.com", is_platform_admin=True)
    target = await make_user(db_session, email="target3@example.com")

    with pytest.raises(RoleError, match="App not found"):
        await authorization_service.assign_role(db_session, actor, target.id, "fake-app", "member")


async def test_revoke_role_sets_revoked_at(db_session) -> None:
    actor = await make_user(db_session, email="revoker@example.com")
    target = await make_user(db_session, email="revoked@example.com")
    app = await make_app(db_session, app_key="tripod-studio")
    admin_role = await make_role(db_session, app.id, role_key="admin")
    member_role = await make_role(db_session, app.id, role_key="member")
    await make_user_app_role(db_session, actor.id, app.id, admin_role.id)
    await make_user_app_role(db_session, target.id, app.id, member_role.id, granted_by=actor.id)

    assignment = await authorization_service.revoke_role(
        db_session, actor, target.id, "tripod-studio", "member"
    )
    assert assignment.revoked_at is not None


async def test_revoke_role_raises_when_no_active_assignment(db_session) -> None:
    actor = await make_user(db_session, email="revoker2@example.com")
    target = await make_user(db_session, email="no-assignment@example.com")
    app = await make_app(db_session, app_key="tripod-studio")
    admin_role = await make_role(db_session, app.id, role_key="admin")
    await make_role(db_session, app.id, role_key="member")
    await make_user_app_role(db_session, actor.id, app.id, admin_role.id)

    with pytest.raises(RoleError, match="Active assignment not found"):
        await authorization_service.revoke_role(
            db_session, actor, target.id, "tripod-studio", "member"
        )


async def test_list_roles_returns_assigned_roles(db_session) -> None:
    user = await make_user(db_session, email="list-roles@example.com")
    app1 = await make_app(db_session, app_key="app-one")
    app2 = await make_app(db_session, app_key="app-two")
    role1 = await make_role(db_session, app1.id, role_key="admin")
    role2 = await make_role(db_session, app2.id, role_key="member")
    await make_user_app_role(db_session, user.id, app1.id, role1.id)
    await make_user_app_role(db_session, user.id, app2.id, role2.id)

    all_roles = await authorization_service.list_roles(db_session, user.id)
    assert set(all_roles) == {("app-one", "admin"), ("app-two", "member")}

    filtered = await authorization_service.list_roles(db_session, user.id, app_key="app-one")
    assert filtered == [("app-one", "admin")]


async def test_list_roles_excludes_revoked(db_session) -> None:
    user = await make_user(db_session, email="revoked-list@example.com")
    app = await make_app(db_session, app_key="app-revoked")
    role = await make_role(db_session, app.id, role_key="member")
    await make_user_app_role(db_session, user.id, app.id, role.id, revoked_at=datetime.now(UTC))

    roles = await authorization_service.list_roles(db_session, user.id)
    assert roles == []


async def _member_setup(db_session, suffix: str):
    actor = await make_user(db_session, email=f"revoker-{suffix}@example.com")
    target = await make_user(db_session, email=f"target-{suffix}@example.com")
    app = await make_app(db_session, app_key=f"app-{suffix}")
    admin_role = await make_role(db_session, app.id, role_key="admin")
    member_role = await make_role(db_session, app.id, role_key="member")
    await make_user_app_role(db_session, actor.id, app.id, admin_role.id)
    return actor, target, app, member_role


@pytest.mark.asyncio
async def test_revoke_role_records_who_revoked(db_session) -> None:
    """A revocation has an author — what the Shemá Admin's history reads it by (OBT-543)."""
    actor, target, app, member_role = await _member_setup(db_session, "who")
    await make_user_app_role(db_session, target.id, app.id, member_role.id, granted_by=actor.id)

    assignment = await authorization_service.revoke_role(
        db_session, actor, target.id, app.app_key, "member"
    )

    assert assignment.revoked_by == actor.id


@pytest.mark.asyncio
async def test_revoke_role_revokes_every_live_duplicate(db_session) -> None:
    """Two live rows of one grant — two requests that landed together — used to be a 500 here,
    and revoking one of them would have left the role held."""
    actor, target, app, member_role = await _member_setup(db_session, "dup")
    await make_user_app_role(db_session, target.id, app.id, member_role.id)
    await make_user_app_role(db_session, target.id, app.id, member_role.id)

    await authorization_service.revoke_role(db_session, actor, target.id, app.app_key, "member")

    assert await authorization_service.list_roles(db_session, target.id, app.app_key) == []


@pytest.mark.asyncio
async def test_assign_and_revoke_leave_the_transaction_to_the_caller_when_asked(
    db_session,
) -> None:
    """``commit=False`` writes nothing a rollback cannot take back — the seam that lets the
    Shemá Admin write one role in two apps, or a role and its regions, as one commit."""
    actor, target, app, _member_role = await _member_setup(db_session, "tx")
    key, target_id = app.app_key, target.id

    await authorization_service.assign_role(
        db_session, actor, target_id, key, "member", commit=False
    )
    assert await authorization_service.list_roles(db_session, target_id, key) == [(key, "member")]
    await db_session.rollback()
    assert await authorization_service.list_roles(db_session, target_id, key) == []
    await db_session.refresh(actor)

    await authorization_service.assign_role(db_session, actor, target_id, key, "member")
    await authorization_service.revoke_role(
        db_session, actor, target_id, key, "member", commit=False
    )
    assert await authorization_service.list_roles(db_session, target_id, key) == []
    await db_session.rollback()
    assert await authorization_service.list_roles(db_session, target_id, key) == [(key, "member")]
