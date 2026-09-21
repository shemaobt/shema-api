import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.services import organization_service
from tests.baker import make_organization, make_organization_member, make_user


async def test_create_organization(db_session) -> None:
    org = await organization_service.create_organization(
        db_session, name="Acme Corp", slug="acme-corp"
    )
    assert org.name == "Acme Corp"
    assert org.slug == "acme-corp"


async def test_create_organization_lowercases_slug(db_session) -> None:
    org = await organization_service.create_organization(db_session, name="Test", slug="UPPER-SLUG")
    assert org.slug == "upper-slug"


async def test_create_organization_raises_conflict_when_slug_exists(db_session) -> None:
    await make_organization(db_session, slug="taken")
    with pytest.raises(ConflictError, match="slug already exists"):
        await organization_service.create_organization(db_session, name="Other", slug="taken")


async def test_get_organization_by_id(db_session) -> None:
    created = await make_organization(db_session, slug="my-org")
    org = await organization_service.get_organization_by_id(db_session, created.id)
    assert org is not None
    assert org.id == created.id


async def test_get_organization_by_slug(db_session) -> None:
    await make_organization(db_session, slug="find-me")
    org = await organization_service.get_organization_by_slug(db_session, "find-me")
    assert org is not None
    assert org.slug == "find-me"


async def test_get_organization_or_404_raises_when_missing(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Organization .* not found"):
        await organization_service.get_organization_or_404(
            db_session, "00000000-0000-0000-0000-000000000000"
        )


async def test_add_member(db_session) -> None:
    user = await make_user(db_session, email="member@example.com")
    org = await make_organization(db_session, slug="org1")
    member = await organization_service.add_member(db_session, org.id, user.id, role="member")
    assert member.user_id == user.id
    assert member.organization_id == org.id
    assert member.role == "member"


async def test_add_member_raises_conflict_when_already_member(db_session) -> None:
    user = await make_user(db_session, email="dup@example.com")
    org = await make_organization(db_session, slug="org2")
    await make_organization_member(db_session, user.id, org.id)
    with pytest.raises(ConflictError, match="already a member"):
        await organization_service.add_member(db_session, org.id, user.id)


async def test_is_member_true(db_session) -> None:
    user = await make_user(db_session, email="in@example.com")
    org = await make_organization(db_session, slug="org3")
    await make_organization_member(db_session, user.id, org.id)
    result = await organization_service.is_member(db_session, user.id, org.id)
    assert result is True


async def test_is_member_false(db_session) -> None:
    user = await make_user(db_session, email="out@example.com")
    org = await make_organization(db_session, slug="org4")
    result = await organization_service.is_member(db_session, user.id, org.id)
    assert result is False


async def test_update_organization_name(db_session) -> None:
    org = await make_organization(db_session, name="Old Name", slug="upd-name")
    updated = await organization_service.update_organization(db_session, org.id, name="New Name")
    assert updated.name == "New Name"
    assert updated.slug == "upd-name"


async def test_update_organization_slug(db_session) -> None:
    org = await make_organization(db_session, name="Org", slug="old-slug")
    updated = await organization_service.update_organization(db_session, org.id, slug="new-slug")
    assert updated.slug == "new-slug"
    assert updated.name == "Org"


async def test_update_organization_raises_not_found(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Organization .* not found"):
        await organization_service.update_organization(
            db_session, "00000000-0000-0000-0000-000000000000", name="X"
        )


async def test_update_organization_raises_conflict_for_duplicate_slug(db_session) -> None:
    await make_organization(db_session, slug="taken-slug")
    org = await make_organization(db_session, slug="my-slug")
    with pytest.raises(ConflictError, match="slug already exists"):
        await organization_service.update_organization(db_session, org.id, slug="taken-slug")


async def test_list_members_returns_members_with_user_info(db_session) -> None:
    org = await make_organization(db_session, slug="org-members")
    user1 = await make_user(db_session, email="m1@example.com", display_name="User One")
    user2 = await make_user(db_session, email="m2@example.com", display_name="User Two")
    await make_organization_member(db_session, user1.id, org.id, role="admin")
    await make_organization_member(db_session, user2.id, org.id, role="member")
    members = await organization_service.list_members(db_session, org.id)
    assert len(members) == 2
    member_obj, user_obj = members[0]
    assert user_obj.email in ("m1@example.com", "m2@example.com")
    assert member_obj.organization_id == org.id


async def test_list_members_returns_empty_for_no_members(db_session) -> None:
    org = await make_organization(db_session, slug="org-empty")
    members = await organization_service.list_members(db_session, org.id)
    assert members == []


async def test_remove_member_success(db_session) -> None:
    org = await make_organization(db_session, slug="org-rm")
    user = await make_user(db_session, email="rm@example.com")
    await make_organization_member(db_session, user.id, org.id)
    await organization_service.remove_member(db_session, org.id, user.id)
    members = await organization_service.list_members(db_session, org.id)
    assert len(members) == 0


async def test_remove_member_raises_not_found(db_session) -> None:
    org = await make_organization(db_session, slug="org-rm2")
    user = await make_user(db_session, email="notrm@example.com")
    with pytest.raises(NotFoundError, match="Member not found"):
        await organization_service.remove_member(db_session, org.id, user.id)
