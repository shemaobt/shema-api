from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from fastapi import Depends, Request
from fastapi.routing import APIRoute
from starlette.datastructures import UploadFile
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exceptions import StoredAnswer
from app.services.internalization_room import idempotency

CLAIM = "idempotency_claim"


class IdempotentRoute(APIRoute):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.app = _settling(self.app)


async def claim_the_key(request: Request) -> None:
    key = request.headers.get("idempotency-key")
    if not key:
        return
    route = f"{request.method} {request.scope['route'].path}"
    held = await idempotency.claim(key, route, await _request_hash(request))
    if isinstance(held, idempotency.Replay):
        raise StoredAnswer(held.status_code, held.body)
    request.state.idempotency_claim = held


idempotency_dep = Depends(claim_the_key)


async def _request_hash(request: Request) -> str:
    fields: list[list[str]] = []
    for name, value in (await request.form()).multi_items():
        if isinstance(value, UploadFile):
            fields.append([name, hashlib.sha256(await value.read()).hexdigest()])
            await value.seek(0)
        else:
            fields.append([name, value])
    fields.sort()
    canonical = json.dumps(
        {"path": sorted(request.path_params.items()), "form": fields}, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _settling(app: ASGIApp) -> ASGIApp:
    async def handle(scope: Scope, receive: Receive, send: Send) -> None:
        answer = _Answer(scope, send)
        try:
            await app(scope, receive, answer.send)
        finally:
            held = answer.claim()
            if held is not None and not answer.settled:
                await asyncio.shield(idempotency.release(held))

    return handle


class _Answer:
    def __init__(self, scope: Scope, send: Send) -> None:
        self.scope = scope
        self.downstream = send
        self.settled = False
        self.messages: list[Message] = []
        self.status_code = 500
        self.body = b""

    def claim(self) -> idempotency.Claim | None:
        held: idempotency.Claim | None = self.scope.get("state", {}).get(CLAIM)
        return held

    async def send(self, message: Message) -> None:
        held = self.claim()
        if held is None or self.settled:
            await self.downstream(message)
            return
        self.messages.append(message)
        if message["type"] == "http.response.start":
            self.status_code = message["status"]
            return
        self.body += message.get("body", b"")
        if message.get("more_body", False):
            return
        await idempotency.settle(held, self.status_code, self.body)
        self.settled = True
        for kept in self.messages:
            await self.downstream(kept)
