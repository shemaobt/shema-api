from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

_SCHEMES = {"http", "https", "ws", "wss"}


class CloudRunProxyHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = Headers(scope=scope)
            lines = headers.getlist("x-forwarded-for")
            entries = [entry.strip() for entry in ",".join(lines).split(",") if entry.strip()]
            if len(lines) == 1 and entries:
                scope["client"] = (entries[-1], 0)
            schemes = headers.getlist("x-forwarded-proto")
            scheme = schemes[-1].strip() if schemes else ""
            if scheme in _SCHEMES:
                if scope["type"] == "websocket":
                    scheme = scheme.replace("http", "ws")
                scope["scheme"] = scheme
        await self.app(scope, receive, send)
