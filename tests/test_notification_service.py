import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.db.models.notification import NotificationMeaningMapDetail
from app.services.notifications.create_notification import create_notification
from app.services.notifications.list_notifications import list_notifications
from app.services.notifications.mark_all_as_read import mark_all_as_read
from app.services.notifications.mark_as_read import mark_as_read
from app.services.notifications.unread_count import unread_count
from tests.baker import make_app, make_bible_book, make_meaning_map, make_pericope, make_user


async def test_create_notification_basic(db_session) -> None:
    user = await make_user(db_session, email="notif-user1@test.com")
    app = await make_app(db_session, app_key="notif-app-1")

    notif = await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="map_approved",
        title="Your map was approved",
        body="Your meaning map for Ruth 1:1-5 was approved.",
    )

    assert notif.id is not None
    assert notif.user_id == user.id
    assert notif.app_id == app.id
    assert notif.event_type == "map_approved"
    assert notif.title == "Your map was approved"
    assert notif.is_read is False


async def test_create_notification_with_actor(db_session) -> None:
    user = await make_user(db_session, email="notif-user2@test.com")
    actor = await make_user(db_session, email="notif-actor@test.com")
    app = await make_app(db_session, app_key="notif-app-2")

    notif = await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="feedback_added",
        title="New feedback",
        body="Feedback was added.",
        actor_id=actor.id,
    )

    assert notif.actor_id == actor.id


async def test_create_notification_with_mm_detail(db_session) -> None:
    user = await make_user(db_session, email="notif-user3@test.com")
    app = await make_app(db_session, app_key="notif-app-3")
    book = await make_bible_book(db_session)
    pericope = await make_pericope(db_session, book.id)
    mm = await make_meaning_map(db_session, pericope.id, user.id)

    notif = await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="map_approved",
        title="Approved",
        body="Approved.",
        related_map_id=mm.id,
        pericope_reference="Ruth 1:1-5",
    )

    result = await db_session.execute(
        select(NotificationMeaningMapDetail).where(
            NotificationMeaningMapDetail.notification_id == notif.id
        )
    )
    detail = result.scalar_one()
    assert detail.related_map_id == mm.id
    assert detail.pericope_reference == "Ruth 1:1-5"


async def test_create_notification_without_mm_detail_no_child_row(db_session) -> None:
    user = await make_user(db_session, email="notif-user4@test.com")
    app = await make_app(db_session, app_key="notif-app-4")

    notif = await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="generic",
        title="Hello",
        body="World",
    )

    result = await db_session.execute(
        select(NotificationMeaningMapDetail).where(
            NotificationMeaningMapDetail.notification_id == notif.id
        )
    )
    assert result.scalar_one_or_none() is None


async def test_list_notifications_returns_all(db_session) -> None:
    user = await make_user(db_session, email="notif-user5@test.com")
    app = await make_app(db_session, app_key="notif-app-5")

    n1 = await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="e1",
        title="First",
        body="First",
    )
    n2 = await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="e2",
        title="Second",
        body="Second",
    )

    results = await list_notifications(db_session, user.id, app.id)
    result_ids = {r.id for r in results}
    assert n1.id in result_ids
    assert n2.id in result_ids


async def test_list_notifications_unread_only(db_session) -> None:
    user = await make_user(db_session, email="notif-user6@test.com")
    app = await make_app(db_session, app_key="notif-app-6")

    n1 = await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="e1",
        title="Read",
        body="Read",
    )
    await mark_as_read(db_session, n1.id, user.id)
    await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="e2",
        title="Unread",
        body="Unread",
    )

    results = await list_notifications(db_session, user.id, app.id, unread_only=True)
    assert len(results) == 1
    assert results[0].title == "Unread"


async def test_list_notifications_respects_limit(db_session) -> None:
    user = await make_user(db_session, email="notif-user7@test.com")
    app = await make_app(db_session, app_key="notif-app-7")

    for i in range(5):
        await create_notification(
            db_session,
            user_id=user.id,
            app_id=app.id,
            event_type="e",
            title=f"N{i}",
            body=f"B{i}",
        )

    results = await list_notifications(db_session, user.id, app.id, limit=3)
    assert len(results) == 3


async def test_list_notifications_filters_by_app(db_session) -> None:
    user = await make_user(db_session, email="notif-user8@test.com")
    app1 = await make_app(db_session, app_key="notif-app-8a")
    app2 = await make_app(db_session, app_key="notif-app-8b")

    await create_notification(
        db_session,
        user_id=user.id,
        app_id=app1.id,
        event_type="e",
        title="App1",
        body="App1",
    )
    await create_notification(
        db_session,
        user_id=user.id,
        app_id=app2.id,
        event_type="e",
        title="App2",
        body="App2",
    )

    results = await list_notifications(db_session, user.id, app1.id)
    assert all(r.app_id == app1.id for r in results)


async def test_unread_count_zero_when_none(db_session) -> None:
    user = await make_user(db_session, email="notif-user9@test.com")
    app = await make_app(db_session, app_key="notif-app-9")

    count = await unread_count(db_session, user.id, app.id)
    assert count == 0


async def test_unread_count_increments(db_session) -> None:
    user = await make_user(db_session, email="notif-user10@test.com")
    app = await make_app(db_session, app_key="notif-app-10")

    await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="e",
        title="T",
        body="B",
    )
    await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="e",
        title="T2",
        body="B2",
    )

    count = await unread_count(db_session, user.id, app.id)
    assert count == 2


async def test_unread_count_decrements_after_mark_read(db_session) -> None:
    user = await make_user(db_session, email="notif-user11@test.com")
    app = await make_app(db_session, app_key="notif-app-11")

    n = await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="e",
        title="T",
        body="B",
    )
    await mark_as_read(db_session, n.id, user.id)

    count = await unread_count(db_session, user.id, app.id)
    assert count == 0


async def test_mark_as_read_success(db_session) -> None:
    user = await make_user(db_session, email="notif-user12@test.com")
    app = await make_app(db_session, app_key="notif-app-12")

    n = await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="e",
        title="T",
        body="B",
    )
    assert n.is_read is False

    updated = await mark_as_read(db_session, n.id, user.id)
    assert updated.is_read is True


async def test_mark_as_read_wrong_user_raises(db_session) -> None:
    user = await make_user(db_session, email="notif-user13@test.com")
    other = await make_user(db_session, email="notif-other@test.com")
    app = await make_app(db_session, app_key="notif-app-13")

    n = await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="e",
        title="T",
        body="B",
    )

    with pytest.raises(NotFoundError):
        await mark_as_read(db_session, n.id, other.id)


async def test_mark_as_read_nonexistent_raises(db_session) -> None:
    user = await make_user(db_session, email="notif-user14@test.com")

    with pytest.raises(NotFoundError):
        await mark_as_read(db_session, "nonexistent-id", user.id)


async def test_mark_all_as_read_success(db_session) -> None:
    user = await make_user(db_session, email="notif-user15@test.com")
    app = await make_app(db_session, app_key="notif-app-15")

    await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="e",
        title="T1",
        body="B1",
    )
    await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="e",
        title="T2",
        body="B2",
    )

    count = await mark_all_as_read(db_session, user.id)
    assert count == 2

    remaining = await unread_count(db_session, user.id, app.id)
    assert remaining == 0


async def test_mark_all_as_read_idempotent(db_session) -> None:
    user = await make_user(db_session, email="notif-user16@test.com")
    app = await make_app(db_session, app_key="notif-app-16")

    await create_notification(
        db_session,
        user_id=user.id,
        app_id=app.id,
        event_type="e",
        title="T",
        body="B",
    )

    await mark_all_as_read(db_session, user.id)
    count = await mark_all_as_read(db_session, user.id)
    assert count == 0
