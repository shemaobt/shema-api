import pytest

from app.core.exceptions import NotFoundError
from app.services.book_context.compute_entry_brief import compute_entry_brief
from tests.baker import make_bcd, make_bible_book, make_pericope, make_user

SAMPLE_BCD_DATA = {
    "participant_register": [
        {
            "name": "Elimelech",
            "type": "named",
            "entry_verse": {"chapter": 1, "verse": 1},
            "role_in_book": "supporting",
            "relationships": ["husband of Naomi"],
            "arc": [
                {"at": {"chapter": 1, "verse": 1}, "state": "man from Bethlehem"},
                {"at": {"chapter": 1, "verse": 3}, "state": "dead"},
            ],
            "status_at_end": "dead",
        },
        {
            "name": "Naomi",
            "type": "named",
            "entry_verse": {"chapter": 1, "verse": 2},
            "role_in_book": "protagonist",
            "relationships": ["wife of Elimelech"],
            "arc": [
                {"at": {"chapter": 1, "verse": 2}, "state": "wife and mother"},
                {"at": {"chapter": 1, "verse": 5}, "state": "widowed, childless"},
                {"at": {"chapter": 1, "verse": 20}, "state": "bitter, renames herself Mara"},
            ],
            "status_at_end": "grandmother",
        },
        {
            "name": "Boaz",
            "type": "named",
            "entry_verse": {"chapter": 2, "verse": 1},
            "role_in_book": "protagonist",
            "relationships": ["relative of Elimelech"],
            "arc": [
                {"at": {"chapter": 2, "verse": 1}, "state": "wealthy relative introduced"},
                {"at": {"chapter": 2, "verse": 8}, "state": "shows generosity to Ruth"},
            ],
            "status_at_end": "husband of Ruth",
        },
    ],
    "discourse_threads": [
        {
            "label": "Ruth's security",
            "opened_at": {"chapter": 1, "verse": 16},
            "resolved_at": {"chapter": 4, "verse": 13},
            "question": "Will Ruth find security and belonging?",
            "status_by_episode": [
                {"at": {"chapter": 1, "verse": 22}, "status": "opened, Ruth has no provision"},
                {
                    "at": {"chapter": 2, "verse": 23},
                    "status": "partially answered, Boaz shows favor",
                },
            ],
        },
        {
            "label": "Naomi's bitterness",
            "opened_at": {"chapter": 1, "verse": 13},
            "resolved_at": {"chapter": 1, "verse": 21},
            "question": "Will Naomi recover from her losses?",
            "status_by_episode": [
                {"at": {"chapter": 1, "verse": 20}, "status": "intensified, renames herself Mara"},
            ],
        },
    ],
    "places": [
        {
            "name": "Bethlehem",
            "first_appears": {"chapter": 1, "verse": 1},
            "type": "city",
            "meaning_and_function": "home, promised land",
        },
        {
            "name": "Moab",
            "first_appears": {"chapter": 1, "verse": 1},
            "type": "country",
            "meaning_and_function": "exile, foreign land",
        },
        {
            "name": "Boaz's field",
            "first_appears": {"chapter": 2, "verse": 3},
            "type": "field",
            "meaning_and_function": "place of provision",
        },
    ],
    "objects": [
        {
            "name": "grain",
            "first_appears": {"chapter": 2, "verse": 2},
            "what_it_is": "harvested barley",
        },
    ],
    "institutions": [
        {
            "name": "gleaning rights",
            "first_invoked": {"chapter": 2, "verse": 2},
            "what_it_is": "right of the poor to gather leftover grain",
        },
        {
            "name": "kinsman-redeemer",
            "first_invoked": {"chapter": 2, "verse": 20},
            "what_it_is": "obligation of a relative to redeem family property and line",
        },
    ],
}


@pytest.mark.asyncio
async def test_first_pericope_returns_nothing_established(db_session):
    user = await make_user(db_session, email="brief1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", **SAMPLE_BCD_DATA)
    pericope = await make_pericope(
        db_session,
        book.id,
        chapter_start=1,
        verse_start=1,
        chapter_end=1,
        verse_end=5,
        reference="Ruth 1:1-5",
    )

    brief = await compute_entry_brief(db_session, pericope.id)

    assert brief.is_first_pericope is True
    assert len(brief.established_items) == 1
    assert "Nothing" in brief.established_items[0].description


@pytest.mark.asyncio
async def test_slices_participants_before_target_verse(db_session):
    user = await make_user(db_session, email="brief2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", **SAMPLE_BCD_DATA)
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
        chapter_start=2,
        verse_start=1,
        chapter_end=2,
        verse_end=7,
        reference="Ruth 2:1-7",
    )

    brief = await compute_entry_brief(db_session, pericope2.id)

    participant_names = [p.name for p in brief.participants]
    assert "Elimelech" in participant_names
    assert "Naomi" in participant_names
    assert "Boaz" not in participant_names


@pytest.mark.asyncio
async def test_slices_participant_arcs_at_target_verse(db_session):
    user = await make_user(db_session, email="brief3@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", **SAMPLE_BCD_DATA)
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

    brief = await compute_entry_brief(db_session, pericope2.id)

    naomi = next(p for p in brief.participants if p.name == "Naomi")
    arc_states = [a.state for a in naomi.arc]
    assert "wife and mother" in arc_states
    assert "widowed, childless" in arc_states
    assert "bitter, renames herself Mara" not in arc_states


@pytest.mark.asyncio
async def test_includes_active_threads(db_session):
    user = await make_user(db_session, email="brief4@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", **SAMPLE_BCD_DATA)
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
        chapter_start=2,
        verse_start=1,
        chapter_end=2,
        verse_end=7,
        reference="Ruth 2:1-7",
    )

    brief = await compute_entry_brief(db_session, pericope2.id)

    thread_labels = [t.label for t in brief.active_threads]
    assert "Ruth's security" in thread_labels


@pytest.mark.asyncio
async def test_marks_resolved_threads(db_session):
    user = await make_user(db_session, email="brief5@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", **SAMPLE_BCD_DATA)
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
        chapter_start=2,
        verse_start=1,
        chapter_end=2,
        verse_end=7,
        reference="Ruth 2:1-7",
    )

    brief = await compute_entry_brief(db_session, pericope2.id)

    bitterness = next(t for t in brief.active_threads if t.label == "Naomi's bitterness")
    assert bitterness.is_resolved_at_entry is True


@pytest.mark.asyncio
async def test_filters_places_before_target(db_session):
    user = await make_user(db_session, email="brief6@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", **SAMPLE_BCD_DATA)
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
        chapter_start=2,
        verse_start=1,
        chapter_end=2,
        verse_end=7,
        reference="Ruth 2:1-7",
    )

    brief = await compute_entry_brief(db_session, pericope2.id)

    place_names = [p.name for p in brief.places]
    assert "Bethlehem" in place_names
    assert "Boaz's field" not in place_names


@pytest.mark.asyncio
async def test_filters_institutions_before_target(db_session):
    user = await make_user(db_session, email="brief7@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", **SAMPLE_BCD_DATA)
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
        chapter_start=2,
        verse_start=1,
        chapter_end=2,
        verse_end=7,
        reference="Ruth 2:1-7",
    )

    brief = await compute_entry_brief(db_session, pericope2.id)

    inst_names = [i.name for i in brief.institutions]
    assert "gleaning rights" not in inst_names
    assert "kinsman-redeemer" not in inst_names


@pytest.mark.asyncio
async def test_returns_error_when_no_approved_bcd(db_session):
    await make_user(db_session, email="brief8@test.com")
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

    with pytest.raises(NotFoundError, match="No approved Book Context Document"):
        await compute_entry_brief(db_session, pericope.id)


@pytest.mark.asyncio
async def test_same_chapter_different_verses(db_session):
    user = await make_user(db_session, email="brief9@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", **SAMPLE_BCD_DATA)
    await make_pericope(
        db_session,
        book.id,
        chapter_start=1,
        verse_start=1,
        chapter_end=1,
        verse_end=2,
        reference="Ruth 1:1-2",
    )
    pericope2 = await make_pericope(
        db_session,
        book.id,
        chapter_start=1,
        verse_start=3,
        chapter_end=1,
        verse_end=5,
        reference="Ruth 1:3-5",
    )

    brief = await compute_entry_brief(db_session, pericope2.id)

    participant_names = [p.name for p in brief.participants]
    assert "Elimelech" in participant_names
    assert "Naomi" in participant_names

    elim = next(p for p in brief.participants if p.name == "Elimelech")
    arc_states = [a.state for a in elim.arc]
    assert "man from Bethlehem" in arc_states
    assert "dead" not in arc_states
