"""No answer of this module is kept by a cache — OBT-689 (A-03 of INT-12), read off the wire.

Every answer under ``/api/resource-requests`` is built for its reader: the request's document,
the board, a project's cards, the trail, the evaluation, the link session. A body a browser or
a proxy stored is therefore the next reader's body, so every one of them says
``private, no-store`` — the errors too, because a 404 one reader got, cached over another's 200,
is still the wrong body at the wrong screen.

Three nets:

1. **The wiring.** Every route the application mounts under the prefix is one the middleware
   covers, and the middleware is on the application ``app/main.py`` builds — so a route added
   tomorrow inherits the header without its author knowing the rule exists.
2. **The wire, every route.** Every route under the prefix, whatever its method, is called with
   no session and a made-up id, and whatever answers — 401, 404, 405, 422 — carries the header.
   This is the sweep that fails the day a route escapes the mechanism.
3. **The wire, the readers' answers.** The representative 200s the finding named, each read by
   the account that may read it, and the four refusals the module answers most, each built by
   an exception handler the Shemá module's ``Depends`` never reaches.

Called through ``create_app()`` and not through the module's test application, so the header is
the one that leaves the server, after every middleware ``app/main.py`` stacks on it.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import FastAPI, Response
from fastapi.routing import APIRoute
from httpx import ASGITransport

from app.api.resource_requests._no_store import PREFIX, NoStoreUnderPrefix, covers
from app.core.rate_limit import limiter
from app.main import create_app
from tests.baker import make_user
from tests.resource_request_harness import (
    REQUESTS,
    as_mesa,
    as_team,
    create,
    holder,
    put_evaluation,
    submitted_request,
)
from tests.test_resource_requests.conftest import auth_header, grant, own_project_id

#: What the module's answers say, as a browser reads it — the literal and not the constant, so a
#: constant that changed would fail here rather than agree with itself.
NO_STORE_HEADER = "private, no-store"


def _module_routes(app: FastAPI) -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith(PREFIX)
    ]


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


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


# ——— the wiring ——————————————————————————————————————————————————————————————————


def test_the_middleware_is_on_the_application_and_covers_every_route_of_the_module() -> None:
    """The rule is a property of the application, not of each handler remembering it."""
    app = create_app()
    routes = _module_routes(app)
    outside = [route.path for route in routes if not covers(route.path)]

    assert any(m.cls is NoStoreUnderPrefix for m in app.user_middleware), "not mounted"
    assert routes, f"no route mounted under {PREFIX}"
    assert outside == [], f"routes under {PREFIX} the middleware does not cover: {outside}"
    # The access doors are mounted by a second `include_router`, under the same prefix.
    assert f"{PREFIX}/access/invites/{{token}}" in {route.path for route in routes}


def test_covers_is_the_prefix_as_a_path_segment_and_not_as_a_string() -> None:
    assert covers(PREFIX)
    assert covers(f"{PREFIX}/requests/board")
    assert not covers(f"{PREFIX}-outro/requests")
    assert not covers("/api/shema/projects")


# ——— the wire, every route ———————————————————————————————————————————————————————


async def test_every_route_under_the_prefix_answers_no_store_whatever_the_answer(server) -> None:
    """The sweep: each route, each method, with no session and ids nobody issued. Nothing here
    reaches a 200, and that is the point — the refusals are the answers a ``Depends`` on the
    router would never reach."""
    made_up = str(uuid.uuid4())
    failures = []
    for route in _module_routes(create_app()):
        path = route.path
        for name in route.param_convertors:
            path = path.replace(f"{{{name}}}", made_up)
        for method in sorted(route.methods or ()):
            res = await server.request(method, path)
            if res.headers.get("cache-control") != NO_STORE_HEADER:
                failures.append(
                    f"{method} {route.path}: {res.status_code}, "
                    f"Cache-Control {res.headers.get('cache-control')!r}"
                )
    assert failures == [], "\n".join(failures)


# ——— the wire, the readers' answers ———————————————————————————————————————————————


async def test_the_readers_answers_carry_the_header(db_session, server, rrf_app, shema_app) -> None:
    """The 200s the finding measured without the header, each read by who may read it."""
    member = await make_user(db_session, email="equipe-cache@rr.test")
    await grant(db_session, member, rrf_app, "equipe")
    team = await auth_header(db_session, member)
    mesa = await as_mesa(db_session, rrf_app)
    sent = await submitted_request(server, team)
    saved = await put_evaluation(server, mesa, sent["id"])
    assert saved.status_code == 200, saved.text
    _admin, link, link_session = await holder(db_session, server)

    reads = {
        f"{REQUESTS}/board": mesa,
        f"{REQUESTS}/cards": team,
        f"{REQUESTS}/{sent['id']}": team,
        f"{REQUESTS}/{sent['id']}/history": team,
        f"{REQUESTS}/{sent['id']}/evaluation": mesa,
        f"{REQUESTS}/{sent['id']}/status": team,
        f"{PREFIX}/projects/{own_project_id(member)}/requests": mesa,
        f"{PREFIX}/me": team,
        f"{PREFIX}/funds": mesa,
        f"{PREFIX}/link/{link['token']}": None,
        REQUESTS: link_session,
    }
    failures = []
    for url, headers in reads.items():
        res = await server.get(url, headers=headers)
        if res.status_code != 200:
            failures.append(f"{url}: {res.status_code}, the call never reached the answer")
        elif res.headers.get("cache-control") != NO_STORE_HEADER:
            failures.append(f"{url}: Cache-Control {res.headers.get('cache-control')!r}")
    assert failures == [], "\n".join(failures)


async def test_the_refusals_carry_the_header_too(db_session, server, rrf_app) -> None:
    """401 with no session, 403 without the capability, 404 for a request that is not there,
    409 for a second open instance and 422 for a body the model refuses — each one built by an
    exception handler, which is where a router dependency stops."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    await create(server, team)

    answers = [
        (await server.get(f"{REQUESTS}/board"), 401),
        (await server.get(f"{REQUESTS}/board", headers=team), 403),
        (await server.get(f"{REQUESTS}/{uuid.uuid4()}", headers=mesa), 404),
        (await server.post(REQUESTS, json={"request_type": "traducao"}, headers=team), 409),
        (await server.post(REQUESTS, json={"request_type": "poesia"}, headers=team), 422),
        (
            await server.post(
                f"{PREFIX}/link/{uuid.uuid4()}/verify", json={"code": "000000"}, headers=None
            ),
            404,
        ),
    ]
    for res, expected in answers:
        assert res.status_code == expected, res.text
        assert res.headers.get("cache-control") == NO_STORE_HEADER, res.request.url


# ——— the middleware on its own ———————————————————————————————————————————————————


@pytest.fixture()
async def tiny():
    """Two routes under the prefix — one stating its own freshness — and one outside it."""
    app = FastAPI()

    @app.get(f"{PREFIX}/own")
    async def own(response: Response) -> dict[str, str]:
        response.headers["Cache-Control"] = "no-cache"
        return {"ok": "own"}

    @app.get(f"{PREFIX}/plain")
    async def plain() -> dict[str, str]:
        return {"ok": "plain"}

    @app.get("/api/elsewhere")
    async def elsewhere() -> dict[str, str]:
        return {"ok": "elsewhere"}

    app.add_middleware(NoStoreUnderPrefix)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_a_route_that_states_its_own_freshness_keeps_it(tiny) -> None:
    """``setdefault``, never overwrite: the exception the DoD asks to be listed — an attachment
    one day served with a freshness of its own — needs no change here to keep what it wrote."""
    assert (await tiny.get(f"{PREFIX}/own")).headers["cache-control"] == "no-cache"
    assert (await tiny.get(f"{PREFIX}/plain")).headers["cache-control"] == NO_STORE_HEADER


async def test_paths_outside_the_prefix_are_left_alone(tiny) -> None:
    """``app/main.py`` is every application's; the rule is this module's."""
    assert "cache-control" not in (await tiny.get("/api/elsewhere")).headers
