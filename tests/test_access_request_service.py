import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundError, RoleError
from app.db.models.auth import App
from app.services.access_request.create_access_request import create_access_request
from app.services.access_request.get_user_access_request import get_user_access_request
from app.services.access_request.list_access_requests import list_access_requests
from app.services.access_request.review_access_request import review_access_request
from app.services.authorization.has_role import has_role
from tests.baker import make_access_request, make_app, make_role, make_user

APP_KEY = "meaning-map-generator"


async def _setup_app(db):

    result = await db.execute(select(App).where(App.app_key == APP_KEY))
    app = result.scalar_one()
    role = await make_role(db, app.id, role_key="analyst", label="Analyst")
    return app, role


async def test_create_access_request_success(db_session) -> None:
    app, _ = await _setup_app(db_session)
    user = await make_user(db_session, email="new@test.com")
    req = await create_access_request(db_session, user.id, APP_KEY)
    assert req.id
    assert req.user_id == user.id
    assert req.app_id == app.id
    assert req.status == "pending"
    assert req.note is None


async def test_create_access_request_with_note(db_session) -> None:
    await _setup_app(db_session)
    user = await make_user(db_session, email="noted@test.com")
    req = await create_access_request(db_session, user.id, APP_KEY, note="Please add me")
    assert req.note == "Please add me"


async def test_create_access_request_idempotent(db_session) -> None:
    await _setup_app(db_session)
    user = await make_user(db_session, email="idem@test.com")
    first = await create_access_request(db_session, user.id, APP_KEY)
    second = await create_access_request(db_session, user.id, APP_KEY)
    assert first.id == second.id


async def test_create_access_request_invalid_app(db_session) -> None:
    user = await make_user(db_session, email="bad@test.com")
    with pytest.raises(NotFoundError, match="App not found"):
        await create_access_request(db_session, user.id, "nonexistent-app")


async def test_create_access_request_after_rejection(db_session) -> None:
    app, _ = await _setup_app(db_session)
    user = await make_user(db_session, email="rejected@test.com")
    await make_access_request(db_session, user.id, app.id, status="rejected")
    new_req = await create_access_request(db_session, user.id, APP_KEY)
    assert new_req.status == "pending"


async def test_get_user_access_request_found(db_session) -> None:
    await _setup_app(db_session)
    user = await make_user(db_session, email="get1@test.com")
    created = await create_access_request(db_session, user.id, APP_KEY)
    found = await get_user_access_request(db_session, user.id, APP_KEY)
    assert found is not None
    assert found.id == created.id


async def test_get_user_access_request_none(db_session) -> None:
    await _setup_app(db_session)
    user = await make_user(db_session, email="get2@test.com")
    found = await get_user_access_request(db_session, user.id, APP_KEY)
    assert found is None


async def test_get_user_access_request_invalid_app(db_session) -> None:
    user = await make_user(db_session, email="get3@test.com")
    with pytest.raises(NotFoundError, match="App not found"):
        await get_user_access_request(db_session, user.id, "nonexistent-app")


async def test_list_access_requests_all(db_session) -> None:
    await _setup_app(db_session)
    u1 = await make_user(db_session, email="list1@test.com")
    u2 = await make_user(db_session, email="list2@test.com")
    await create_access_request(db_session, u1.id, APP_KEY)
    await create_access_request(db_session, u2.id, APP_KEY)
    rows = await list_access_requests(db_session)
    assert len(rows) == 2
    assert all(ak == APP_KEY for _, ak in rows)


async def test_list_access_requests_filter_by_status(db_session) -> None:
    app, _ = await _setup_app(db_session)
    u1 = await make_user(db_session, email="listf1@test.com")
    u2 = await make_user(db_session, email="listf2@test.com")
    await create_access_request(db_session, u1.id, APP_KEY)
    await make_access_request(db_session, u2.id, app.id, status="rejected")
    rows = await list_access_requests(db_session, status="pending")
    assert len(rows) == 1


async def test_list_access_requests_filter_by_app_key(db_session) -> None:
    await _setup_app(db_session)
    other_app = await make_app(db_session, app_key="other-app", name="Other")
    user = await make_user(db_session, email="listapp@test.com")
    await create_access_request(db_session, user.id, APP_KEY)
    await make_access_request(db_session, user.id, other_app.id)
    rows = await list_access_requests(db_session, app_key=APP_KEY)
    assert len(rows) == 1


async def test_list_access_requests_empty(db_session) -> None:
    rows = await list_access_requests(db_session)
    assert rows == []


async def test_review_approve_assigns_analyst(db_session) -> None:
    await _setup_app(db_session)
    user = await make_user(db_session, email="approve@test.com")
    admin = await make_user(db_session, email="admin@test.com", is_platform_admin=True)
    req = await create_access_request(db_session, user.id, APP_KEY)
    reviewed = await review_access_request(db_session, admin, req.id, "approved")
    assert reviewed.status == "approved"
    assert reviewed.reviewed_by == admin.id
    assert reviewed.reviewed_at is not None
    has = await has_role(db_session, user.id, APP_KEY, "analyst")
    assert has is True


async def test_review_reject(db_session) -> None:
    await _setup_app(db_session)
    user = await make_user(db_session, email="reject@test.com")
    admin = await make_user(db_session, email="admin2@test.com", is_platform_admin=True)
    req = await create_access_request(db_session, user.id, APP_KEY)
    reviewed = await review_access_request(
        db_session, admin, req.id, "rejected", reason="Not qualified"
    )
    assert reviewed.status == "rejected"
    assert reviewed.review_reason == "Not qualified"
    has = await has_role(db_session, user.id, APP_KEY, "analyst")
    assert has is False


async def test_review_invalid_status(db_session) -> None:
    await _setup_app(db_session)
    user = await make_user(db_session, email="inv@test.com")
    admin = await make_user(db_session, email="admin3@test.com", is_platform_admin=True)
    req = await create_access_request(db_session, user.id, APP_KEY)
    with pytest.raises(RoleError, match="Status must be"):
        await review_access_request(db_session, admin, req.id, "maybe")


async def test_review_not_found(db_session) -> None:
    admin = await make_user(db_session, email="admin4@test.com", is_platform_admin=True)
    with pytest.raises(NotFoundError, match="Access request not found"):
        await review_access_request(db_session, admin, "nonexistent-id", "approved")


async def test_review_already_reviewed(db_session) -> None:
    await _setup_app(db_session)
    user = await make_user(db_session, email="already@test.com")
    admin = await make_user(db_session, email="admin5@test.com", is_platform_admin=True)
    req = await create_access_request(db_session, user.id, APP_KEY)
    await review_access_request(db_session, admin, req.id, "approved")
    with pytest.raises(RoleError, match="Request already approved"):
        await review_access_request(db_session, admin, req.id, "rejected")
