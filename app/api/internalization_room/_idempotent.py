from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from fastapi import Depends, Request
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.internalization_room._deps import device_dep, device_project_dep
from app.core.database import get_db
from app.core.exceptions import StoredAnswer, ValidationError
from app.core.stage_clock import stage
from app.services.internalization_room import idempotency

CLAIM = "idempotency_claim"
LONGEST_KEY = 255


class IdempotentRoute(APIRoute):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.app = _settling(self.app)


async def claim_the_key(
    request: Request,
    session_id: str,
    _device_id: str = device_dep,
    project_id: str | None = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> None:
    key = request.headers.get("idempotency-key")
    if not key:
        return
    if len(key) > LONGEST_KEY:
        raise ValidationError(f"Idempotency-Key must be at most {LONGEST_KEY} characters")
    with stage("db_let_go"):
        await db.commit()
    route = f"{request.method} {request.scope['route'].path}"
    held = await idempotency.claim(
        key,
        route,
        await _request_hash(request),
        session_id=session_id,
        project_id=project_id,
    )
    if isinstance(held, idempotency.Replay):
        raise StoredAnswer(held.status_code, held.body)
    request.scope.setdefault("state", {})[CLAIM] = held


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
            if held is not None and answer.storing is None:
                await asyncio.shield(idempotency.release(held))

    return handle


class _Answer:
    def __init__(self, scope: Scope, send: Send) -> None:
        self.scope = scope
        self.downstream = send
        self.storing: asyncio.Future[None] | None = None
        self.messages: list[Message] = []
        self.status_code = 500
        self.body = b""

    def claim(self) -> idempotency.Claim | None:
        held: idempotency.Claim | None = self.scope.get("state", {}).get(CLAIM)
        return held

    async def send(self, message: Message) -> None:
        held = self.claim()
        if held is None or self.storing is not None:
            await self.downstream(message)
            return
        self.messages.append(message)
        if message["type"] == "http.response.start":
            self.status_code = message["status"]
            return
        self.body += message.get("body", b"")
        if message.get("more_body", False):
            return
        self.storing = asyncio.ensure_future(_store(held, self.status_code, self.body))
        self.storing.add_done_callback(_retrieved)
        await asyncio.shield(self.storing)
        for kept in self.messages:
            await self.downstream(kept)


async def _store(held: idempotency.Claim, status_code: int, body: bytes) -> None:
    try:
        await idempotency.settle(held, status_code, body)
    except Exception:
        await idempotency.release(held)
        raise


def _retrieved(storing: asyncio.Future[None]) -> None:
    if not storing.cancelled():
        storing.exception()
