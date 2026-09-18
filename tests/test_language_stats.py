import pytest

from app.core.exceptions import NotFoundError
from app.models.language import LanguageProjectRef
from app.services import language_service
from tests.baker import make_language, make_project


@pytest.mark.asyncio
async def test_language_stats_lists_projects(db_session) -> None:
    lang = await make_language(db_session, code="ksa")
    other = await make_language(db_session, code="oth")
    p1 = await make_project(db_session, language_id=lang.id, name="P1")
    p2 = await make_project(db_session, language_id=lang.id, name="P2")
    await make_project(db_session, language_id=other.id, name="P3")

    stats = await language_service.get_language_stats(db_session, lang.id)
    assert stats.language_id == lang.id
    assert stats.project_count == 2
    assert stats.projects == [
        LanguageProjectRef(id=p1.id, name=p1.name),
        LanguageProjectRef(id=p2.id, name=p2.name),
    ]


@pytest.mark.asyncio
async def test_language_stats_empty_when_unused(db_session) -> None:
    lang = await make_language(db_session, code="ksb")
    stats = await language_service.get_language_stats(db_session, lang.id)
    assert stats.project_count == 0
    assert stats.projects == []


@pytest.mark.asyncio
async def test_language_stats_missing_raises_not_found(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Language .* not found"):
        await language_service.get_language_stats(
            db_session, "00000000-0000-0000-0000-000000000000"
        )
