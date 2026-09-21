import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.services import language_service
from tests.baker import make_language


async def test_create_language(db_session) -> None:
    language = await language_service.create_language(db_session, name="Kokama", code="kos")
    assert language.name == "Kokama"
    assert language.code == "kos"


async def test_create_language_lowercases_code(db_session) -> None:
    language = await language_service.create_language(db_session, name="Portuguese", code="POR")
    assert language.code == "por"


async def test_create_language_raises_conflict_when_code_exists(db_session) -> None:
    await make_language(db_session, code="kos")
    with pytest.raises(ConflictError, match="code already exists"):
        await language_service.create_language(db_session, name="Other", code="kos")


async def test_get_language_by_id(db_session) -> None:
    created = await make_language(db_session, name="Kokama", code="kos")
    language = await language_service.get_language_by_id(db_session, created.id)
    assert language is not None
    assert language.id == created.id
    assert language.code == "kos"


async def test_get_language_by_id_returns_none_when_missing(db_session) -> None:
    language = await language_service.get_language_by_id(
        db_session, "00000000-0000-0000-0000-000000000000"
    )
    assert language is None


async def test_get_language_by_code(db_session) -> None:
    await make_language(db_session, name="Kokama", code="kos")
    language = await language_service.get_language_by_code(db_session, "kos")
    assert language is not None
    assert language.code == "kos"


async def test_get_language_by_code_returns_none_when_missing(db_session) -> None:
    language = await language_service.get_language_by_code(db_session, "xyz")
    assert language is None


async def test_list_languages_ordered_by_code(db_session) -> None:
    await make_language(db_session, code="zzz", name="Z")
    await make_language(db_session, code="aaa", name="A")
    languages = await language_service.list_languages(db_session)
    assert len(languages) == 2
    assert languages[0].code == "aaa"
    assert languages[1].code == "zzz"


async def test_get_language_or_404_raises_when_missing(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Language .* not found"):
        await language_service.get_language_or_404(
            db_session, "00000000-0000-0000-0000-000000000000"
        )
