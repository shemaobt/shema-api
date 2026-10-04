import pytest

from app.services.book_context.list_generation_logs import list_generation_logs
from app.services.book_context.track_step import track_step
from tests.baker import make_bcd, make_bible_book, make_user


async def test_track_step_creates_log_on_start(db_session):
    user = await make_user(db_session, email="log1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    async with track_step(db_session, bcd.id, "structural_outline", 1, input_summary="4 chapters"):
        logs = await list_generation_logs(db_session, bcd.id)
        assert len(logs) == 1
        assert logs[0].status == "running"
        assert logs[0].input_summary == "4 chapters"


async def test_track_step_marks_completed_on_success(db_session):
    user = await make_user(db_session, email="log2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    async with track_step(db_session, bcd.id, "participant_scan", 2) as log:
        log.output_summary = "8 participants found"

    logs = await list_generation_logs(db_session, bcd.id)
    assert logs[0].status == "completed"
    assert logs[0].duration_ms is not None
    assert logs[0].output_summary == "8 participants found"


async def test_track_step_marks_failed_on_exception(db_session):
    user = await make_user(db_session, email="log3@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    with pytest.raises(ValueError, match="LLM broke"):
        async with track_step(db_session, bcd.id, "discourse_threads", 4):
            raise ValueError("LLM broke")

    logs = await list_generation_logs(db_session, bcd.id)
    assert logs[0].status == "failed"
    assert "LLM broke" in logs[0].error_detail


async def test_list_generation_logs_ordered_by_step(db_session):
    user = await make_user(db_session, email="log4@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    async with track_step(db_session, bcd.id, "step_c", 3):
        pass
    async with track_step(db_session, bcd.id, "step_a", 1):
        pass
    async with track_step(db_session, bcd.id, "step_b", 2):
        pass

    logs = await list_generation_logs(db_session, bcd.id)
    assert [log_entry.step_name for log_entry in logs] == ["step_a", "step_b", "step_c"]
