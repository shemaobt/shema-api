from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.db.models.internalization_room import IRSession
from app.models.internalization_room import CoverageFrame, CoverageView
from app.services.internalization_room.canon.elements import absence_index
from app.services.internalization_room.coverage import counts

_subscribers: defaultdict[str, set[asyncio.Queue[CoverageFrame]]] = defaultdict(set)


@asynccontextmanager
async def subscribe(session_id: str) -> AsyncIterator[asyncio.Queue[CoverageFrame]]:
    queue: asyncio.Queue[CoverageFrame] = asyncio.Queue()
    _subscribers[session_id].add(queue)
    try:
        yield queue
    finally:
        _subscribers[session_id].discard(queue)
        if not _subscribers[session_id]:
            del _subscribers[session_id]


def publish(session_id: str, frame: CoverageFrame) -> None:
    for queue in list(_subscribers.get(session_id, ())):
        queue.put_nowait(frame)


def settled_view(session: IRSession) -> CoverageView:
    numbers = counts(session.coverage_state or {})
    return CoverageView(
        engaged=numbers["engaged"],
        surfaced=numbers["surfaced"],
        total=numbers["total"],
        absence_index=absence_index(session.pericope),
    )
