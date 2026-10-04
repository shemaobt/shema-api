"""No answer of this module is kept by a cache — OBT-555, read off the application as built.

Every read under ``/api/shema`` is built for its reader: the scope, the reader of OBT-528, the role,
and on the two unauthenticated routes whoever holds a link. A body a cache stored is therefore
somebody else's body — another coordinator's projects, an intercessor's raw contact, the intake
form of a link revoked since — so every one of them says ``private, no-store``.

Two nets, and what each catches that the other does not:

1. **The wiring.** Every route the application mounts under the prefix, whatever its method, passes
   through :data:`~app.api.shema._deps.NO_STORE` — so a route added tomorrow inherits the header
   the way it inherits the app gate, without its author knowing the rule exists.
2. **The wire.** Every ``GET`` is called and its answer read. The dependency writes the header on
   the ``Response`` FastAPI builds from a returned model, and a handler that returns a ``Response``
   of its own is answered with that object instead — so the first net passes for it and only this
   one sees whether it wrote the header itself. Each call has to reach the answer (a 2xx): a route
   refused on the way would carry no reader's body and prove nothing, and one with a path
   parameter nobody gave a value to below is refused, which is what makes adding it a line here.

Called through ``create_app()`` and not through the module's test application, so the header is
the one that leaves the server, after every middleware ``app/main.py`` stacks on it. The account
is an installation admin because it passes every guard and the claim is about the answer, not
about who may have it: who may is each route's own file.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport
from sqlalchemy import select

from app.api.shema._deps import NO_STORE
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_form import ShemaSubmission
from app.main import create_app
from app.services.shema import issue_exit_link
from tests.baker import make_user
from tests.shema_harness import UNAUTHENTICATED_PATHS, reaches
from tests.test_shema.conftest import (
    PREFIX,
    auth_header,
    make_intercessor,
    make_shema_project,
)

#: What the module's answers say, as the console's other tests read it off the wire — the literal
#: and not the constant, so a constant that changed would fail here rather than agree with itself.
NO_STORE_HEADER = "private, no-store"


def _shema_routes(app) -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith(PREFIX)
    ]


def test_every_route_under_the_module_passes_through_no_store() -> None:
    """The rule is a property of the module's router, not of each handler remembering it."""
    routes = _shema_routes(create_app())
    outside = [
        f"{sorted(route.methods)} {route.path}"
        for route in routes
        if not reaches(route.dependant, NO_STORE.dependency)
    ]

    assert routes, f"no route mounted under {PREFIX}"
    assert outside == [], f"routes under {PREFIX} that skip the no-store dependency: {outside}"


@pytest.fixture()
async def server(db_session):
    """The application ``app/main.py`` builds, on the test's database session."""
    from app.core.database import get_db

    app = create_app()

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture()
async def urls(db_session, server, shema_app, form_app) -> tuple[dict[str, str], dict[str, str]]:
    """A concrete URL for every ``GET`` that cannot be called as its template, and the headers.

    Everything a path parameter names is made through the real routes or the module's services,
    as the files that own them make it: a project, an intake link and an answer through it, a
    person in the prayer network and the exit link a send would carry to them.
    """
    admin = await make_user(db_session, email="cache@shema.test", is_platform_admin=True)
    headers = await auth_header(db_session, admin)

    project_id = str(uuid.uuid4())
    await make_shema_project(
        db_session,
        project_id=project_id,
        region_key=ShemaRegionKey.SOUTH_AMERICA,
        language_name="Lingua Cache",
    )

    minted = await server.post(
        f"{PREFIX}/intake-links", json={"projectId": project_id}, headers=headers
    )
    assert minted.status_code == 201, minted.text
    token = minted.json()["token"]
    answered = await server.post(
        f"{PREFIX}/intake/{token}",
        json={"definitionVersion": 1, "answers": {"submittedBy": "Kuaray", "period": "2026-09"}},
    )
    assert answered.status_code == 202, answered.text
    submission_id = (await db_session.execute(select(ShemaSubmission.id))).scalar_one()

    person = await make_intercessor(server, headers, contact="pessoa@example.test")
    exit_token = await issue_exit_link(db_session, person["id"])

    concrete = {
        f"{PREFIX}/projects/{{project_id}}": f"{PREFIX}/projects/{project_id}",
        f"{PREFIX}/projects/{{project_id}}/members": f"{PREFIX}/projects/{project_id}/members",
        f"{PREFIX}/projects/{{project_id}}/health-assessments": (
            f"{PREFIX}/projects/{project_id}/health-assessments"
        ),
        f"{PREFIX}/forms/submissions/{{submission_id}}": (
            f"{PREFIX}/forms/submissions/{submission_id}"
        ),
        f"{PREFIX}/intake/{{token}}": f"{PREFIX}/intake/{token}",
        f"{PREFIX}/intercessors/leave/{{token}}": f"{PREFIX}/intercessors/leave/{exit_token}",
        f"{PREFIX}/prayer/intercessors/{{intercessor_id}}/contact": (
            f"{PREFIX}/prayer/intercessors/{person['id']}/contact"
        ),
        f"{PREFIX}/regions/{{region_key}}/team": (
            f"{PREFIX}/regions/{ShemaRegionKey.SOUTH_AMERICA.value}/team"
        ),
        f"{PREFIX}/eten/report": f"{PREFIX}/eten/report?year={datetime.now(UTC).year}",
        f"{PREFIX}/export/projects": f"{PREFIX}/export/projects?format=json",
        f"{PREFIX}/access/people": f"{PREFIX}/access/people?email={admin.email}",
    }
    return concrete, headers


async def test_every_get_under_the_module_answers_private_no_store(server, urls) -> None:
    """**The DoD**, route by route: every ``GET`` the application serves under the prefix answers
    a reader's body that no cache may keep. The two link routes are called with no
    ``Authorization`` at all, as the leader and the intercessor call them — the case where a
    shared cache would be allowed to store the answer."""
    concrete, headers = urls
    gets = sorted(
        route.path for route in _shema_routes(create_app()) if "GET" in (route.methods or ())
    )

    failures = []
    for path in gets:
        bearer = None if path in UNAUTHENTICATED_PATHS else headers
        res = await server.get(concrete.get(path, path), headers=bearer)
        if not res.is_success:
            failures.append(f"{path}: {res.status_code}, the call never reached the answer")
        elif res.headers.get("cache-control") != NO_STORE_HEADER:
            failures.append(f"{path}: Cache-Control {res.headers.get('cache-control')!r}")

    assert gets, f"no GET mounted under {PREFIX}"
    assert failures == [], "\n".join(failures)
