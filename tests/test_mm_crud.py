import pytest

from app.core.exceptions import NotFoundError
from app.services.meaning_map.add_feedback import add_feedback
from app.services.meaning_map.create_meaning_map import create_meaning_map
from app.services.meaning_map.create_pericope import create_pericope
from app.services.meaning_map.get_book_or_404 import get_book_or_404
from app.services.meaning_map.get_meaning_map_or_404 import get_meaning_map_or_404
from app.services.meaning_map.get_pericope_or_404 import get_pericope_or_404
from tests.baker import (
    SAMPLE_MM_DATA,
    make_bible_book,
    make_meaning_map,
    make_pericope,
    make_user,
)


async def test_create_pericope_success(db_session) -> None:
    book = await make_bible_book(db_session)
    pericope = await create_pericope(db_session, book.id, 1, 1, 1, 5, "Gen 1:1-5", title="Creation")
    assert pericope.id
    assert pericope.book_id == book.id
    assert pericope.reference == "Gen 1:1-5"
    assert pericope.title == "Creation"


async def test_create_meaning_map_success(db_session) -> None:
    user = await make_user(db_session, email="analyst@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await create_meaning_map(db_session, pericope.id, user.id, SAMPLE_MM_DATA)
    assert mm.id
    assert mm.pericope_id == pericope.id
    assert mm.analyst_id == user.id
    assert mm.status == "draft"
    assert mm.data == SAMPLE_MM_DATA


async def test_create_meaning_map_custom_status(db_session) -> None:
    user = await make_user(db_session, email="analyst2@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await create_meaning_map(db_session, pericope.id, user.id, {}, status="cross_check")
    assert mm.status == "cross_check"


async def test_add_feedback_success(db_session) -> None:
    user = await make_user(db_session, email="analyst3@test.com")
    reviewer = await make_user(db_session, email="reviewer@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    fb = await add_feedback(db_session, mm.id, "level_1.arc", reviewer.id, "Needs work")
    assert fb.id
    assert fb.meaning_map_id == mm.id
    assert fb.section_key == "level_1.arc"
    assert fb.author_id == reviewer.id
    assert fb.content == "Needs work"
    assert fb.resolved is False


async def test_create_pericope_without_title(db_session) -> None:
    book = await make_bible_book(db_session)
    pericope = await create_pericope(db_session, book.id, 2, 1, 2, 10, "Gen 2:1-10")
    assert pericope.title is None


async def test_get_book_or_404_success(db_session) -> None:
    book = await make_bible_book(db_session)
    found = await get_book_or_404(db_session, book.id)
    assert found.id == book.id
    assert found.name == "Genesis"


async def test_get_book_or_404_raises(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Bible book .* not found"):
        await get_book_or_404(db_session, "nonexistent-id")


async def test_get_pericope_or_404_success(db_session) -> None:
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    found = await get_pericope_or_404(db_session, pericope.id)
    assert found.id == pericope.id


async def test_get_pericope_or_404_raises(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Pericope .* not found"):
        await get_pericope_or_404(db_session, "nonexistent-id")


async def test_get_meaning_map_or_404_success(db_session) -> None:
    user = await make_user(db_session, email="analyst4@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    found = await get_meaning_map_or_404(db_session, mm.id)
    assert found.id == mm.id


async def test_get_meaning_map_or_404_raises(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Meaning map .* not found"):
        await get_meaning_map_or_404(db_session, "nonexistent-id")
