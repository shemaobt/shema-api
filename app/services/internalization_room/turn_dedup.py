from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRTurn


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
    """Record this turn's answer, once, so a resend finds it instead of repeating the work.

    Caught rather than avoided, the way ``working_time.py`` catches its own tick's race:
    ``ON CONFLICT`` is not spelled the same on Postgres and the SQLite the suite runs
    against, and the unique constraint is the guard that actually holds either way. A
    genuinely simultaneous resend loses this insert; it has already been answered from
    whatever the winner wrote, so there is nothing here worth keeping.
    """
    db.add(IRTurn(session_id=session_id, turn_id=turn_id, response=response))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
