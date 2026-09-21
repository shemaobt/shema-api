import pytest

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.services import language_service
from tests.baker import make_language, make_project, make_user


@pytest.mark.asyncio
async def test_create_language(db_session) -> None:
    language = await language_service.create_language(db_session, name="Kokama", code="kos")
    assert language.name == "Kokama"
    assert language.code == "kos"


@pytest.mark.asyncio
async def test_create_language_lowercases_code(db_session) -> None:
    language = await language_service.create_language(db_session, name="Portuguese", code="POR")
    assert language.code == "por"


@pytest.mark.asyncio
async def test_create_language_raises_conflict_when_code_exists(db_session) -> None:
    await make_language(db_session, code="kos")
    with pytest.raises(ConflictError, match="code already exists"):
        await language_service.create_language(db_session, name="Other", code="kos")


@pytest.mark.asyncio
async def test_get_language_by_id(db_session) -> None:
    created = await make_language(db_session, name="Kokama", code="kos")
    language = await language_service.get_language_by_id(db_session, created.id)
    assert language is not None
    assert language.id == created.id
    assert language.code == "kos"


@pytest.mark.asyncio
async def test_get_language_by_id_returns_none_when_missing(db_session) -> None:
    language = await language_service.get_language_by_id(
        db_session, "00000000-0000-0000-0000-000000000000"
    )
    assert language is None


@pytest.mark.asyncio
async def test_get_language_by_code(db_session) -> None:
    await make_language(db_session, name="Kokama", code="kos")
    language = await language_service.get_language_by_code(db_session, "kos")
    assert language is not None
    assert language.code == "kos"


@pytest.mark.asyncio
async def test_get_language_by_code_returns_none_when_missing(db_session) -> None:
    language = await language_service.get_language_by_code(db_session, "xyz")
    assert language is None


@pytest.mark.asyncio
async def test_list_languages_ordered_by_code(db_session) -> None:
    manager = await make_user(db_session, email="manager@example.com")
    await make_language(db_session, code="zzz", name="Z")
    await make_language(db_session, code="aaa", name="A")
    languages = await language_service.list_languages(db_session, manager)
    assert len(languages) == 2
    assert languages[0].code == "aaa"
    assert languages[1].code == "zzz"


@pytest.mark.asyncio
async def test_create_language_sets_created_by(db_session) -> None:
    user = await make_user(db_session)
    language = await language_service.create_language(
        db_session, name="Kokama", code="kos", created_by=user.id
    )
    assert language.created_by == user.id


@pytest.mark.asyncio
async def test_deactivate_language_sets_inactive(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    created = await make_language(db_session, code="kos")
    deactivated = await language_service.deactivate_language(db_session, created.id, admin)
    assert deactivated.is_active is False


@pytest.mark.asyncio
async def test_deactivate_language_forbidden_for_creator(db_session) -> None:
    creator = await make_user(db_session)
    created = await make_language(db_session, code="kos", created_by=creator.id)
    with pytest.raises(AuthorizationError, match="Only platform admins"):
        await language_service.deactivate_language(db_session, created.id, creator)


@pytest.mark.asyncio
async def test_deactivate_language_forbidden_for_non_admin(db_session) -> None:
    creator = await make_user(db_session, email="creator@example.com")
    other = await make_user(db_session, email="other@example.com")
    created = await make_language(db_session, code="kos", created_by=creator.id)
    with pytest.raises(AuthorizationError, match="Only platform admins"):
        await language_service.deactivate_language(db_session, created.id, other)


@pytest.mark.asyncio
async def test_deactivate_language_allowed_when_in_use(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    created = await make_language(db_session, code="kos")
    project = await make_project(db_session, created.id, name="Genesis OBT")
    deactivated = await language_service.deactivate_language(db_session, created.id, admin)
    assert deactivated.is_active is False
    assert project.language_id == created.id


@pytest.mark.asyncio
async def test_deactivate_language_forbidden_for_creator_when_in_use(db_session) -> None:
    creator = await make_user(db_session, email="creator@example.com")
    created = await make_language(db_session, code="kos", created_by=creator.id)
    await make_project(db_session, created.id, name="Genesis OBT")
    with pytest.raises(AuthorizationError, match="Only platform admins"):
        await language_service.deactivate_language(db_session, created.id, creator)


@pytest.mark.asyncio
async def test_deactivate_language_missing_raises_not_found(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    with pytest.raises(NotFoundError, match=r"Language .* not found"):
        await language_service.deactivate_language(
            db_session, "00000000-0000-0000-0000-000000000000", admin
        )


@pytest.mark.asyncio
async def test_list_languages_hides_inactive_by_default(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    active = await make_language(db_session, code="act", name="Active")
    inactive = await make_language(db_session, code="ina", name="Inactive")
    await language_service.deactivate_language(db_session, inactive.id, admin)

    languages = await language_service.list_languages(db_session, admin)
    assert [lang.id for lang in languages] == [active.id]


@pytest.mark.asyncio
async def test_list_languages_include_inactive(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    active = await make_language(db_session, code="act", name="Active")
    inactive = await make_language(db_session, code="ina", name="Inactive")
    await language_service.deactivate_language(db_session, inactive.id, admin)

    languages = await language_service.list_languages(db_session, admin, include_inactive=True)
    assert {lang.id for lang in languages} == {active.id, inactive.id}


@pytest.mark.asyncio
async def test_list_languages_ignores_include_inactive_for_non_admin(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    manager = await make_user(db_session, email="manager@example.com")
    active = await make_language(db_session, code="act", name="Active")
    inactive = await make_language(db_session, code="ina", name="Inactive")
    await language_service.deactivate_language(db_session, inactive.id, admin)

    languages = await language_service.list_languages(db_session, manager, include_inactive=True)
    assert [lang.id for lang in languages] == [active.id]


@pytest.mark.asyncio
async def test_get_language_or_404_raises_when_missing(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Language .* not found"):
        await language_service.get_language_or_404(
            db_session, "00000000-0000-0000-0000-000000000000"
        )


@pytest.mark.asyncio
async def test_update_language_name_and_code(db_session) -> None:
    created = await make_language(db_session, name="Kokama", code="kos")
    updated = await language_service.update_language(
        db_session, created.id, name="Kokama Renamed", code="KOK"
    )
    assert updated.name == "Kokama Renamed"
    assert updated.code == "kok"


@pytest.mark.asyncio
async def test_update_language_partial_keeps_other_field(db_session) -> None:
    created = await make_language(db_session, name="Kokama", code="kos")
    updated = await language_service.update_language(db_session, created.id, name="Only Name")
    assert updated.name == "Only Name"
    assert updated.code == "kos"


@pytest.mark.asyncio
async def test_update_language_same_code_is_allowed(db_session) -> None:
    created = await make_language(db_session, name="Kokama", code="kos")
    updated = await language_service.update_language(db_session, created.id, code="kos")
    assert updated.code == "kos"


@pytest.mark.asyncio
async def test_update_language_conflicting_code_raises(db_session) -> None:
    await make_language(db_session, name="Other", code="oth")
    target = await make_language(db_session, name="Kokama", code="kos")
    with pytest.raises(ConflictError, match="code already exists"):
        await language_service.update_language(db_session, target.id, code="oth")


@pytest.mark.asyncio
async def test_update_language_missing_raises_not_found(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Language .* not found"):
        await language_service.update_language(
            db_session, "00000000-0000-0000-0000-000000000000", name="X"
        )


async def test_get_visible_language_hides_inactive_from_non_admin(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    manager = await make_user(db_session, email="manager@example.com")
    language = await make_language(db_session, code="kos")
    await language_service.deactivate_language(db_session, language.id, admin)

    with pytest.raises(NotFoundError, match=r"Language .* not found"):
        await language_service.get_visible_language_or_404(db_session, language.id, manager)


@pytest.mark.asyncio
async def test_get_visible_language_allows_admin_to_see_inactive(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    language = await make_language(db_session, code="kos")
    await language_service.deactivate_language(db_session, language.id, admin)

    found = await language_service.get_visible_language_or_404(db_session, language.id, admin)
    assert found.id == language.id
    assert found.is_active is False


@pytest.mark.asyncio
async def test_get_visible_language_returns_active_for_non_admin(db_session) -> None:
    manager = await make_user(db_session, email="manager@example.com")
    language = await make_language(db_session, code="kos")

    found = await language_service.get_visible_language_or_404(db_session, language.id, manager)
    assert found.id == language.id


@pytest.mark.asyncio
async def test_get_visible_language_by_code_hides_inactive_from_non_admin(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    manager = await make_user(db_session, email="manager@example.com")
    language = await make_language(db_session, code="kos")
    await language_service.deactivate_language(db_session, language.id, admin)

    with pytest.raises(NotFoundError, match="Language not found"):
        await language_service.get_visible_language_by_code_or_404(db_session, "kos", manager)


@pytest.mark.asyncio
async def test_get_visible_language_by_code_allows_admin_to_see_inactive(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    language = await make_language(db_session, code="kos")
    await language_service.deactivate_language(db_session, language.id, admin)

    found = await language_service.get_visible_language_by_code_or_404(db_session, "kos", admin)
    assert found.id == language.id


@pytest.mark.asyncio
async def test_get_visible_language_by_code_missing_raises_not_found(db_session) -> None:
    manager = await make_user(db_session, email="manager@example.com")
    with pytest.raises(NotFoundError, match="Language not found"):
        await language_service.get_visible_language_by_code_or_404(db_session, "zzz", manager)


@pytest.mark.asyncio
async def test_reactivate_language_sets_active(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    created = await make_language(db_session, code="kos")
    await language_service.deactivate_language(db_session, created.id, admin)

    reactivated = await language_service.reactivate_language(db_session, created.id, admin)
    assert reactivated.is_active is True


@pytest.mark.asyncio
async def test_reactivate_language_forbidden_for_non_admin(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    other = await make_user(db_session, email="other@example.com")
    created = await make_language(db_session, code="kos")
    await language_service.deactivate_language(db_session, created.id, admin)

    with pytest.raises(AuthorizationError, match="Only platform admins"):
        await language_service.reactivate_language(db_session, created.id, other)


@pytest.mark.asyncio
async def test_reactivate_language_missing_raises_not_found(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    with pytest.raises(NotFoundError, match=r"Language .* not found"):
        await language_service.reactivate_language(
            db_session, "00000000-0000-0000-0000-000000000000", admin
        )


@pytest.mark.asyncio
async def test_reactivate_language_restores_default_list_visibility(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    created = await make_language(db_session, code="kos")
    await language_service.deactivate_language(db_session, created.id, admin)
    assert await language_service.list_languages(db_session, admin) == []

    await language_service.reactivate_language(db_session, created.id, admin)
    languages = await language_service.list_languages(db_session, admin)
    assert [lang.id for lang in languages] == [created.id]


@pytest.mark.asyncio
async def test_reactivate_active_language_is_noop(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    created = await make_language(db_session, code="kos")

    reactivated = await language_service.reactivate_language(db_session, created.id, admin)
    assert reactivated.is_active is True


@pytest.mark.asyncio
async def test_list_active_languages_leaves_out_the_deactivated(db_session) -> None:
    """The public form never offers a language the platform retired."""
    admin = await make_user(db_session, email="admin-public@example.com", is_platform_admin=True)
    kept = await make_language(db_session, code="kos")
    retired = await make_language(db_session, code="ret")
    await language_service.deactivate_language(db_session, retired.id, admin)

    languages = await language_service.list_active_languages(db_session)

    assert [lng.code for lng in languages] == [kept.code]
