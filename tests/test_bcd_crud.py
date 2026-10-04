import pytest

from app.core.exceptions import AuthorizationError, ConflictError
from app.services.book_context.create_bcd import create_bcd
from app.services.book_context.create_new_version import create_new_version
from app.services.book_context.get_latest_approved import get_latest_approved
from app.services.book_context.lock_bcd import lock_bcd
from app.services.book_context.update_section import update_section
from tests.baker import make_bcd, make_bible_book, make_user

SAMPLE_PARTICIPANTS = [
    {
        "name": "Naomi",
        "type": "named",
        "entry_verse": {"chapter": 1, "verse": 1},
        "role_in_book": "protagonist",
        "relationships": ["wife of Elimelech", "mother-in-law of Ruth"],
        "arc": [
            {"at": {"chapter": 1, "verse": 2}, "state": "introduced as wife and mother"},
            {"at": {"chapter": 1, "verse": 5}, "state": "widowed, childless"},
        ],
        "status_at_end": "grandmother of Obed",
    },
]


async def test_create_bcd_success(db_session):
    user = await make_user(db_session, email="creator@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )

    bcd = await create_bcd(db_session, book.id, user.id, "narrative")

    assert bcd.book_id == book.id
    assert bcd.status.value == "draft"
    assert bcd.version == 1


async def test_create_bcd_rejects_nt_book(db_session):
    user = await make_user(db_session, email="creator2@test.com")
    book = await make_bible_book(
        db_session,
        name="Matthew",
        abbreviation="Mat",
        testament="NT",
        order=40,
        chapter_count=28,
        is_enabled=False,
    )

    with pytest.raises(AuthorizationError, match="Old Testament"):
        await create_bcd(db_session, book.id, user.id, "narrative")


async def test_get_latest_approved_returns_highest_version(db_session):
    user = await make_user(db_session, email="creator3@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", version=1)
    await make_bcd(db_session, book.id, user.id, status="approved", version=2)

    result = await get_latest_approved(db_session, book.id)

    assert result is not None
    assert result.version == 2


async def test_get_latest_approved_skips_drafts(db_session):
    user = await make_user(db_session, email="creator4@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", version=1)
    await make_bcd(db_session, book.id, user.id, status="draft", version=2)

    result = await get_latest_approved(db_session, book.id)

    assert result is not None
    assert result.version == 1


async def test_get_latest_approved_returns_none_when_no_approved(db_session):
    user = await make_user(db_session, email="creator5@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="draft", version=1)

    result = await get_latest_approved(db_session, book.id)

    assert result is None


async def test_update_section_in_draft(db_session):
    user = await make_user(db_session, email="creator6@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)
    await lock_bcd(db_session, bcd, user.id)

    result = await update_section(
        db_session, bcd.id, "participant_register", SAMPLE_PARTICIPANTS, user.id
    )

    assert result.participant_register == SAMPLE_PARTICIPANTS


async def test_update_section_rejects_if_approved(db_session):
    user = await make_user(db_session, email="creator7@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="approved")

    with pytest.raises(ConflictError, match="Cannot edit an approved"):
        await update_section(
            db_session, bcd.id, "participant_register", SAMPLE_PARTICIPANTS, user.id
        )


async def test_create_new_version_from_approved(db_session):
    user = await make_user(db_session, email="creator8@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(
        db_session,
        book.id,
        user.id,
        status="approved",
        version=1,
        participant_register=SAMPLE_PARTICIPANTS,
    )

    new_bcd = await create_new_version(db_session, bcd.id, user.id)

    assert new_bcd.version == 2
    assert new_bcd.status.value == "draft"
    assert new_bcd.participant_register == SAMPLE_PARTICIPANTS
