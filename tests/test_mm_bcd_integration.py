from app.services.meaning_map.create_meaning_map import create_meaning_map
from tests.baker import make_bible_book, make_pericope, make_user


async def test_create_meaning_map_with_bcd_version(db_session):
    user = await make_user(db_session, email="mmint1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    pericope = await make_pericope(db_session, book.id, reference="Ruth 1:1-5")

    mm = await create_meaning_map(
        db_session,
        pericope_id=pericope.id,
        analyst_id=user.id,
        data={"level_1": {"arc": "test"}},
        bcd_version_at_creation=3,
    )

    assert mm.bcd_version_at_creation == 3


async def test_create_meaning_map_without_bcd_version(db_session):
    user = await make_user(db_session, email="mmint2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    pericope = await make_pericope(db_session, book.id, reference="Ruth 1:1-5")

    mm = await create_meaning_map(
        db_session,
        pericope_id=pericope.id,
        analyst_id=user.id,
        data={"level_1": {"arc": "test"}},
    )

    assert mm.bcd_version_at_creation is None
