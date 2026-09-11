from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.models.internalization_room import CoverageFrame

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
