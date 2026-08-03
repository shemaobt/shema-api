import pytest

from app.core.org_scope import get_managed_org_ids
from tests.baker import make_organization, make_organization_member, make_user


@pytest.mark.asyncio
async def test_returns_empty_when_user_manages_nothing(db_session) -> None:
    user = await make_user(db_session, email="nobody@example.com")
    result = await get_managed_org_ids(db_session, user.id)
    assert result == []


@pytest.mark.asyncio
async def test_returns_orgs_via_member_role(db_session) -> None:
    user = await make_user(db_session, email="mgr-member@example.com")
    org_a = await make_organization(db_session, slug="role-a")
    org_b = await make_organization(db_session, slug="role-b")
    await make_organization_member(db_session, user.id, org_a.id, role="manager")
    await make_organization_member(db_session, user.id, org_b.id, role="member")

    result = await get_managed_org_ids(db_session, user.id)
    assert result == [org_a.id]


@pytest.mark.asyncio
async def test_returns_orgs_via_manager_id(db_session) -> None:
    user = await make_user(db_session, email="mgr-owner@example.com")
    org = await make_organization(db_session, slug="owned", manager_id=user.id)

    result = await get_managed_org_ids(db_session, user.id)
    assert result == [org.id]


@pytest.mark.asyncio
async def test_deduplicates_when_both_paths_match(db_session) -> None:
    user = await make_user(db_session, email="both@example.com")
    org = await make_organization(db_session, slug="both-paths", manager_id=user.id)
    await make_organization_member(db_session, user.id, org.id, role="manager")

    result = await get_managed_org_ids(db_session, user.id)
    assert result == [org.id]


@pytest.mark.asyncio
async def test_combines_both_sources_without_overlap(db_session) -> None:
    user = await make_user(db_session, email="combo@example.com")
    org_via_role = await make_organization(db_session, slug="via-role")
    org_via_owner = await make_organization(db_session, slug="via-owner", manager_id=user.id)
    await make_organization_member(db_session, user.id, org_via_role.id, role="manager")

    result = await get_managed_org_ids(db_session, user.id)
    assert sorted(result) == sorted([org_via_role.id, org_via_owner.id])


@pytest.mark.asyncio
async def test_does_not_include_other_users_orgs(db_session) -> None:
    user_a = await make_user(db_session, email="a@example.com")
    user_b = await make_user(db_session, email="b@example.com")
    org = await make_organization(db_session, slug="only-b", manager_id=user_b.id)
    await make_organization_member(db_session, user_b.id, org.id, role="manager")

    result = await get_managed_org_ids(db_session, user_a.id)
    assert result == []
