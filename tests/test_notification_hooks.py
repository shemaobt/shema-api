import pytest
from sqlalchemy import select

from app.db.models.auth import App
from app.db.models.notification import Notification
from app.services.meaning_map.add_feedback import add_feedback
from app.services.meaning_map.transition_status import transition_status
from tests.baker import make_bible_book, make_meaning_map, make_pericope, make_user


@pytest.fixture
async def mm_app(db_session):

    result = await db_session.execute(select(App).where(App.app_key == "meaning-map-generator"))
    return result.scalar_one()


async def _get_notifications(db_session, user_id: str) -> list[Notification]:
    result = await db_session.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    return list(result.scalars().all())


async def test_approve_creates_notification_for_analyst(db_session, mm_app) -> None:
    analyst = await make_user(db_session, email="hook-analyst1@test.com")
    checker = await make_user(db_session, email="hook-checker1@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id, reference="Ruth 1:1-5")
    mm = await make_meaning_map(db_session, pericope.id, analyst.id, status="cross_check")

    await transition_status(db_session, mm, "approved", checker.id)

    notifs = await _get_notifications(db_session, analyst.id)
    assert len(notifs) == 1
    assert notifs[0].event_type == "map_approved"
    assert notifs[0].title == "Your meaning map was approved"
    assert "Ruth 1:1-5" in notifs[0].body
    assert notifs[0].actor_id == checker.id
    assert notifs[0].app_id == mm_app.id


async def test_revisions_requested_creates_notification(db_session, mm_app) -> None:
    analyst = await make_user(db_session, email="hook-analyst2@test.com")
    checker = await make_user(db_session, email="hook-checker2@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id, reference="Gen 1:1-5")
    mm = await make_meaning_map(db_session, pericope.id, analyst.id, status="cross_check")

    await transition_status(db_session, mm, "draft", checker.id)

    notifs = await _get_notifications(db_session, analyst.id)
    assert len(notifs) == 1
    assert notifs[0].event_type == "revisions_requested"
    assert "Gen 1:1-5" in notifs[0].body


async def test_draft_to_crosscheck_creates_no_notification(db_session, mm_app) -> None:
    analyst = await make_user(db_session, email="hook-analyst3@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, analyst.id, status="draft")

    await transition_status(db_session, mm, "cross_check", analyst.id)

    notifs = await _get_notifications(db_session, analyst.id)
    assert len(notifs) == 0


async def test_add_feedback_creates_notification_for_analyst(db_session, mm_app) -> None:
    analyst = await make_user(db_session, email="hook-analyst4@test.com")
    checker = await make_user(db_session, email="hook-checker4@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id, reference="Exod 2:1-10")
    mm = await make_meaning_map(db_session, pericope.id, analyst.id, status="cross_check")

    await add_feedback(db_session, mm.id, "level_1.arc", checker.id, "Needs revision")

    notifs = await _get_notifications(db_session, analyst.id)
    assert len(notifs) == 1
    assert notifs[0].event_type == "feedback_added"
    assert "Exod 2:1-10" in notifs[0].body


async def test_add_feedback_no_notification_when_self(db_session, mm_app) -> None:
    analyst = await make_user(db_session, email="hook-analyst5@test.com")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, analyst.id, status="cross_check")

    await add_feedback(db_session, mm.id, "level_1.arc", analyst.id, "Self feedback")

    notifs = await _get_notifications(db_session, analyst.id)
    assert len(notifs) == 0
