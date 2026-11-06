"""``Cache-Control: private, no-store`` on every answer under ``/api/resource-requests`` (OBT-689).

Every answer here is built for its reader, so a body a browser or a proxy kept would be served
to the next reader of the same URL — ``docs/resource_requests.md`` §3 has the finding (A-03 of
INT-12) and the rule. What the code cannot say for itself:

* **A middleware, not the router ``Depends`` the Shemá module carries**, because a dependency
  writes only on the ``Response`` FastAPI builds for a handler that returns a model — never on a
  handler's own ``JSONResponse`` (``endorse.py``, ``link_public.py``) nor on the 401/403/404/409/
  422 the exception handlers build, and the adversarial pass measured those too. On the ASGI
  ``send`` every answer passes; only the 500 of ``ServerErrorMiddleware`` sits outside.
* **Scoped and never overwriting**: ``app/main.py`` is every application's, so the rule holds for
  this prefix alone, and a route that states its own freshness one day keeps what it wrote.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

#: The module's own copy of the Shemá module's rule, so neither file depends on the other.
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
