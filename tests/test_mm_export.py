import json

import pytest

from app.core.exceptions import AuthorizationError, NotFoundError
from app.services.meaning_map.ensure_ot import ensure_ot
from app.services.meaning_map.export_json import export_json
from app.services.meaning_map.export_prose import export_prose
from app.services.meaning_map.list_books import list_books
from app.services.meaning_map.resolve_feedback import resolve_feedback
from app.services.meaning_map.seed_books import seed_books
from tests.baker import (
    SAMPLE_MM_DATA,
    make_bible_book,
    make_meaning_map,
    make_meaning_map_feedback,
    make_pericope,
    make_user,
)


async def test_export_json_returns_valid_json(db_session) -> None:
    user = await make_user(db_session, email="analyst43@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, data=SAMPLE_MM_DATA)
    result = export_json(mm)
    parsed = json.loads(result)
    assert parsed == SAMPLE_MM_DATA


async def test_export_json_empty_data(db_session) -> None:
    user = await make_user(db_session, email="analyst44@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, data={})
    result = export_json(mm)
    assert json.loads(result) == {}


async def test_export_prose_contains_arc(db_session) -> None:
    user = await make_user(db_session, email="analyst45@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, data=SAMPLE_MM_DATA)
    result = export_prose(mm)
    assert "God creates the heavens and the earth." in result
    assert "# Bible Meaning Map" in result
    assert "Level 1 — The Arc" in result


async def test_export_prose_contains_scene_details(db_session) -> None:
    user = await make_user(db_session, email="analyst46@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, data=SAMPLE_MM_DATA)
    result = export_prose(mm)
    assert "Scene 1" in result
    assert "Creation of light" in result
    assert "2A — People" in result
    assert "2B — Places" in result
    assert "2C — Objects and Elements" in result
    assert "2D — What Happens" in result
    assert "2E — Communicative Purpose" in result


async def test_export_prose_contains_propositions(db_session) -> None:
    user = await make_user(db_session, email="analyst47@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, data=SAMPLE_MM_DATA)
    result = export_prose(mm)
    assert "Proposition 1" in result
    assert "What happens?" in result


async def test_export_prose_empty_data(db_session) -> None:
    user = await make_user(db_session, email="analyst48@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, data={})
    result = export_prose(mm)
    assert "# Bible Meaning Map" in result


async def test_resolve_feedback_success(db_session) -> None:
    user = await make_user(db_session, email="analyst49@test.com")
    reviewer = await make_user(db_session, email="reviewer3@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    fb = await make_meaning_map_feedback(db_session, mm.id, reviewer.id)
    assert fb.resolved is False
    resolved = await resolve_feedback(db_session, mm.id, fb.id)
    assert resolved.resolved is True


async def test_resolve_feedback_raises_if_not_found(db_session) -> None:
    user = await make_user(db_session, email="analyst50@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    with pytest.raises(NotFoundError, match=r"Feedback .* not found"):
        await resolve_feedback(db_session, mm.id, "nonexistent-id")


async def test_resolve_feedback_wrong_meaning_map(db_session) -> None:
    user = await make_user(db_session, email="analyst51@test.com")
    reviewer = await make_user(db_session, email="reviewer4@test.com")
    book = await make_bible_book(db_session)
    p1 = await make_pericope(db_session, book.id, reference="Gen 1:1-5")
    p2 = await make_pericope(db_session, book.id, chapter_start=2, reference="Gen 2:1-5")
    mm1 = await make_meaning_map(db_session, p1.id, user.id)
    mm2 = await make_meaning_map(db_session, p2.id, user.id)
    fb = await make_meaning_map_feedback(db_session, mm1.id, reviewer.id)
    with pytest.raises(NotFoundError, match=r"Feedback .* not found"):
        await resolve_feedback(db_session, mm2.id, fb.id)


async def test_seed_books_inserts_all_66(db_session) -> None:
    count = await seed_books(db_session)
    assert count == 66
    books = await list_books(db_session)
    assert len(books) == 66


async def test_seed_books_idempotent(db_session) -> None:
    first = await seed_books(db_session)
    assert first == 66
    second = await seed_books(db_session)
    assert second == 0
    books = await list_books(db_session)
    assert len(books) == 66


async def test_seed_books_ot_enabled_nt_disabled(db_session) -> None:
    await seed_books(db_session)
    books = await list_books(db_session)
    for book in books:
        if book.testament == "OT":
            assert book.is_enabled is True, f"{book.name} should be enabled"
        else:
            assert book.is_enabled is False, f"{book.name} should be disabled"


async def test_ensure_ot_passes_for_enabled_book(db_session) -> None:
    book = await make_bible_book(db_session, is_enabled=True)
    ensure_ot(book)


async def test_ensure_ot_raises_for_disabled_book(db_session) -> None:
    book = await make_bible_book(
        db_session,
        name="Matthew",
        abbreviation="Matt",
        testament="NT",
        order=40,
        chapter_count=28,
        is_enabled=False,
    )
    with pytest.raises(AuthorizationError, match="not enabled for meaning map work"):
        ensure_ot(book)
