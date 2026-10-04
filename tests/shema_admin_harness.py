"""What the cases about the Admin's surface share — a client, the routes, the accounts.

``test_shema/test_admin_gate.py``, ``test_admin_grants.py`` and ``test_admin_invites.py`` drive
the surface, and ``test_pending_projects.py`` signs the same Admin in to confirm what an
approval filed. Not in ``tests/test_shema/conftest.py`` on purpose: that file is every Shemá
test's, and several branches edit it at once. The client here mounts what those tests need and
the shared one does not: the form's invitation routes, where an invite is accepted, and
``/api/roles``, the raw tool the surface closes for the two apps.

Builders and constants only. ``surface_client`` is a context manager a case opens, not a
fixture, so nothing here has to travel as one.

**The Admin of these tests holds ``admin`` in both apps and is not an installation admin.**
An installation admin passes every guard, so a refusal proved with one proves nothing, and an
Admin holding the role in one app only is a case of its own
(``test_shema/test_admin_gate.py::test_an_admin_held_only_in_the_form_is_refused``).

Addresses are ``@shema.example``: ``EmailStr`` refuses the reserved ``.test`` TLD, and the
invitation routes validate with it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from httpx import ASGITransport

from tests.baker import make_user
from tests.test_shema.conftest import PREFIX, auth_header, grant

ACCESS = f"{PREFIX}/access"
PEOPLE = f"{ACCESS}/people"
GRANTS = f"{ACCESS}/grants"
REVOKE = f"{ACCESS}/grants/revoke"
INVITES = f"{ACCESS}/invites"
WITHDRAW = f"{ACCESS}/invites/revoke"
CHANGES = f"{ACCESS}/changes"
FORM_INVITES = "/api/resource-requests/access/invites"

PME_URL = "https://pme.shema.example"
FORM_URL = "https://form.shema.example"


@asynccontextmanager
async def surface_client(db_session) -> AsyncIterator[httpx.AsyncClient]:
    """The module's real router, auth, ``/api/roles`` and the form's invitation routes."""
    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from app.api.auth import router as auth_router
    from app.api.resource_requests.access import router as form_access_router
    from app.api.roles import router as roles_router
    from app.api.shema import router as module_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.core.rate_limit import limiter

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(module_router, prefix=PREFIX)
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(roles_router, prefix="/api/roles")
    app.include_router(form_access_router, prefix="/api/resource-requests/access")
    register_exception_handlers(app)

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def give_urls(db_session, shema_app, form_app) -> None:
    """Two different addresses, so a link built off the wrong app cannot pass for the right one."""
    shema_app.app_url = PME_URL
    form_app.app_url = FORM_URL
    await db_session.commit()


async def make_admin(db_session, shema_app, form_app, email: str = "admin@shema.example"):
    """The PME's Admin: ``admin`` in both apps, as granting it writes it."""
    admin = await make_user(db_session, email=email, display_name="The Admin")
    await grant(db_session, admin, shema_app, "admin")
    await grant(db_session, admin, form_app, "admin")
    return admin, await auth_header(db_session, admin)


async def make_account(db_session, email: str, *grants):
    """A plain account, with ``(app, role)`` grants written directly."""
    account = await make_user(db_session, email=email, display_name=None)
    for app, role in grants:
        await grant(db_session, account, app, role)
    return account
