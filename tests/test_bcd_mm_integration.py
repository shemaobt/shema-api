from app.services.book_context.check_stale import check_bcd_staleness
from tests.baker import make_bcd, make_bible_book, make_meaning_map, make_pericope, make_user


async def test_check_stale_returns_false_when_current(db_session):
    user = await make_user(db_session, email="int1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", version=2)
    pericope = await make_pericope(db_session, book.id, reference="Ruth 1:1-5")
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    mm.bcd_version_at_creation = 2
    await db_session.commit()

    result = await check_bcd_staleness(db_session, mm)

    assert result.is_stale is False


async def test_check_stale_returns_true_when_bcd_updated(db_session):
    user = await make_user(db_session, email="int2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", version=1)
    await make_bcd(db_session, book.id, user.id, status="approved", version=2)
    pericope = await make_pericope(db_session, book.id, reference="Ruth 1:1-5")
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    mm.bcd_version_at_creation = 1
    await db_session.commit()

    result = await check_bcd_staleness(db_session, mm)

    assert result.is_stale is True
    assert result.current_version == 2


async def test_check_stale_returns_false_when_no_bcd(db_session):
    user = await make_user(db_session, email="int3@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    pericope = await make_pericope(db_session, book.id, reference="Ruth 1:1-5")
    mm = await make_meaning_map(db_session, pericope.id, user.id)

    result = await check_bcd_staleness(db_session, mm)

    assert result.is_stale is False
