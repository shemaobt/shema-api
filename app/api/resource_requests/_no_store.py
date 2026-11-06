"""``Cache-Control: private, no-store`` on every answer under ``/api/resource-requests`` (OBT-689).

Every answer of this module is built for its reader — the document of the request (names, place,
team, contacts), the evaluation, the board, a project's cards, the link session — so a body a
browser or a proxy kept would be served to the next reader of the same URL. The PME's module has
said so since OBT-555 (``PER_READER_CACHE_CONTROL``, ``app/api/shema/_deps.py``); the adversarial
pass of INT-12 (A-03, 6/nov/2026) measured this module answering with no ``Cache-Control`` at all.

**Why a middleware and not the ``Depends`` the Shemá module carries.** A router dependency writes
on the ``Response`` FastAPI builds for a handler that returns a model, and on nothing else: a
handler that returns a ``Response`` of its own (``endorse.py`` and ``link_public.py`` answer 410
and 403 that way) is served as it is, and an answer built by an exception handler — the 401 of a
missing session, the 403 of a missing capability, the 404, the 409 of a second open instance, the
422 — never passes through the dependency. Those errors say less than a 200, but a 404 that one
reader got cached over another reader's 200 is still the wrong body at the wrong screen. The
middleware sits on the ASGI ``send``, where every answer of the application passes, including
the error envelopes of ``app/core/exceptions.py`` (``ExceptionMiddleware`` is inside it; only the
500 of ``ServerErrorMiddleware`` is outside, and that one carries no record).

**Scoped, and never overwriting.** ``app/main.py`` is shared by every application in this
repository, so the middleware answers for this prefix alone and leaves every other path untouched;
and it adds the header only when the answer carries none, so a route that one day states its own
freshness — an attachment served through a signed address, say — keeps what it wrote. Today no
route under the prefix writes one: the attachment's ``GET`` answers metadata plus a short-lived
signed URL as JSON, and the signed address itself is the bucket's answer, not this server's.

``tests/test_resource_requests/test_cache_control.py`` reads the header off the wire for every
route the application mounts under the prefix, errors included.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

#: The module's own copy of the rule the PME's module states, so neither file depends on the other.
PER_READER_CACHE_CONTROL = "private, no-store"

#: Where ``app/main.py`` mounts the module and its access doors (``/api/resource-requests/access``).
PREFIX = "/api/resource-requests"

_HEADER = b"cache-control"


def covers(path: str, prefix: str = PREFIX) -> bool:
    """Whether an answer at ``path`` is this module's — the prefix itself or a path below it."""
    return path == prefix or path.startswith(prefix + "/")


class NoStoreUnderPrefix:
    """Pure ASGI: ``Cache-Control: private, no-store`` on every HTTP answer under ``prefix``
    that does not already carry a ``Cache-Control`` of its own."""

    def __init__(self, app: ASGIApp, prefix: str = PREFIX) -> None:
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not covers(scope["path"], self.prefix):
            await self.app(scope, receive, send)
            return

        async def send_no_store(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                if not any(name.lower() == _HEADER for name, _ in headers):
                    headers.append((_HEADER, PER_READER_CACHE_CONTROL.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_no_store)
