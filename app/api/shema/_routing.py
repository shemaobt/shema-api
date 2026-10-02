"""The module's own route class — what a validation error may say, and to whom (OBT-556).

Two of the INT-12 findings are one fact read from two ends: a validation error carries the
value it refused. FastAPI's 422 hands each field error's ``input`` back to whoever sent it, and
a Pydantic error raised while the server builds a shape — a row that will not validate, a
response that does not fit its model — is logged with ``input_value=`` in its message. In this
module that value is a project's place, a contact or a prayer request as easily as anything
else.

**Here, and nowhere else.** ``app/core/exceptions.py`` registers the handlers eight
applications share, and their 422 is a contract some of their clients read, so the rule is a
route class that only this module's routes carry. :class:`ShemaRouter` hands it to every
route included into the module's three routers, so a route a later issue adds is quiet by
being included, as it is guarded by being included (``app/api/shema/__init__.py``).

**Why the route and not an exception handler.** Starlette's ``ServerErrorMiddleware`` calls the
handler for an unexpected exception and then re-raises it, so the server logs the original
whatever the handler wrote. The one place to keep the value out of every log is before the
exception leaves the route, which is where this class stands.

What changes, and what does not:

* a 422's field errors keep ``type``, ``loc`` and ``msg`` — what the console reads to place a
  refusal on a field — and lose ``input`` and ``ctx``, which is how ``IncompleteSubmission``
  already renders the same list. The envelope is FastAPI's own, drawn by FastAPI's own handler:
  the error is raised again without the values, not answered here.
* an unexpected Pydantic error leaves as :class:`UnexpectedShapeError`, whose message names the
  model and each failing location and kind and never a value. It keeps the original traceback,
  whose frames say *where* without saying *what*, and it is raised outside the ``except`` so
  nothing chains the original message back onto it.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Sequence
from typing import Any, Final

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.routing import APIRoute, APIRouter
from pydantic import ValidationError as PydanticValidationError

#: What a field error keeps on the wire: the kind of the refusal, where it is, and the sentence.
KEPT_ERROR_KEYS: Final = ("type", "loc", "msg")


class UnexpectedShapeError(Exception):
    """A shape this module could not build, named by where it failed and never by the value.

    It replaces a Pydantic error that reached the edge of a route, so ``handle_unexpected`` and
    the server log a sentence that is safe to keep: the model, each failing location and the
    kind of each failure. The response is the 500 every unexpected error already answers.
    """


def without_input(errors: Sequence[Any]) -> list[dict[str, Any]]:
    """A request's field errors as this module answers them — the input and the context gone."""
    return [{key: error[key] for key in KEPT_ERROR_KEYS if key in error} for error in errors]


def _located(failed: PydanticValidationError | ResponseValidationError) -> str:
    """The failure as a log may keep it: the model, and the location and kind of each error.

    ``msg`` stays out too. A built-in message is generic, but a validator of this module writes
    its own, and one that names the value it refused would carry the value into the log.
    """
    if isinstance(failed, PydanticValidationError):
        title = failed.title
        errors: Sequence[Any] = failed.errors(
            include_url=False, include_context=False, include_input=False
        )
    else:
        title = "the response"
        errors = failed.errors()
    places = ", ".join(
        f"{'.'.join(str(part) for part in error.get('loc', ()))} [{error.get('type', '?')}]"
        for error in errors
    )
    return f"{len(errors)} validation error(s) building {title}: {places}"


def _quiet(
    caught: RequestValidationError | ResponseValidationError | PydanticValidationError,
) -> Exception:
    """The exception to raise in place of ``caught`` — the same refusal, without the value."""
    if isinstance(caught, RequestValidationError):
        return RequestValidationError(without_input(caught.errors()))
    return UnexpectedShapeError(_located(caught)).with_traceback(caught.__traceback__)


class ShemaRoute(APIRoute):
    """A route whose validation errors carry no value they refused — the module docstring."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handle = super().get_route_handler()

        async def quiet(request: Request) -> Response:
            try:
                return await handle(request)
            except (
                RequestValidationError,
                ResponseValidationError,
                PydanticValidationError,
            ) as caught:
                replacement = _quiet(caught)
            raise replacement

        return quiet


class ShemaRouter(APIRouter):
    """An ``APIRouter`` whose every route is a :class:`ShemaRoute`, wherever it was declared.

    ``include_router`` re-creates each included route with ``route_class_override`` set to the
    route's own class, so a router's ``route_class`` reaches the routes declared on it and none
    of the ones included into it. Forcing the override here is what lets the module's three
    routers hand the class to every sub-router's routes, without each file that declares an
    ``APIRouter()`` having to remember it.
    """

    def add_api_route(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        kwargs["route_class_override"] = ShemaRoute
        super().add_api_route(path, endpoint, **kwargs)
