from datetime import UTC, datetime

import pytest

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.services.meaning_map.delete_meaning_map import delete_meaning_map
from app.services.meaning_map.get_meaning_map_or_404 import get_meaning_map_or_404
from app.services.meaning_map.lock_map import lock_map
from app.services.meaning_map.transition_status import transition_status
from app.services.meaning_map.unlock_map import unlock_map
from app.services.meaning_map.update_meaning_map_data import update_meaning_map_data
from tests.baker import (
    SAMPLE_MM_DATA,
    make_bible_book,
    make_meaning_map,
    make_pericope,
    make_user,
)


async def test_delete_meaning_map_success(db_session) -> None:
    user = await make_user(db_session, email="analyst13@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    await delete_meaning_map(db_session, mm, user.id)
    with pytest.raises(NotFoundError):
        await get_meaning_map_or_404(db_session, mm.id)


async def test_delete_meaning_map_raises_if_not_draft(db_session) -> None:
    user = await make_user(db_session, email="analyst14@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, status="cross_check")
    with pytest.raises(AuthorizationError, match="Only draft meaning maps can be deleted"):
        await delete_meaning_map(db_session, mm, user.id)


async def test_delete_meaning_map_raises_if_not_analyst(db_session) -> None:
    analyst = await make_user(db_session, email="analyst15@test.com")
    other = await make_user(db_session, email="other@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, analyst.id)
    with pytest.raises(
        AuthorizationError, match="Only the analyst who created the map can delete it"
    ):
        await delete_meaning_map(db_session, mm, other.id)


async def test_update_meaning_map_data_success(db_session) -> None:
    user = await make_user(db_session, email="analyst16@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    updated = await update_meaning_map_data(db_session, mm, SAMPLE_MM_DATA, user.id)
    assert updated.data == SAMPLE_MM_DATA


async def test_update_meaning_map_data_by_lock_holder(db_session) -> None:
    user = await make_user(db_session, email="analyst17@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(
        db_session, pericope.id, user.id, locked_by=user.id, locked_at=datetime.now(UTC)
    )
    updated = await update_meaning_map_data(db_session, mm, {"new": "data"}, user.id)
    assert updated.data == {"new": "data"}


async def test_update_meaning_map_data_raises_if_locked_by_other(db_session) -> None:
    analyst = await make_user(db_session, email="analyst18@test.com")
    other = await make_user(db_session, email="other2@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(
        db_session, pericope.id, analyst.id, locked_by=other.id, locked_at=datetime.now(UTC)
    )
    with pytest.raises(AuthorizationError, match="locked by another user"):
        await update_meaning_map_data(db_session, mm, {"x": 1}, analyst.id)


async def test_update_meaning_map_data_raises_if_approved(db_session) -> None:
    user = await make_user(db_session, email="analyst19@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, status="approved")
    with pytest.raises(AuthorizationError, match="Cannot edit an approved meaning map"):
        await update_meaning_map_data(db_session, mm, {"x": 1}, user.id)


async def test_update_meaning_map_data_unlocked_map(db_session) -> None:
    user = await make_user(db_session, email="analyst20@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, data={"old": "data"})
    updated = await update_meaning_map_data(db_session, mm, {"replaced": True}, user.id)
    assert updated.data == {"replaced": True}


async def test_transition_draft_to_cross_check(db_session) -> None:
    user = await make_user(db_session, email="analyst21@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(
        db_session, pericope.id, user.id, locked_by=user.id, locked_at=datetime.now(UTC)
    )
    result = await transition_status(db_session, mm, "cross_check", user.id)
    assert result.status == "cross_check"
    assert result.locked_by is None
    assert result.locked_at is None


async def test_transition_cross_check_to_approved(db_session) -> None:
    analyst = await make_user(db_session, email="analyst22@test.com")
    reviewer = await make_user(db_session, email="reviewer22@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, analyst.id, status="cross_check")
    result = await transition_status(db_session, mm, "approved", reviewer.id)
    assert result.status == "approved"
    assert result.date_approved is not None
    assert result.approved_by == reviewer.id
    assert result.cross_checker_id == reviewer.id
    assert result.locked_by is None


async def test_transition_cross_check_to_draft(db_session) -> None:
    analyst = await make_user(db_session, email="analyst23@test.com")
    reviewer = await make_user(db_session, email="reviewer23@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, analyst.id, status="cross_check")
    result = await transition_status(db_session, mm, "draft", reviewer.id)
    assert result.status == "draft"
    assert result.locked_by is None


async def test_transition_invalid_draft_to_approved(db_session) -> None:
    user = await make_user(db_session, email="analyst24@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    with pytest.raises(ConflictError, match="Invalid status transition: draft -> approved"):
        await transition_status(db_session, mm, "approved", user.id)


async def test_transition_approved_to_draft_invalid(db_session) -> None:
    user = await make_user(db_session, email="analyst25@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, status="approved")
    with pytest.raises(ConflictError, match="Invalid status transition: approved -> draft"):
        await transition_status(db_session, mm, "draft", user.id)


async def test_transition_approved_to_cross_check_invalid(db_session) -> None:
    user = await make_user(db_session, email="analyst26@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, status="approved")
    with pytest.raises(ConflictError, match="Invalid status transition: approved -> cross_check"):
        await transition_status(db_session, mm, "cross_check", user.id)


async def test_transition_raises_if_locked_by_other(db_session) -> None:
    analyst = await make_user(db_session, email="analyst27@test.com")
    other = await make_user(db_session, email="other3@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(
        db_session,
        pericope.id,
        analyst.id,
        locked_by=other.id,
        locked_at=datetime.now(UTC),
    )
    with pytest.raises(AuthorizationError, match="locked by another user"):
        await transition_status(db_session, mm, "cross_check", analyst.id)


async def test_transition_same_status_invalid(db_session) -> None:
    user = await make_user(db_session, email="analyst28@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    with pytest.raises(ConflictError, match="Invalid status transition: draft -> draft"):
        await transition_status(db_session, mm, "draft", user.id)


async def test_transition_lock_holder_can_transition(db_session) -> None:
    user = await make_user(db_session, email="analyst29@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(
        db_session, pericope.id, user.id, locked_by=user.id, locked_at=datetime.now(UTC)
    )
    result = await transition_status(db_session, mm, "cross_check", user.id)
    assert result.status == "cross_check"


async def test_transition_cross_check_to_approved_clears_lock(db_session) -> None:
    analyst = await make_user(db_session, email="analyst30@test.com")
    reviewer = await make_user(db_session, email="reviewer30@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(
        db_session,
        pericope.id,
        analyst.id,
        status="cross_check",
        locked_by=reviewer.id,
        locked_at=datetime.now(UTC),
    )
    result = await transition_status(db_session, mm, "approved", reviewer.id)
    assert result.locked_by is None
    assert result.locked_at is None


async def test_lock_map_success(db_session) -> None:
    user = await make_user(db_session, email="analyst31@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    result = await lock_map(db_session, mm, user.id)
    assert result.locked_by == user.id
    assert result.locked_at is not None


async def test_lock_map_already_locked_by_self(db_session) -> None:
    user = await make_user(db_session, email="analyst32@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(
        db_session, pericope.id, user.id, locked_by=user.id, locked_at=datetime.now(UTC)
    )
    result = await lock_map(db_session, mm, user.id)
    assert result.locked_by == user.id


async def test_lock_map_raises_if_locked_by_other(db_session) -> None:
    user1 = await make_user(db_session, email="analyst33@test.com")
    user2 = await make_user(db_session, email="other4@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(
        db_session, pericope.id, user1.id, locked_by=user1.id, locked_at=datetime.now(UTC)
    )
    with pytest.raises(ConflictError, match="already locked by another user"):
        await lock_map(db_session, mm, user2.id)


async def test_lock_map_raises_if_approved(db_session) -> None:
    user = await make_user(db_session, email="analyst34@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, status="approved")
    with pytest.raises(ConflictError, match="Cannot lock an approved meaning map"):
        await lock_map(db_session, mm, user.id)


async def test_unlock_map_success(db_session) -> None:
    user = await make_user(db_session, email="analyst35@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(
        db_session, pericope.id, user.id, locked_by=user.id, locked_at=datetime.now(UTC)
    )
    result = await unlock_map(db_session, mm, user.id)
    assert result.locked_by is None
    assert result.locked_at is None


async def test_unlock_map_not_locked_returns_unchanged(db_session) -> None:
    user = await make_user(db_session, email="analyst36@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)
    result = await unlock_map(db_session, mm, user.id)
    assert result.locked_by is None


async def test_unlock_map_raises_if_locked_by_other_non_admin(db_session) -> None:
    user1 = await make_user(db_session, email="analyst37@test.com")
    user2 = await make_user(db_session, email="other5@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(
        db_session, pericope.id, user1.id, locked_by=user1.id, locked_at=datetime.now(UTC)
    )
    with pytest.raises(AuthorizationError, match="Only the lock holder or an admin can unlock"):
        await unlock_map(db_session, mm, user2.id)


async def test_unlock_map_admin_can_unlock_others(db_session) -> None:
    user1 = await make_user(db_session, email="analyst38@test.com")
    admin = await make_user(db_session, email="admin@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(
        db_session, pericope.id, user1.id, locked_by=user1.id, locked_at=datetime.now(UTC)
    )
    result = await unlock_map(db_session, mm, admin.id, is_admin=True)
    assert result.locked_by is None


async def test_lock_map_cross_check_status(db_session) -> None:
    user = await make_user(db_session, email="analyst39@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id, status="cross_check")
    result = await lock_map(db_session, mm, user.id)
    assert result.locked_by == user.id
