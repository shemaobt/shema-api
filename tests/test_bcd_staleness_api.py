from app.services.book_context.check_stale import check_bcd_staleness
from app.services.book_context.validate_against_brief import validate_map_against_brief
from tests.baker import make_bcd, make_bible_book, make_meaning_map, make_pericope, make_user


async def test_staleness_check_current_version(db_session):
    user = await make_user(db_session, email="stale1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", version=3)
    pericope = await make_pericope(db_session, book.id, reference="Ruth 1:1-5")
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    mm.bcd_version_at_creation = 3
    await db_session.commit()

    result = await check_bcd_staleness(db_session, mm)
    assert result.is_stale is False


async def test_staleness_check_outdated_version(db_session):
    user = await make_user(db_session, email="stale2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", version=1)
    await make_bcd(db_session, book.id, user.id, status="approved", version=5)
    pericope = await make_pericope(db_session, book.id, reference="Ruth 1:1-5")
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    mm.bcd_version_at_creation = 1
    await db_session.commit()

    result = await check_bcd_staleness(db_session, mm)
    assert result.is_stale is True
    assert result.current_version == 5


async def test_staleness_check_no_bcd_at_all(db_session):
    user = await make_user(db_session, email="stale3@test.com")
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


async def test_staleness_check_no_version_on_mm(db_session):
    user = await make_user(db_session, email="stale4@test.com")
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

    result = await check_bcd_staleness(db_session, mm)
    assert result.is_stale is False


async def test_validate_non_first_pericope_no_established(db_session):
    user = await make_user(db_session, email="val_api1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_pericope(
        db_session,
        book.id,
        chapter_start=1,
        verse_start=1,
        chapter_end=1,
        verse_end=5,
        reference="Ruth 1:1-5",
    )
    pericope2 = await make_pericope(
        db_session,
        book.id,
        chapter_start=1,
        verse_start=6,
        chapter_end=1,
        verse_end=18,
        reference="Ruth 1:6-18",
    )

    mm = await make_meaning_map(
        db_session,
        pericope2.id,
        user.id,
        data={
            "level_1": {"arc": "test"},
            "already_established": [],
            "level_2_scenes": [],
            "level_3_propositions": [],
        },
    )

    issues = await validate_map_against_brief(db_session, mm)
    assert any(i.severity == "error" and "Already Established" in i.message for i in issues)


async def test_validate_first_pericope_no_issues(db_session):
    user = await make_user(db_session, email="val_api2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    pericope = await make_pericope(
        db_session,
        book.id,
        chapter_start=1,
        verse_start=1,
        chapter_end=1,
        verse_end=5,
        reference="Ruth 1:1-5",
    )

    mm = await make_meaning_map(
        db_session,
        pericope.id,
        user.id,
        data={
            "level_1": {"arc": "test"},
            "already_established": [],
            "level_2_scenes": [],
            "level_3_propositions": [],
        },
    )

    issues = await validate_map_against_brief(db_session, mm)
    assert not any(i.severity == "error" for i in issues)


async def test_validate_detects_established_name_in_propositions(db_session):
    user = await make_user(db_session, email="val_api3@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_pericope(
        db_session,
        book.id,
        chapter_start=1,
        verse_start=1,
        chapter_end=1,
        verse_end=5,
        reference="Ruth 1:1-5",
    )
    pericope2 = await make_pericope(
        db_session,
        book.id,
        chapter_start=1,
        verse_start=6,
        chapter_end=1,
        verse_end=18,
        reference="Ruth 1:6-18",
    )

    mm = await make_meaning_map(
        db_session,
        pericope2.id,
        user.id,
        data={
            "level_1": {"arc": "test"},
            "already_established": [
                {
                    "category": "participant",
                    "name": "Boaz",
                    "description": "A kinsman",
                    "verse_reference": "2:1",
                },
            ],
            "level_2_scenes": [],
            "level_3_propositions": [
                {
                    "proposition_number": 1,
                    "verse": "6",
                    "content": [
                        {"question": "Who?", "answer": "Boaz goes to the gate"},
                    ],
                },
            ],
        },
    )

    issues = await validate_map_against_brief(db_session, mm)
    assert any("Boaz" in i.message for i in issues)
