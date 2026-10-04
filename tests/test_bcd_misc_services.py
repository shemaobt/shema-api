from datetime import UTC, datetime

import pytest

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.services.book_context.create_bcd import create_bcd
from app.services.book_context.create_new_version import create_new_version
from app.services.book_context.list_generation_logs import list_generation_logs
from app.services.book_context.track_step import track_step
from app.services.book_context.update_section import update_section
from tests.baker import make_bcd, make_bible_book, make_user


async def test_create_bcd_stores_genre_context(db_session):
    user = await make_user(db_session, email="genre1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )

    bcd = await create_bcd(db_session, book.id, user.id, "poetry")

    assert bcd.genre_context == {"primary_genre": "poetry"}


async def test_create_bcd_increments_version(db_session):
    user = await make_user(db_session, email="ver1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )

    bcd1 = await create_bcd(db_session, book.id, user.id, "narrative")
    bcd2 = await create_bcd(db_session, book.id, user.id, "narrative")

    assert bcd1.version == 1
    assert bcd2.version == 2


async def test_update_section_unknown_key_raises_not_found(db_session):
    user = await make_user(db_session, email="unk1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    with pytest.raises(NotFoundError, match="Unknown section"):
        await update_section(db_session, bcd.id, "nonexistent_section", {}, user.id)


async def test_update_section_rejects_generating(db_session):
    user = await make_user(db_session, email="gen2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="generating")

    with pytest.raises(ConflictError, match="currently being generated"):
        await update_section(db_session, bcd.id, "places", [], user.id)


async def test_create_new_version_rejects_draft(db_session):
    user = await make_user(db_session, email="nv1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="draft")

    with pytest.raises(ConflictError, match="approved document"):
        await create_new_version(db_session, bcd.id, user.id)


async def test_track_step_success(db_session):
    user = await make_user(db_session, email="ts1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    async with track_step(db_session, bcd.id, "structural_outline", 1, input_summary="test") as log:
        log.output_summary = "done"

    assert log.status == "completed"
    assert log.duration_ms is not None
    assert log.completed_at is not None


async def test_track_step_failure(db_session):
    user = await make_user(db_session, email="ts2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    with pytest.raises(RuntimeError, match="boom"):
        async with track_step(db_session, bcd.id, "participants", 2) as log:
            raise RuntimeError("boom")

    assert log.status == "failed"
    assert "boom" in log.error_detail


async def test_update_section_requires_lock(db_session):
    user = await make_user(db_session, email="lock_required@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    with pytest.raises(ConflictError, match="lock the document"):
        await update_section(db_session, bcd.id, "places", [], user.id)


async def test_update_section_wrong_user_cannot_edit(db_session):
    owner = await make_user(db_session, email="owner@test.com")
    intruder = await make_user(db_session, email="intruder@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, owner.id)
    bcd.locked_by = owner.id
    bcd.locked_at = datetime.now(UTC)
    await db_session.commit()

    with pytest.raises(AuthorizationError, match="locked by another user"):
        await update_section(db_session, bcd.id, "places", [], intruder.id)


async def test_update_section_en_drops_section_from_cached_locales(db_session):
    user = await make_user(db_session, email="en_drop@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, places=[{"name": "old"}])
    bcd.locked_by = user.id
    bcd.locked_at = datetime.now(UTC)
    bcd.translations = {
        "pt-BR": {
            "places": [{"name": "pt places"}],
            "objects": [{"name": "pt objects"}],
        },
        "es": {
            "places": [{"name": "es places"}],
            "objects": [{"name": "es objects"}],
        },
    }
    await db_session.commit()

    new_places = [{"name": "fresh english"}]
    updated = await update_section(db_session, bcd.id, "places", new_places, user.id, locale="en")

    assert updated.places == new_places
    assert updated.translations is not None
    # places dropped from both locales
    assert "places" not in updated.translations["pt-BR"]
    assert "places" not in updated.translations["es"]
    # objects preserved in both locales
    assert updated.translations["pt-BR"]["objects"] == [{"name": "pt objects"}]
    assert updated.translations["es"]["objects"] == [{"name": "es objects"}]


async def test_update_section_non_en_stores_original_payload(db_session, monkeypatch):
    async def fake_back_translate(data, locale):
        return {"english_version": True, "source_locale": locale}

    monkeypatch.setattr(
        "app.services.book_context.update_section.back_translate_content",
        fake_back_translate,
    )

    user = await make_user(db_session, email="pt_store@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, genre_context={"primary_genre": "old"})
    bcd.locked_by = user.id
    bcd.locked_at = datetime.now(UTC)
    await db_session.commit()

    pt_payload = {"primary_genre": "narrativa", "sub_genres": ["história"]}
    updated = await update_section(
        db_session,
        bcd.id,
        "genre_context",
        pt_payload,
        user.id,
        locale="pt-BR",
    )

    assert updated.genre_context == {"english_version": True, "source_locale": "pt-BR"}
    assert updated.translations is not None
    assert updated.translations["pt-BR"]["genre_context"] == pt_payload


async def test_update_section_non_en_isolates_locale_caches(db_session, monkeypatch):
    async def fake_back_translate(data, locale):
        return {"english": "translated"}

    monkeypatch.setattr(
        "app.services.book_context.update_section.back_translate_content",
        fake_back_translate,
    )

    user = await make_user(db_session, email="pt_isolate@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)
    bcd.locked_by = user.id
    bcd.locked_at = datetime.now(UTC)
    bcd.translations = {
        "pt-BR": {"places": [{"name": "old pt"}], "theological_spine": "pt spine"},
        "es": {"places": [{"name": "old es"}], "theological_spine": "es spine"},
        "fr": {"places": [{"name": "old fr"}], "theological_spine": "fr spine"},
    }
    await db_session.commit()

    pt_payload = [{"name": "novo lugar"}]
    updated = await update_section(
        db_session,
        bcd.id,
        "places",
        pt_payload,
        user.id,
        locale="pt-BR",
    )

    assert updated.translations["pt-BR"]["places"] == pt_payload
    # pt-BR.theological_spine untouched (same section, different locale path)
    assert updated.translations["pt-BR"]["theological_spine"] == "pt spine"
    # places dropped from es and fr
    assert "places" not in updated.translations["es"]
    assert "places" not in updated.translations["fr"]
    # theological_spine preserved in es and fr (different section)
    assert updated.translations["es"]["theological_spine"] == "es spine"
    assert updated.translations["fr"]["theological_spine"] == "fr spine"


async def test_update_section_non_en_first_translation(db_session, monkeypatch):
    async def fake_back_translate(data, locale):
        return {"english": "back"}

    monkeypatch.setattr(
        "app.services.book_context.update_section.back_translate_content",
        fake_back_translate,
    )

    user = await make_user(db_session, email="pt_first@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)
    bcd.locked_by = user.id
    bcd.locked_at = datetime.now(UTC)
    assert bcd.translations is None
    await db_session.commit()

    pt_payload = {"primary_genre": "poesia"}
    updated = await update_section(
        db_session,
        bcd.id,
        "genre_context",
        pt_payload,
        user.id,
        locale="pt-BR",
    )

    assert updated.translations == {"pt-BR": {"genre_context": pt_payload}}


async def test_list_generation_logs_ordered(db_session):
    user = await make_user(db_session, email="lg1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    async with track_step(db_session, bcd.id, "collect_bhsa", 0):
        pass
    async with track_step(db_session, bcd.id, "structural_outline", 1):
        pass
    async with track_step(db_session, bcd.id, "participants", 2):
        pass

    logs = await list_generation_logs(db_session, bcd.id)
    assert len(logs) == 3
    assert [log_entry.step_name for log_entry in logs] == [
        "collect_bhsa",
        "structural_outline",
        "participants",
    ]
