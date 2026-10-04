from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.stage_clock import StageClock, adopt, current_clock
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


async def _on_a_session_of_its_own(
    answer: Callable[[AsyncSession], Coroutine[Any, Any, TurnResponse]],
) -> TurnResponse:
    async with AsyncSessionLocal() as db:
        return await answer(db)


async def answered_turn(
    db: AsyncSession, session_id: str, turn_id: str, project_id: str | None
) -> dict[str, Any] | None:
    """The response already given for this turn id, to the project that may hear it.

    A caller naming no project is judged the way the session read beside this one
    judges it — by id alone — so only a caller naming one joins against the session,
    which names none of its own: a turn belonging to somebody else's session reads as
    not landed yet, the same as a turn nobody has answered, so it falls through to the
    ownership check the session read below already gives that caller its own refusal
    from.
    """
    query = select(IRTurn).where(IRTurn.session_id == session_id, IRTurn.turn_id == turn_id)
    if project_id is not None:
        query = query.join(IRSession, IRSession.id == IRTurn.session_id).where(
            or_(IRSession.project_id.is_(None), IRSession.project_id == project_id)
        )
    result = await db.execute(query)
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
