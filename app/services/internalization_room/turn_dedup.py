from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.stage_clock import StageClock, adopt, current_clock
from app.db.models.internalization_room import IRTurn
from app.models.internalization_room import TurnResponse

_in_flight: dict[tuple[str, str], tuple[asyncio.Task[TurnResponse], StageClock | None]] = {}


async def answer_once(
    session_id: str,
    turn_id: str,
    answer: Callable[[AsyncSession], Coroutine[Any, Any, TurnResponse]],
) -> TurnResponse:
    """Run this turn once while it is in flight; a resend joins it and hears the same answer.

    A registry in this process rather than a claim row, because the second request has to
    come back with the first one's answer and a row can only hand that over by polling it
    until the first commits. Shielded so the tablet that gave up on the first request
    cannot take the answer away from the one still waiting for it — and run on a session
    of its own, the way `settle_coverage` is, because the request's session closes when
    that request unwinds, and a turn that outlives it would otherwise write through a
    session that is no longer there.
    """
    key = (session_id, turn_id)
    if key not in _in_flight:
        task = asyncio.create_task(_on_a_session_of_its_own(answer))
        _in_flight[key] = (task, current_clock())
        task.add_done_callback(lambda _: _in_flight.pop(key, None))
    running, clock = _in_flight[key]
    answered = await asyncio.shield(running)
    adopt(clock)
    return answered


async def _on_a_session_of_its_own(
    answer: Callable[[AsyncSession], Coroutine[Any, Any, TurnResponse]],
) -> TurnResponse:
    async with AsyncSessionLocal() as db:
        return await answer(db)


async def answered_turn(db: AsyncSession, session_id: str, turn_id: str) -> dict[str, Any] | None:
    """The response already given for this turn id, or nothing if it has not landed yet."""
    result = await db.execute(
        select(IRTurn).where(IRTurn.session_id == session_id, IRTurn.turn_id == turn_id)
    )
    turn = result.scalar_one_or_none()
    return turn.response if turn is not None else None


async def remember_turn(
    db: AsyncSession, *, session_id: str, turn_id: str, response: dict[str, Any]
) -> None:
    """Record this turn's answer, once, so a resend finds it instead of repeating the work."""
    insert = postgresql.insert if db.get_bind().dialect.name == "postgresql" else sqlite.insert
    await db.execute(
        insert(IRTurn)
        .values(session_id=session_id, turn_id=turn_id, response=response)
        .on_conflict_do_nothing(index_elements=["session_id", "turn_id"])
    )
