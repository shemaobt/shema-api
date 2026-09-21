import pytest

from app.services.book_context.add_feedback import add_feedback
from app.services.book_context.list_bcds import list_bcds
from app.services.book_context.list_feedback import list_feedback
from app.services.book_context.resolve_feedback import resolve_feedback
from tests.baker import make_bcd, make_bible_book, make_user


async def test_list_bcds_returns_all(db_session):
    user = await make_user(db_session, email="api1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, version=1)
    await make_bcd(db_session, book.id, user.id, version=2)

    items = await list_bcds(db_session)
    assert len(items) == 2


async def test_list_bcds_filter_by_book(db_session):
    user = await make_user(db_session, email="api2@test.com")
    book1 = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    book2 = await make_bible_book(
        db_session,
        name="Esther",
        abbreviation="Est",
        order=17,
        chapter_count=10,
    )
    await make_bcd(db_session, book1.id, user.id)
    await make_bcd(db_session, book2.id, user.id)

    items = await list_bcds(db_session, book_id=book1.id)
    assert len(items) == 1
    assert items[0].book_id == book1.id


async def test_add_feedback_creates_entry(db_session):
    user = await make_user(db_session, email="api3@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    fb = await add_feedback(db_session, bcd.id, "participant_register", user.id, "Missing Boaz")
    assert fb.section_key == "participant_register"
    assert fb.content == "Missing Boaz"
    assert fb.resolved is False


async def test_list_feedback_returns_ordered(db_session):
    user = await make_user(db_session, email="api4@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)
    await add_feedback(db_session, bcd.id, "places", user.id, "First")
    await add_feedback(db_session, bcd.id, "objects", user.id, "Second")

    items = await list_feedback(db_session, bcd.id)
    assert len(items) == 2
    assert items[0].content == "First"


async def test_resolve_feedback_marks_resolved(db_session):
    user = await make_user(db_session, email="api5@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)
    fb = await add_feedback(db_session, bcd.id, "discourse_threads", user.id, "Fix thread")

    resolved = await resolve_feedback(db_session, bcd.id, fb.id)
    assert resolved.resolved is True


async def test_resolve_feedback_raises_not_found(db_session):
    user = await make_user(db_session, email="api6@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    from app.core.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        await resolve_feedback(db_session, bcd.id, "nonexistent-id")
