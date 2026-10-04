import pytest

from app.core.exceptions import AuthorizationError, ConflictError
from app.services.book_context.lock_bcd import lock_bcd
from app.services.book_context.unlock_bcd import unlock_bcd
from app.services.book_context.update_section import update_section
from tests.baker import make_bcd, make_bible_book, make_user


async def test_lock_draft_bcd(db_session):
    user = await make_user(db_session, email="lock1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    result = await lock_bcd(db_session, bcd, user.id)

    assert result.locked_by == user.id
    assert result.locked_at is not None


async def test_lock_allows_review_status(db_session):
    user = await make_user(db_session, email="lock2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="review")

    result = await lock_bcd(db_session, bcd, user.id)
    assert result.locked_by == user.id


async def test_lock_rejects_approved_status(db_session):
    user = await make_user(db_session, email="lock2b@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth2",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="approved")

    with pytest.raises(ConflictError, match="draft or review status"):
        await lock_bcd(db_session, bcd, user.id)


async def test_lock_rejects_if_locked_by_other(db_session):
    user1 = await make_user(db_session, email="lock3a@test.com")
    user2 = await make_user(db_session, email="lock3b@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user1.id)

    await lock_bcd(db_session, bcd, user1.id)

    with pytest.raises(ConflictError, match="already locked"):
        await lock_bcd(db_session, bcd, user2.id)


async def test_lock_allows_relock_by_same_user(db_session):
    user = await make_user(db_session, email="lock4@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    await lock_bcd(db_session, bcd, user.id)
    result = await lock_bcd(db_session, bcd, user.id)

    assert result.locked_by == user.id


async def test_unlock_by_holder(db_session):
    user = await make_user(db_session, email="unlock1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)
    await lock_bcd(db_session, bcd, user.id)

    result = await unlock_bcd(db_session, bcd, user.id)

    assert result.locked_by is None
    assert result.locked_at is None


async def test_unlock_by_admin(db_session):
    user = await make_user(db_session, email="unlock2a@test.com")
    admin = await make_user(db_session, email="unlock2b@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)
    await lock_bcd(db_session, bcd, user.id)

    result = await unlock_bcd(db_session, bcd, admin.id, is_admin=True)

    assert result.locked_by is None


async def test_unlock_rejects_non_holder_non_admin(db_session):
    user1 = await make_user(db_session, email="unlock3a@test.com")
    user2 = await make_user(db_session, email="unlock3b@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user1.id)
    await lock_bcd(db_session, bcd, user1.id)

    with pytest.raises(AuthorizationError, match="lock holder or an admin"):
        await unlock_bcd(db_session, bcd, user2.id)


async def test_update_section_requires_lock(db_session):
    user = await make_user(db_session, email="nolock1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    with pytest.raises(ConflictError, match="must lock"):
        await update_section(db_session, bcd.id, "places", [], user.id)


async def test_update_section_rejects_wrong_user(db_session):
    user1 = await make_user(db_session, email="wronguser1@test.com")
    user2 = await make_user(db_session, email="wronguser2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user1.id)
    await lock_bcd(db_session, bcd, user1.id)

    with pytest.raises(AuthorizationError, match="locked by another user"):
        await update_section(db_session, bcd.id, "places", [], user2.id)
