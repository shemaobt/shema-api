from app.services.book_context.validate_against_brief import validate_map_against_brief
from tests.baker import make_bible_book, make_meaning_map, make_pericope, make_user

SAMPLE_BCD_DATA = {
    "participant_register": [
        {
            "name": "Naomi",
            "type": "named",
            "entry_verse": {"chapter": 1, "verse": 1},
            "role_in_book": "protagonist",
            "relationships": ["wife of Elimelech"],
            "arc": [
                {"at": {"chapter": 1, "verse": 2}, "state": "wife and mother"},
            ],
            "status_at_end": "grandmother",
        },
    ],
    "discourse_threads": [],
    "places": [],
    "objects": [],
    "institutions": [],
}

SAMPLE_MAP_DATA_WITH_ESTABLISHED = {
    "level_1": {"arc": "The narrative arc of the passage."},
    "already_established": [
        {
            "category": "participant",
            "name": "Naomi",
            "description": "Naomi: wife and mother",
            "verse_reference": "1:2",
        },
    ],
    "level_2_scenes": [],
    "level_3_propositions": [
        {
            "proposition_number": 1,
            "verse": "6",
            "content": [
                {"question": "What happens?", "answer": "Naomi hears news from Judah"},
            ],
        },
    ],
}

SAMPLE_MAP_DATA_CLEAN_L3 = {
    "level_1": {"arc": "The narrative arc of the passage."},
    "already_established": [
        {
            "category": "participant",
            "name": "Naomi",
            "description": "Naomi: wife and mother",
            "verse_reference": "1:2",
        },
    ],
    "level_2_scenes": [],
    "level_3_propositions": [
        {
            "proposition_number": 1,
            "verse": "6",
            "content": [
                {"question": "What happens?", "answer": "a woman hears news from Judah"},
            ],
        },
    ],
}

SAMPLE_MAP_DATA_NO_ESTABLISHED = {
    "level_1": {"arc": "The arc."},
    "already_established": [],
    "level_2_scenes": [],
    "level_3_propositions": [],
}

SAMPLE_MAP_DATA_FIRST_PERICOPE = {
    "level_1": {"arc": "The arc."},
    "already_established": [
        {
            "category": "event",
            "name": "Opening",
            "description": "Nothing. This is the opening of the book.",
            "verse_reference": "",
        },
    ],
    "level_2_scenes": [],
    "level_3_propositions": [],
}


async def test_warns_missing_established_list_non_first_pericope(db_session):
    user = await make_user(db_session, email="val1@test.com")
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
        data=SAMPLE_MAP_DATA_NO_ESTABLISHED,
    )

    issues = await validate_map_against_brief(db_session, mm)

    assert any(i.severity == "error" and "Already Established" in i.message for i in issues)


async def test_passes_first_pericope_with_nothing_entry(db_session):
    user = await make_user(db_session, email="val2@test.com")
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
        data=SAMPLE_MAP_DATA_FIRST_PERICOPE,
    )

    issues = await validate_map_against_brief(db_session, mm)

    assert not any(i.severity == "error" for i in issues)


async def test_warns_established_name_in_level_3(db_session):
    user = await make_user(db_session, email="val3@test.com")
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
        data=SAMPLE_MAP_DATA_WITH_ESTABLISHED,
    )

    issues = await validate_map_against_brief(db_session, mm)

    assert any("Naomi" in i.message and i.section.startswith("prop_") for i in issues)


async def test_passes_when_level_3_has_no_established_names(db_session):
    user = await make_user(db_session, email="val4@test.com")
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
    mm = await make_meaning_map(db_session, pericope2.id, user.id, data=SAMPLE_MAP_DATA_CLEAN_L3)

    issues = await validate_map_against_brief(db_session, mm)

    assert not any(i.section.startswith("prop_") for i in issues)
