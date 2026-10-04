import pytest

from app.core.exceptions import NotFoundError
from app.services.book_context.compute_entry_brief import compute_entry_brief
from tests.baker import make_bcd, make_bible_book, make_pericope, make_user

SAMPLE_PARTICIPANTS = [
    {
        "name": "Naomi",
        "type": "named",
        "entry_verse": {"chapter": 1, "verse": 1},
        "role_in_book": "protagonist",
        "relationships": [],
        "arc": [
            {"at": {"chapter": 1, "verse": 2}, "state": "introduced"},
            {"at": {"chapter": 1, "verse": 5}, "state": "widowed"},
        ],
        "status_at_end": "grandmother",
    },
    {
        "name": "Ruth",
        "type": "named",
        "entry_verse": {"chapter": 1, "verse": 4},
        "role_in_book": "protagonist",
        "relationships": [],
        "arc": [
            {"at": {"chapter": 1, "verse": 4}, "state": "married"},
            {"at": {"chapter": 1, "verse": 16}, "state": "committed"},
        ],
        "status_at_end": "ancestor of David",
    },
    {
        "name": "Boaz",
        "type": "named",
        "entry_verse": {"chapter": 2, "verse": 1},
        "role_in_book": "kinsman-redeemer",
        "relationships": [],
        "arc": [
            {"at": {"chapter": 2, "verse": 4}, "state": "introduced at field"},
        ],
        "status_at_end": "husband of Ruth",
    },
]

SAMPLE_THREADS = [
    {
        "label": "Famine migration",
        "opened_at": {"chapter": 1, "verse": 1},
        "question": "What will happen due to the famine?",
        "status_by_episode": [
            {"at": {"chapter": 1, "verse": 1}, "status": "famine drives family to Moab"},
        ],
        "resolved_at": {"chapter": 1, "verse": 6},
    },
    {
        "label": "Loyalty of Ruth",
        "opened_at": {"chapter": 1, "verse": 8},
        "question": "Will Ruth stay loyal to Naomi?",
        "status_by_episode": [
            {"at": {"chapter": 1, "verse": 16}, "status": "Ruth commits to Naomi"},
        ],
        "resolved_at": None,
    },
]

SAMPLE_INSTITUTIONS = [
    {
        "name": "Kinsman-redeemer",
        "what_it_is": "Near relative with right of redemption",
        "first_invoked": {"chapter": 2, "verse": 20},
    },
]


async def test_first_pericope_returns_opening_brief(db_session):
    user = await make_user(db_session, email="eb1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(
        db_session,
        book.id,
        user.id,
        status="approved",
        version=1,
        participant_register=SAMPLE_PARTICIPANTS,
        discourse_threads=SAMPLE_THREADS,
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

    brief = await compute_entry_brief(db_session, pericope.id)

    assert brief.is_first_pericope is True
    assert len(brief.established_items) == 1
    assert brief.established_items[0].name == "Opening"
    assert brief.bcd_version == 1


async def test_non_first_pericope_slices_by_entry_verse(db_session):
    user = await make_user(db_session, email="eb2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(
        db_session,
        book.id,
        user.id,
        status="approved",
        version=2,
        participant_register=SAMPLE_PARTICIPANTS,
        discourse_threads=SAMPLE_THREADS,
        institutions=SAMPLE_INSTITUTIONS,
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

    brief = await compute_entry_brief(db_session, pericope2.id)

    assert brief.is_first_pericope is False
    assert brief.bcd_version == 2
    participant_names = [p.name for p in brief.participants]
    assert "Naomi" in participant_names
    assert "Ruth" in participant_names
    assert "Boaz" not in participant_names


async def test_entry_brief_filters_threads_by_opened_at(db_session):
    user = await make_user(db_session, email="eb3@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(
        db_session,
        book.id,
        user.id,
        status="approved",
        version=1,
        discourse_threads=SAMPLE_THREADS,
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
        verse_end=7,
        reference="Ruth 1:6-7",
    )

    brief = await compute_entry_brief(db_session, pericope2.id)

    thread_labels = [t.label for t in brief.active_threads]
    assert "Famine migration" in thread_labels
    assert "Loyalty of Ruth" not in thread_labels


async def test_entry_brief_resolved_thread_excluded_from_established(db_session):
    user = await make_user(db_session, email="eb4@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(
        db_session,
        book.id,
        user.id,
        status="approved",
        version=1,
        discourse_threads=SAMPLE_THREADS,
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
        verse_start=8,
        chapter_end=1,
        verse_end=18,
        reference="Ruth 1:8-18",
    )

    brief = await compute_entry_brief(db_session, pericope2.id)

    established_names = [e.name for e in brief.established_items]
    assert "Famine migration" not in established_names


async def test_entry_brief_institutions_filtered(db_session):
    user = await make_user(db_session, email="eb5@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(
        db_session,
        book.id,
        user.id,
        status="approved",
        version=1,
        institutions=SAMPLE_INSTITUTIONS,
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
        chapter_end=2,
        verse_end=19,
        reference="Ruth 1:6-2:19",
    )

    brief = await compute_entry_brief(db_session, pericope2.id)

    assert len(brief.institutions) == 0


async def test_entry_brief_no_approved_bcd_raises(db_session):
    user = await make_user(db_session, email="eb6@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="draft", version=1)
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


async def test_entry_brief_nonexistent_pericope_raises(db_session):
    with pytest.raises(NotFoundError, match="Pericope"):
        await compute_entry_brief(db_session, "nonexistent-id")
