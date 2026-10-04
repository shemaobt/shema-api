import pytest

from app.core.exceptions import NotFoundError
from app.services import organization_service
from tests.baker import make_organization, make_organization_member, make_user


async def test_promote_member_to_manager(db_session) -> None:
    org = await make_organization(db_session, slug="role-org-1")
    user = await make_user(db_session, email="promote@example.com")
    await make_organization_member(db_session, user.id, org.id, role="member")
    updated = await organization_service.update_member_role(db_session, org.id, user.id, "manager")
    assert updated.role == "manager"


async def test_demote_manager_to_member(db_session) -> None:
    org = await make_organization(db_session, slug="role-org-2")
    user = await make_user(db_session, email="demote@example.com")
    await make_organization_member(db_session, user.id, org.id, role="manager")
    updated = await organization_service.update_member_role(db_session, org.id, user.id, "member")
    assert updated.role == "member"


async def test_update_role_member_not_found(db_session) -> None:
    org = await make_organization(db_session, slug="role-org-3")
    user = await make_user(db_session, email="ghost@example.com")
    with pytest.raises(NotFoundError, match="Member not found"):
        await organization_service.update_member_role(db_session, org.id, user.id, "manager")


async def test_update_role_idempotent(db_session) -> None:
    org = await make_organization(db_session, slug="role-org-4")
    user = await make_user(db_session, email="same@example.com")
    await make_organization_member(db_session, user.id, org.id, role="manager")
    updated = await organization_service.update_member_role(db_session, org.id, user.id, "manager")
    assert updated.role == "manager"
