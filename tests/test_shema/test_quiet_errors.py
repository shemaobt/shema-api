"""A validation error under ``/api/shema`` says nothing about the value it refused (OBT-556).

Two halves of one rule. FastAPI's 422 hands each field error's ``input`` back to whoever sent
it, and an unexpected Pydantic error is logged — by ``handle_unexpected`` and, after it, by the
server — with ``input_value=`` in its message. Both are closed for this module's routes, and for
nobody else's: every other application keeps the 422 its clients read.

The canary is a string no route of the module could produce on its own, so finding it anywhere
— the body, the raised exception, the log — is the value having travelled.
"""

from __future__ import annotations

import logging
import traceback
import uuid

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from app.api.shema._routing import KEPT_ERROR_KEYS, ShemaRoute, UnexpectedShapeError
from app.main import create_app
from tests.test_shema.conftest import PREFIX, REGIONS, auth_header, make_scoped_user

PROJECTS = f"{PREFIX}/projects"

#: What a person typed, standing in for a place, a contact or a prayer request.
CANARY = "VALOR-SIGILOSO-DO-FORMULARIO"


async def _headers(db_session, shema_app, *, role: str = "coordinator") -> dict[str, str]:
    user = await make_scoped_user(
        db_session, shema_app, email=f"{role.lower()}@quiet.test", role_key=role, regions=[]
    )
    return await auth_header(db_session, user)


def _assert_quiet(body: dict) -> None:
    """Every field error carries the kind, the place and the sentence, and nothing else."""
    assert body["detail"], "a 422 with no located error would place nothing on the screen"
    for error in body["detail"]:
        assert set(error) <= set(KEPT_ERROR_KEYS), error
        assert {"type", "loc", "msg"} <= set(error), error


async def test_a_shema_422_does_not_echo_what_was_sent(db_session, client, shema_app) -> None:
    """The body and the query string both, because both are what a person types.

    The body is the realistic one: a record saved from the console with a field the server
    refuses. FastAPI answers a *missing* field with the whole body as its ``input`` — so this
    payload, which leaves the four mandatory fields out, would echo the canary twice over
    without the route class. The location stays, which is what the console places the error by.
    """
    headers = await _headers(db_session, shema_app)

    body = await client.post(
        PROJECTS, headers=headers, json={"id": str(uuid.uuid4()), "location": [CANARY]}
    )
    query = await client.get(PROJECTS, headers=headers, params={"limit": CANARY})

    for res in (body, query):
        assert res.status_code == 422, res.text
        assert CANARY not in res.text
        _assert_quiet(res.json())
    assert ["body", "location"] in [error["loc"] for error in body.json()["detail"]]
    assert ["query", "limit"] in [error["loc"] for error in query.json()["detail"]]


async def test_another_applications_422_is_untouched(client) -> None:
    """The rule is the module's: the 422 the other applications' clients read is FastAPI's own.

    ``/api/auth`` is mounted beside the module in the test application, and its refusal still
    carries ``input`` — so the route class is what quiets the module, not a handler that would
    have changed the contract for everybody.
    """
    res = await client.post("/api/auth/login", json={"email": CANARY, "password": "x"})

    assert res.status_code == 422
    assert any("input" in error for error in res.json()["detail"])


class _Probe(BaseModel):
    count: int


@pytest.mark.parametrize("where", ["service", "response"])
async def test_an_unexpected_validation_error_leaves_no_input_in_the_log(
    db_session, client, shema_app, monkeypatch, caplog, where: str
) -> None:
    """A shape the server could not build reaches the log by where it failed, never by value.

    ``service`` is a Pydantic error raised inside the handler — a row that would not validate
    into its shape. ``response`` is the route's own response model refusing what the handler
    returned, which FastAPI raises as ``ResponseValidationError`` with the whole value in it.
    Both used to reach ``handle_unexpected`` and the server's own traceback with the canary in
    the message. The exception that leaves the application is read here as the server would
    print it, chained causes included.
    """

    async def _refuses(db) -> object:
        if where == "service":
            _Probe.model_validate({"count": CANARY})
        return [{"key": CANARY}]

    monkeypatch.setattr("app.api.shema.regions.list_regions", _refuses)
    headers = await _headers(db_session, shema_app, role="obtLab")

    with caplog.at_level(logging.ERROR), pytest.raises(UnexpectedShapeError) as raised:
        await client.get(REGIONS, headers=headers)

    printed = "".join(traceback.format_exception(raised.value))
    assert CANARY not in printed
    assert CANARY not in caplog.text
    assert "Unhandled exception" in caplog.text
    assert ("count [int_parsing]" if where == "service" else "response.0") in str(raised.value)


def test_every_shema_route_is_a_quiet_route() -> None:
    """Read off the application the server builds, so a route added by a later issue is asked.

    The other half is asserted too: a route outside the module is FastAPI's plain one, which is
    what *only under /api/shema* means on the route table.
    """
    routes = [route for route in create_app().routes if isinstance(route, APIRoute)]
    shema = [route for route in routes if route.path.startswith(PREFIX)]
    others = [route for route in routes if not route.path.startswith(PREFIX)]

    assert shema, "the module mounted no route, so the check below would pass on nothing"
    assert [route.path for route in shema if not isinstance(route, ShemaRoute)] == []
    assert others
    assert not any(isinstance(route, ShemaRoute) for route in others)
