"""The Desk's nudge channel: one registry of listening Desks per team.

A route that wrote something the Desk shows calls `nudge` after its commit, naming what changed
and nothing else; every Desk listening on that team hears it and reads that thing again. A write
with no team nudges nobody.

The registry is memory in this process, so it holds while the API runs in one copy (ADR 0041).
`subscribe` and `nudge` are the seam a broker between copies replaces.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.models.internalization_room import Nudge, NudgeWhat

_subscribers: defaultdict[str, set[asyncio.Queue[Nudge]]] = defaultdict(set)


@asynccontextmanager
async def subscribe(team_id: str) -> AsyncIterator[asyncio.Queue[Nudge]]:
    queue: asyncio.Queue[Nudge] = asyncio.Queue()
    _subscribers[team_id].add(queue)
    try:
        yield queue
    finally:
        _subscribers[team_id].discard(queue)
        if not _subscribers[team_id]:
            del _subscribers[team_id]


def nudge(team_id: str | None, what: NudgeWhat) -> None:
    if team_id is None:
        return
    for queue in _subscribers.get(team_id, ()):
        queue.put_nowait(Nudge(what=what))


def nudge_stretches(team_id: str | None, *, warned: bool) -> None:
    nudge(team_id, "stretches")
    if warned:
        nudge(team_id, "halts")
