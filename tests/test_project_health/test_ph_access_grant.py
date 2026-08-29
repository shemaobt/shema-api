import pytest

from app.services.access_request._default_roles import default_role_for
from app.services.access_request.review_access_request import review_access_request
from app.services.authorization.has_role import has_role
from app.services.authorization.list_roles import list_roles
from tests.baker import make_access_request, make_user


def test_project_health_resolves_to_a_role_it_defines() -> None:
    """``project-health`` defines ``user`` and ``admin`` — never ``analyst``.

    Without an entry in ``DEFAULT_ROLE_BY_APP_KEY`` it fell through to the ``analyst``
    fallback, so approval could not succeed no matter who ran it.
    """
    assert default_role_for("project-health") == "user"


@pytest.mark.asyncio
async def test_review_approve_grants_user_role_for_project_health(db_session, ph_app) -> None:
    """The full request→approve→access path works for Project Health.

    This is the path that had been failing since the app launched in May 2026: approval
    resolved the ``analyst`` fallback, ``grant_app_role`` could not find that role on
    ``project-health``, and the request raised ``RoleError`` instead of granting anything.
    The only account that ever held access was written directly into ``user_app_roles`` by
    ``20260518_0002_backfill_ph_bootstrap_admin`` — the grant in ``20260518_0001`` skips
    silently when the bootstrap user does not yet exist, which in production it did not.
    """
    requester = await make_user(db_session, email="ph_req@test.com")
    admin = await make_user(db_session, email="ph_admin@test.com", is_platform_admin=True)
    access_request = await make_access_request(db_session, requester.id, ph_app.id)

    reviewed = await review_access_request(db_session, admin, access_request.id, status="approved")

    assert reviewed.status == "approved"
    assert await list_roles(db_session, requester.id, "project-health") == [
        ("project-health", "user")
    ]
    assert await has_role(db_session, requester.id, "project-health", "user") is True
