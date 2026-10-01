from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from fastapi.routing import APIRoute
from starlette.datastructures import Headers, UploadFile
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.services.internalization_room import idempotency


class IdempotentRoute(APIRoute):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.app = _idempotent(self.app, f"{' '.join(sorted(self.methods))} {self.path}")


def _idempotent(app: ASGIApp, route: str) -> ASGIApp:
    async def handle(scope: Scope, receive: Receive, send: Send) -> None:
        key = Headers(scope=scope).get("idempotency-key")
        if key is None:
            await app(scope, receive, send)
            return

        request = Request(scope, receive)
        body = await request.body()
        held = await idempotency.claim(key, route, await _request_hash(request))
        if isinstance(held, idempotency.Replay):
            replay = Response(held.body, held.status_code, media_type="application/json")
            await replay(scope, receive, send)
            return

        answer = _SettledAnswer(held, send)
        try:
            await app(scope, _replaying(body, receive), answer.send)
        finally:
            if not answer.answered:
                await asyncio.shield(idempotency.release(held))

    return handle


async def _request_hash(request: Request) -> str:
    fields: list[list[str]] = []
    async with request.form() as form:
        for name, value in form.multi_items():
            if isinstance(value, UploadFile):
                fields.append([name, hashlib.sha256(await value.read()).hexdigest()])
            else:
                fields.append([name, value])
    fields.sort()
    canonical = json.dumps(
        {"path": sorted(request.path_params.items()), "form": fields}, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _replaying(body: bytes, receive: Receive) -> Receive:
    delivered = False

    async def replay() -> Message:
        nonlocal delivered
        if delivered:
            return await receive()
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    return replay


class _SettledAnswer:
    def __init__(self, held: idempotency.Claim, send: Send) -> None:
        self.held = held
        self.downstream = send
        self.answered = False
        self.messages: list[Message] = []
        self.status_code = 500
        self.body = b""

    async def send(self, message: Message) -> None:
        if self.answered:
            await self.downstream(message)
            return
        self.messages.append(message)
        if message["type"] == "http.response.start":
            self.status_code = message["status"]
            return
        self.body += message.get("body", b"")
        if message.get("more_body", False):
            return
        await idempotency.settle(self.held, self.status_code, self.body)
        self.answered = True
        for kept in self.messages:
            await self.downstream(kept)
