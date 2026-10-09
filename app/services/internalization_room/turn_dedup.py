from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.stage_clock import StageClock, adopt, current_clock
from app.db.insert_once import insert_once
from app.db.models.internalization_room import IRSession, IRTurn
from app.models.internalization_room import TurnResponse

_in_flight: dict[
    tuple[str, str, str | None], tuple[asyncio.Task[TurnResponse], StageClock | None]
] = {}


async def answer_once(
    session_id: str,
    turn_id: str,
    project_id: str | None,
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

    Keyed on the caller's project along with the session and turn id, so a stranger's
    request landing on the same turn id while the owner's is still in flight runs its own
    answer and its own ownership check, rather than joining the owner's and hearing back
    a reply it was never checked against.
    """
    key = (session_id, turn_id, project_id)
    if key not in _in_flight:
        task = asyncio.create_task(_on_a_session_of_its_own(answer))
        _in_flight[key] = (task, current_clock())
        task.add_done_callback(lambda _: _in_flight.pop(key, None))
    running, clock = _in_flight[key]
    answered = await asyncio.shield(running)
    adopt(clock)
    return answered


def in_flight(session_id: str, turn_id: str, project_id: str | None) -> bool:
    """Whether this caller's request for this turn is still being answered in this process.

    Keyed the way `answer_once` keys it, so a stranger's turn id landing on the owner's
    turn in flight is not reported as in flight for the stranger.
    """
    return (session_id, turn_id, project_id) in _in_flight


async def _on_a_session_of_its_own(
    answer: Callable[[AsyncSession], Coroutine[Any, Any, TurnResponse]],
) -> TurnResponse:
    async with AsyncSessionLocal() as db:
        return await answer(db)


async def answered_turn(
    db: AsyncSession, session_id: str, turn_id: str, project_id: str
) -> dict[str, Any] | None:
    """The response already given for this turn id, to the team that may hear it.

    Joined against the session, which names the team: a turn belonging to somebody else's
    session, or to a session that names no team, reads as not landed yet, the same as a
    turn nobody has answered, so it falls through to the session read beside this one,
    which refuses it.
    """
    result = await db.execute(
        select(IRTurn)
        .join(IRSession, IRSession.id == IRTurn.session_id)
        .where(
            IRTurn.session_id == session_id,
            IRTurn.turn_id == turn_id,
            IRSession.project_id == project_id,
        )
    )
    turn = result.scalar_one_or_none()
    return turn.response if turn is not None else None


async def remember_turn(
    db: AsyncSession, *, session_id: str, turn_id: str, response: dict[str, Any]
) -> None:
    """Record this turn's answer, once, so a resend finds it instead of repeating the work."""
    await insert_once(
        db,
        IRTurn,
        {"session_id": session_id, "turn_id": turn_id, "response": response},
        conflict_on=["session_id", "turn_id"],
    )
