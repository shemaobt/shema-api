from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from app.core.database import AsyncSessionLocal
from app.core.room_enums import HaltKind
from app.services.internalization_room import halt
from app.services.internalization_room.sessions import get_session

What = Literal["sessions", "hands", "halts", "takes", "stretches", "verdict", "release"]

_subscribers: defaultdict[str, set[asyncio.Queue[What]]] = defaultdict(set)


@asynccontextmanager
async def subscribe(team_id: str) -> AsyncIterator[asyncio.Queue[What]]:
    queue: asyncio.Queue[What] = asyncio.Queue()
    _subscribers[team_id].add(queue)
    try:
        yield queue
    finally:
        _subscribers[team_id].discard(queue)
        if not _subscribers[team_id]:
            del _subscribers[team_id]


def nudge(team_id: str | None, what: What) -> None:
    if team_id is None:
        return
    for queue in _subscribers.get(team_id, ()):
        queue.put_nowait(what)


def nudge_stretches(team_id: str | None, *, warned: bool) -> None:
    nudge(team_id, "stretches")
    if warned:
        nudge(team_id, "halts")


async def nudge_after_a_turn(*, session_id: str) -> None:
    async with AsyncSessionLocal() as db:
        session = await get_session(db, session_id)
    nudge(session.project_id, "sessions")
    if halt.last(session) is HaltKind.BLOCKING and halt.standing(session) is None:
        nudge(session.project_id, "halts")
