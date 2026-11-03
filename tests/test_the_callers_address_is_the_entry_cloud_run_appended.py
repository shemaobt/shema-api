from __future__ import annotations

import httpx
import pytest
from fastapi import APIRouter
from httpx import ASGITransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.core.config import get_settings
from app.core.database import get_db
from app.core.proxy_headers import CloudRunProxyHeadersMiddleware
from app.core.rate_limit import limiter
from app.main import create_app

TEAM_REPORT_LIMIT = 60
TEAM_REPORT = "/probe"
PROXY_APPENDED = "203.0.113.7"
ANOTHER_CALLER = "198.51.100.9"


probe_router = APIRouter()


@probe_router.get("/probe")
@limiter.limit("60/minute")
async def probe(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


def _app(monkeypatch, db_session, k_service):
    if k_service is None:
        monkeypatch.delenv("K_SERVICE", raising=False)
    else:
        monkeypatch.setenv("K_SERVICE", k_service)
    get_settings.cache_clear()
    app = create_app()

    app.include_router(probe_router)

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    return app


def _client(app):
    return httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    )


@pytest.fixture()
async def on_cloud_run(monkeypatch, db_session):
    async with _client(_app(monkeypatch, db_session, "tripod-backend")) as c:
        yield c
    monkeypatch.delenv("K_SERVICE", raising=False)
    get_settings.cache_clear()


@pytest.fixture()
async def off_cloud_run(monkeypatch, db_session):
    async with _client(_app(monkeypatch, db_session, None)) as c:
        yield c
    get_settings.cache_clear()


async def _exhaust(client, forwarded_for):
    for i in range(TEAM_REPORT_LIMIT):
        headers = {"X-Forwarded-For": forwarded_for(i)} if forwarded_for else {}
        r = await client.get(TEAM_REPORT, headers=headers)
        assert r.status_code == 200


async def _status(client, forwarded_for=None):
    headers = {"X-Forwarded-For": forwarded_for} if forwarded_for is not None else {}
    return (await client.get(TEAM_REPORT, headers=headers)).status_code


async def test_two_requests_from_one_socket_with_different_forwarded_for_values_share_one_bucket(
    off_cloud_run,
):
    await _exhaust(off_cloud_run, lambda i: f"192.0.2.{i}")

    assert await _status(off_cloud_run, "192.0.2.200") == 429


async def test_on_cloud_run_a_client_written_entry_never_moves_the_caller_to_another_bucket(
    on_cloud_run,
):
    await _exhaust(on_cloud_run, lambda i: f"192.0.2.{i}, {PROXY_APPENDED}")

    assert await _status(on_cloud_run, f"192.0.2.200, {PROXY_APPENDED}") == 429


async def test_on_cloud_run_the_limit_keys_on_the_address_the_proxy_appended(on_cloud_run):
    await _exhaust(on_cloud_run, lambda i: f"192.0.2.{i}, {PROXY_APPENDED}")

    assert await _status(on_cloud_run, f"192.0.2.1, {ANOTHER_CALLER}") == 200
    assert await _status(on_cloud_run, f"192.0.2.1, {PROXY_APPENDED}") == 429


async def test_on_cloud_run_a_request_with_no_forwarded_for_keys_on_the_socket(on_cloud_run):
    await _exhaust(on_cloud_run, None)

    assert await _status(on_cloud_run) == 429
    assert await _status(on_cloud_run, ANOTHER_CALLER) == 200


@pytest.mark.parametrize("empty", ["", ",", " , "])
async def test_on_cloud_run_a_forwarded_for_with_no_entry_keeps_the_socket_as_the_caller(empty):
    async def whoami(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.client.host)

    app = Starlette(routes=[Route("/", whoami)])
    app.add_middleware(CloudRunProxyHeadersMiddleware)
    transport = ASGITransport(app=app, client=("127.0.0.1", 123))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/", headers={"X-Forwarded-For": empty})

    assert r.text == "127.0.0.1"


async def test_off_cloud_run_the_forwarded_for_header_is_never_read(off_cloud_run):
    await _exhaust(off_cloud_run, lambda i: PROXY_APPENDED)

    assert await _status(off_cloud_run, ANOTHER_CALLER) == 429


async def test_on_cloud_run_the_request_keeps_the_scheme_the_proxy_forwarded(on_cloud_run):
    r = await on_cloud_run.get(TEAM_REPORT + "/", headers={"X-Forwarded-Proto": "https"})

    assert r.status_code == 307
    assert r.headers["location"].startswith("https://test/probe")


async def test_off_cloud_run_the_forwarded_scheme_is_not_taken(off_cloud_run):
    r = await off_cloud_run.get(TEAM_REPORT + "/", headers={"X-Forwarded-Proto": "https"})

    assert r.status_code == 307
    assert r.headers["location"].startswith("http://test/probe")


async def _through_middleware(raw_headers):
    seen = {}

    async def app(scope, receive, send):
        seen.update(client=scope["client"], scheme=scope["scheme"])

    scope = {
        "type": "http",
        "scheme": "http",
        "client": ("127.0.0.1", 123),
        "headers": [(k.encode(), v.encode()) for k, v in raw_headers],
    }
    await CloudRunProxyHeadersMiddleware(app)(scope, None, None)
    return seen


async def test_on_cloud_run_a_request_with_two_forwarded_for_lines_keeps_the_socket_as_the_caller():
    seen = await _through_middleware(
        [("x-forwarded-for", "192.0.2.1, 203.0.113.7"), ("x-forwarded-for", "192.0.2.2")]
    )

    assert seen["client"] == ("127.0.0.1", 123)


async def test_on_cloud_run_a_request_with_two_forwarded_proto_lines_takes_the_last():
    seen = await _through_middleware(
        [("x-forwarded-proto", "http"), ("x-forwarded-proto", "https")]
    )

    assert seen["scheme"] == "https"
