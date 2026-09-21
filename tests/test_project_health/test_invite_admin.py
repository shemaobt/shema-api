from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError
from app.services.authorization.list_roles import list_roles
from app.services.project_health.invite_admin import invite_admin
from tests.baker import make_user


async def test_invite_admin_grants_role_to_existing_user(db_session, ph_app):
    inviter = await make_user(db_session, email="inviter@test.com")
    invitee = await make_user(db_session, email="newbie@test.com")

    result = await invite_admin(db_session, email="newbie@test.com", invited_by_user_id=inviter.id)

    assert result.granted is True
    assert result.pre_approved_role == "admin"
    roles = await list_roles(db_session, invitee.id, "project-health")
    assert ("project-health", "admin") in roles


async def test_invite_admin_is_idempotent(db_session, ph_app):
    inviter = await make_user(db_session, email="inviter@test.com")
    await make_user(db_session, email="newbie@test.com")

    first = await invite_admin(db_session, email="newbie@test.com", invited_by_user_id=inviter.id)
    second = await invite_admin(db_session, email="newbie@test.com", invited_by_user_id=inviter.id)
    assert first.access_request_id == second.access_request_id


async def test_invite_admin_rejects_unknown_email(db_session, ph_app):
    inviter = await make_user(db_session, email="inviter@test.com")
    with pytest.raises(NotFoundError):
        await invite_admin(db_session, email="ghost@test.com", invited_by_user_id=inviter.id)
