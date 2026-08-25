"""ENG-448 — the credential is never handed back, in a body or in a log line.

A credential that appears in a log is a credential that outlives the request, in a place
nobody revokes: log sinks are copied, shipped, and read by people who were never given the
device. The same string in an error body is worse, because it goes back over the wire.

The enumeration is read off the mounted router, not written here. A list of route names
would be written from the same memory that forgets the new route, and the route nobody
remembered is exactly the one that leaks — so the set is derived, and a case below fails if
it ever comes back empty. An audit over nothing passes over nothing.

Both directions are exercised, because they fail differently. A credential that is *not
recognised* travels the refusal path, where a well-meant "invalid credential: abc123" is the
easiest mistake in the file. A credential that *is* recognised travels the success path,
where the leak would be a response model that carries the row's own column.
"""

import logging

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.enums import ProjectRole
from app.services.device import claim_device_as_facilitator, create_device
from tests.baker import make_language, make_project, make_project_user_access, make_user

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"

#: A credential-shaped string that matches no device. Distinctive enough that finding it
#: anywhere is unambiguous — no substring of a uuid or a path could be mistaken for it.
UNRECOGNISED = "cafeb0ba" * 8

_PLACEHOLDER = "algum-id"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _dependency_calls(dependant) -> set:
    calls = {dependant.call}
    for sub in dependant.dependencies:
        calls |= _dependency_calls(sub)
    return calls


def room_app_routes() -> list:
    """Every mounted route a tablet can reach, in path order.

    Identified by the room's own gates appearing in the route's dependency tree. Renaming a
    gate without updating this set would silently empty it, which is what
    ``test_the_audit_is_not_empty`` is here to catch.
    """
    from app.api.internalization_room import _deps
    from app.main import app

    gates = {_deps.require_room_caller, _deps.require_device}
    return sorted(
        (
            route
            for route in app.routes
            if getattr(route, "dependant", None) is not None
            and gates & _dependency_calls(route.dependant)
        ),
        key=lambda route: (route.path, sorted(route.methods)),
    )


def _exercisable(route) -> list[tuple[str, str]]:
    """(method, concrete path) for each method the route answers."""
    path = route.path
    while "{" in path:
        head, _, rest = path.partition("{")
        _, _, tail = rest.partition("}")
        path = f"{head}{_PLACEHOLDER}{tail}"
    return [(method, path) for method in sorted(route.methods - {"HEAD", "OPTIONS"})]


async def a_credential_that_works(db: AsyncSession) -> str:
    user = await make_user(db, email="fac@example.com")
    language = await make_language(db, name="Lang", code="fac")
    project = await make_project(db, language.id, name="Team")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    minted = await create_device(db)
    claimed = await claim_device_as_facilitator(
        db, user=user, code=minted.claim_code, project_id=project.id
    )
    return claimed.credential


def test_the_audit_is_not_empty() -> None:
    """The guard on every other case in this file.

    Every assertion here is "the credential is absent from these responses". Over an empty
    set that is true and says nothing, and it would go green exactly when the gate is
    renamed — the moment the audit stops watching anything.
    """
    assert room_app_routes(), (
        "nenhuma rota da sala foi encontrada: os portoes mudaram de nome e esta auditoria "
        "parou de olhar para qualquer coisa"
    )


async def test_no_room_route_echoes_an_unrecognised_credential(client, caplog) -> None:
    """The refusal path, over every room route."""
    caplog.set_level(logging.DEBUG)
    echoed = []

    for route in room_app_routes():
        for method, path in _exercisable(route):
            answer = await client.request(
                method, path, headers={DEVICE_CREDENTIAL_HEADER: UNRECOGNISED}
            )
            if UNRECOGNISED in answer.text:
                echoed.append((method, path))

    logged = [r.getMessage() for r in caplog.records if UNRECOGNISED in r.getMessage()]

    assert not echoed, f"estas rotas devolveram a credencial no corpo: {echoed}"
    assert not logged, f"a credencial foi parar no log: {logged}"


async def test_no_room_route_echoes_a_credential_that_works(client, db_session, caplog) -> None:
    """The success path, over every room route.

    A recognised credential resolves a device row, and the row is what a response model is
    built from — so this is where a column named like a credential would come back out.
    """
    caplog.set_level(logging.DEBUG)
    credential = await a_credential_that_works(db_session)
    echoed = []

    for route in room_app_routes():
        for method, path in _exercisable(route):
            answer = await client.request(
                method, path, headers={DEVICE_CREDENTIAL_HEADER: credential}
            )
            if credential in answer.text:
                echoed.append((method, path))

    logged = [r.getMessage() for r in caplog.records if credential in r.getMessage()]

    assert not echoed, f"estas rotas devolveram a credencial no corpo: {echoed}"
    assert not logged, f"a credencial foi parar no log: {logged}"
