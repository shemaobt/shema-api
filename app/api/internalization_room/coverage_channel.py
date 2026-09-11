"""The per-session coverage channel: where a settled classification is announced.

The classifier runs after the turn's reply has already shipped, so the tablet used to
guess thirty seconds and ask the state endpoint once. This route lets the server say it
instead — one `coverage` event per settled turn, carrying the turn id the turn response
promised, the moment `settle_coverage` publishes it.

It is Server-Sent Events, not a WebSocket, and the choice is deliberate. Nothing here
travels from the tablet to the server: the app subscribes and listens, so one direction
is the whole need. SSE is a plain HTTP response that never ends, which means no new
dependency — `StreamingResponse` is already what the Translation Helper streams its chats
through — and nothing to teach the proxies in front of Cloud Run about upgrades, pings or
close frames. The keep-alive comments below are what keeps an idle stream from being cut
by an intermediary that has not seen a byte in a while.

The subscriber registry is in-process memory, and nothing pins the service to one process:
Cloud Run runs it with no `--max-instances` and no session affinity, so the GET holding a
channel and the POST whose background task publishes can land on different instances, and
that turn's frame reaches nobody. The tablet's thirty-second fallback — one `fetchState`
and stop — is therefore part of the contract, not a safety net, until the announcement
travels through something every instance can see.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import room_caller_dep
from app.core.database import get_db
from app.services.internalization_room.coverage_channel import subscribe
from app.services.internalization_room.sessions import get_session

KEEP_ALIVE_SECONDS = 15.0

router = APIRouter()


@router.get("/sessions/{session_id}/coverage", dependencies=[room_caller_dep])
async def coverage_channel(
    session_id: str, db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    await get_session(db, session_id)

    async def _frames() -> AsyncIterator[bytes]:
        async with subscribe(session_id) as queue:
            while True:
                try:
                    frame = await asyncio.wait_for(queue.get(), timeout=KEEP_ALIVE_SECONDS)
                except TimeoutError:
                    yield b": keep-alive\n\n"
                    continue
                yield f"event: coverage\ndata: {frame.model_dump_json()}\n\n".encode()

    return StreamingResponse(
        _frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
