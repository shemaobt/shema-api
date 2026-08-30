import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.services import language_service
from tests.baker import make_language


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
    await make_language(db_session, code="zzz", name="Z")
    await make_language(db_session, code="aaa", name="A")
    languages = await language_service.list_languages(db_session)
    assert len(languages) == 2
    assert languages[0].code == "aaa"
    assert languages[1].code == "zzz"


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
