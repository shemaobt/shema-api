from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

_SCHEMES = {"http", "https", "ws", "wss"}


class CloudRunProxyHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = Headers(scope=scope)
            forwarded_for = ",".join(headers.getlist("x-forwarded-for"))
            entries = [entry.strip() for entry in forwarded_for.split(",") if entry.strip()]
            if entries:
                scope["client"] = (entries[-1], 0)
            scheme = headers.get("x-forwarded-proto", "").strip()
            if scheme in _SCHEMES:
                if scope["type"] == "websocket":
                    scheme = scheme.replace("http", "ws")
                scope["scheme"] = scheme
        await self.app(scope, receive, send)
