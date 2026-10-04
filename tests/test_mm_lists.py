import pytest

from app.core.exceptions import NotFoundError
from app.services.meaning_map.get_chapter_summaries import get_chapter_summaries
from app.services.meaning_map.get_map_with_book import get_map_with_book
from app.services.meaning_map.get_pericope_with_book import get_pericope_with_book
from app.services.meaning_map.list_books import list_books
from app.services.meaning_map.list_feedback import list_feedback
from app.services.meaning_map.list_meaning_maps import list_meaning_maps
from app.services.meaning_map.list_pericopes import list_pericopes
from tests.baker import (
    make_bible_book,
    make_meaning_map,
    make_meaning_map_feedback,
    make_pericope,
    make_user,
)


async def test_list_books_empty(db_session) -> None:
    result = await list_books(db_session)
    assert result == []


async def test_list_books_ordered(db_session) -> None:
    await make_bible_book(db_session, name="Exodus", abbreviation="Exod", order=2)
    await make_bible_book(db_session, name="Genesis", abbreviation="Gen", order=1)
    result = await list_books(db_session)
    assert len(result) == 2
    assert result[0].name == "Genesis"
    assert result[1].name == "Exodus"


async def test_list_meaning_maps_no_filters(db_session) -> None:
    user = await make_user(db_session, email="analyst5@test.com")
    book = await make_bible_book(db_session)
    p1 = await make_pericope(db_session, book.id, reference="Gen 1:1-5")
    p2 = await make_pericope(db_session, book.id, chapter_start=2, reference="Gen 2:1-5")
    await make_meaning_map(db_session, p1.id, user.id)
    await make_meaning_map(db_session, p2.id, user.id)
    result = await list_meaning_maps(db_session)
    assert len(result) == 2


async def test_list_meaning_maps_filter_by_book(db_session) -> None:
    user = await make_user(db_session, email="analyst6@test.com")
    book1 = await make_bible_book(db_session, name="Genesis", abbreviation="Gen", order=1)
    book2 = await make_bible_book(db_session, name="Exodus", abbreviation="Exod", order=2)
    p1 = await make_pericope(db_session, book1.id, reference="Gen 1:1-5")
    p2 = await make_pericope(db_session, book2.id, reference="Exod 1:1-5")
    await make_meaning_map(db_session, p1.id, user.id)
    await make_meaning_map(db_session, p2.id, user.id)
    result = await list_meaning_maps(db_session, book_id=book1.id)
    assert len(result) == 1


async def test_list_meaning_maps_filter_by_chapter(db_session) -> None:
    user = await make_user(db_session, email="analyst7@test.com")
    book = await make_bible_book(db_session)
    p1 = await make_pericope(db_session, book.id, chapter_start=1, reference="Gen 1:1-5")
    p2 = await make_pericope(db_session, book.id, chapter_start=3, reference="Gen 3:1-5")
    await make_meaning_map(db_session, p1.id, user.id)
    await make_meaning_map(db_session, p2.id, user.id)
    result = await list_meaning_maps(db_session, chapter=1)
    assert len(result) == 1


async def test_list_meaning_maps_filter_by_status(db_session) -> None:
    user = await make_user(db_session, email="analyst8@test.com")
    book = await make_bible_book(db_session)
    p1 = await make_pericope(db_session, book.id, reference="Gen 1:1-5")
    p2 = await make_pericope(db_session, book.id, chapter_start=2, reference="Gen 2:1-5")
    await make_meaning_map(db_session, p1.id, user.id, status="draft")
    await make_meaning_map(db_session, p2.id, user.id, status="cross_check")
    result = await list_meaning_maps(db_session, status="draft")
    assert len(result) == 1
    assert result[0].status == "draft"


async def test_list_meaning_maps_empty(db_session) -> None:
    result = await list_meaning_maps(db_session)
    assert result == []


async def test_list_feedback_returns_ordered(db_session) -> None:
    user = await make_user(db_session, email="analyst9@test.com")
    reviewer = await make_user(db_session, email="reviewer2@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    await make_meaning_map_feedback(
        db_session, mm.id, reviewer.id, section_key="level_1.arc", content="First"
    )
    await make_meaning_map_feedback(
        db_session, mm.id, reviewer.id, section_key="level_2", content="Second"
    )
    result = await list_feedback(db_session, mm.id)
    assert len(result) == 2
    assert result[0].content == "First"
    assert result[1].content == "Second"


async def test_list_feedback_empty(db_session) -> None:
    user = await make_user(db_session, email="analyst10@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    result = await list_feedback(db_session, mm.id)
    assert result == []


async def test_list_pericopes_returns_all_for_book(db_session) -> None:
    book = await make_bible_book(db_session)
    await make_pericope(db_session, book.id, chapter_start=1, reference="Gen 1:1-5")
    await make_pericope(db_session, book.id, chapter_start=2, reference="Gen 2:1-5")
    result = await list_pericopes(db_session, book.id)
    assert len(result) == 2


async def test_list_pericopes_filter_by_chapter(db_session) -> None:
    book = await make_bible_book(db_session)
    await make_pericope(db_session, book.id, chapter_start=1, chapter_end=1, reference="Gen 1:1-5")
    await make_pericope(db_session, book.id, chapter_start=3, chapter_end=3, reference="Gen 3:1-5")
    result = await list_pericopes(db_session, book.id, chapter=1)
    assert len(result) == 1
    assert result[0].reference == "Gen 1:1-5"


async def test_list_pericopes_includes_meaning_map_info(db_session) -> None:
    user = await make_user(db_session, email="analyst12@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id, reference="Gen 1:1-5")
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    result = await list_pericopes(db_session, book.id)
    assert len(result) == 1
    assert result[0].meaning_map_id == mm.id
    assert result[0].status == "draft"


async def test_list_pericopes_without_meaning_map(db_session) -> None:
    book = await make_bible_book(db_session)
    await make_pericope(db_session, book.id, reference="Gen 1:1-5")
    result = await list_pericopes(db_session, book.id)
    assert len(result) == 1
    assert result[0].meaning_map_id is None


async def test_get_chapter_summaries_empty(db_session) -> None:
    book = await make_bible_book(db_session)
    result = await get_chapter_summaries(db_session, book.id)
    assert result == []


async def test_get_chapter_summaries_counts_statuses(db_session) -> None:
    user = await make_user(db_session, email="analyst40@test.com")
    book = await make_bible_book(db_session)
    p1 = await make_pericope(
        db_session, book.id, chapter_start=1, chapter_end=1, reference="Gen 1:1-5"
    )
    p2 = await make_pericope(
        db_session, book.id, chapter_start=1, chapter_end=1, reference="Gen 1:6-10"
    )
    await make_meaning_map(db_session, p1.id, user.id, status="draft")
    await make_meaning_map(db_session, p2.id, user.id, status="cross_check")
    result = await get_chapter_summaries(db_session, book.id)
    assert len(result) == 1
    assert result[0].chapter == 1
    assert result[0].pericope_count == 2
    assert result[0].draft_count == 1
    assert result[0].cross_check_count == 1
    assert result[0].approved_count == 0


async def test_get_chapter_summaries_multi_chapter_pericope(db_session) -> None:
    user = await make_user(db_session, email="analyst41@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(
        db_session, book.id, chapter_start=1, chapter_end=2, reference="Gen 1:1-2:3"
    )
    await make_meaning_map(db_session, pericope.id, user.id, status="draft")
    result = await get_chapter_summaries(db_session, book.id)
    assert len(result) == 2
    assert result[0].chapter == 1
    assert result[0].pericope_count == 1
    assert result[1].chapter == 2
    assert result[1].pericope_count == 1


async def test_get_chapter_summaries_pericope_without_map(db_session) -> None:
    book = await make_bible_book(db_session)
    await make_pericope(db_session, book.id, chapter_start=1, chapter_end=1, reference="Gen 1:1-5")
    result = await get_chapter_summaries(db_session, book.id)
    assert len(result) == 1
    assert result[0].pericope_count == 1
    assert result[0].draft_count == 0


async def test_get_chapter_summaries_approved_count(db_session) -> None:
    user = await make_user(db_session, email="analyst42@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(
        db_session, book.id, chapter_start=5, chapter_end=5, reference="Gen 5:1-10"
    )
    await make_meaning_map(db_session, pericope.id, user.id, status="approved")
    result = await get_chapter_summaries(db_session, book.id)
    assert len(result) == 1
    assert result[0].chapter == 5
    assert result[0].approved_count == 1


async def test_get_map_with_book_success(db_session) -> None:
    user = await make_user(db_session, email="join1@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    found_mm, found_book = await get_map_with_book(db_session, mm.id)
    assert found_mm.id == mm.id
    assert found_book.id == book.id
    assert found_book.name == "Genesis"


async def test_get_map_with_book_raises_not_found(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Meaning map .* not found"):
        await get_map_with_book(db_session, "nonexistent-id")


async def test_get_pericope_with_book_success(db_session) -> None:
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    found_pericope, found_book = await get_pericope_with_book(db_session, pericope.id)
    assert found_pericope.id == pericope.id
    assert found_book.id == book.id
    assert found_book.name == "Genesis"


async def test_get_pericope_with_book_raises_not_found(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Pericope .* not found"):
        await get_pericope_with_book(db_session, "nonexistent-id")
