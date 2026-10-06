"""The one claim on a session's opening, held on the session's own row (ADR 0053).

Her kickoff lease (`src/session/leases.ts`): the first request for a session's opening claims
it, and every other request for it, whatever its turn id, waits for that one's answer. A team
turn that arrives while the opening drafts waits for it too, so it lands after the opening and
not on an empty conversation.

On the row and not in this process, because two tablets can reach two Cloud Run instances
and the in-process registry `answer_once` keeps would never let them meet. A conditional
UPDATE and not ``SELECT … FOR UPDATE``: the lock does nothing on SQLite, and held across the
Guide it would pin a pooled connection for the whole turn bound. A request that loses the
claim therefore polls for the holder's stored answer, on a session of its own each look, so
nothing is held between looks.

A claim older than the turn bound plus thirty seconds (her ``KICKOFF_LEASE_TTL_MS`` against
``maxDuration``) belongs to a request the deployment has already killed, and is no claim.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.db.models.internalization_room import IRSession
from app.models.internalization_room import TurnResponse
from app.services.internalization_room.turn_dedup import answered_turn, remember_turn

#: How often a waiting request looks for the claimed answer (her ``KICKOFF_POLL_MS``).
LOOK_EVERY_S = 1.0
#: How much longer than the turn bound a claim outlives the request that took it.
_OUTLIVES_THE_BOUND = timedelta(seconds=30)


def _dead_before() -> datetime:
    bound = timedelta(milliseconds=get_settings().internalization_room_turn_bound_ms)
    return datetime.now(UTC) - bound - _OUTLIVES_THE_BOUND


async def claim(db: AsyncSession, session_id: str, turn_id: str) -> bool:
    """Claim this session's opening under `turn_id`, committed alone; False when it stands claimed.

    The claim is not the team's activity, so `updated_at` is written its own value and
    `version` is left alone: the Desk reads the one, and `_land` guards the conversation with
    the other.
    """
    claimed = await db.execute(
        update(IRSession)
        .where(
            IRSession.id == session_id,
            or_(
                IRSession.opening_claim_turn_id.is_(None),
                IRSession.opening_claimed_at < _dead_before(),
            ),
        )
        .values(
            opening_claim_turn_id=turn_id,
            opening_claimed_at=datetime.now(UTC),
            updated_at=IRSession.updated_at,
        )
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    return bool(claimed.rowcount == 1)


async def release(db: AsyncSession, session_id: str, turn_id: str) -> None:
    """Free the claim this holder took, when it ends without an opening.

    Guarded on the holder's own turn id, so a holder that outlived its claim never clears the
    claim of the request that took it over (ADR 0043's rule). On a session of its own, because
    the holder's may be the very thing that failed — and only after the holder's own work is
    rolled back: a failure after the opening was written but before it was committed leaves
    the holder holding the session's row, and the release would wait on it for good.
    """
    await db.rollback()
    async with AsyncSessionLocal() as own:
        await own.execute(
            update(IRSession)
            .where(IRSession.id == session_id, IRSession.opening_claim_turn_id == turn_id)
            .values(
                opening_claim_turn_id=None,
                opening_claimed_at=None,
                updated_at=IRSession.updated_at,
            )
            .execution_options(synchronize_session=False)
        )
        await own.commit()


def drafting_since(session: IRSession) -> datetime | None:
    """When the opening drafting on this session right now was claimed, read off the loaded row.

    None when nothing drafts: the team has spoken, nothing was claimed, or the claim is dead.
    """
    claimed_at = session.opening_claimed_at
    if session.messages or session.opening_claim_turn_id is None or claimed_at is None:
        return None
    return claimed_at if claimed_at >= _dead_before() else None


async def claimed_answer(
    session_id: str, project_id: str | None, *, until: float
) -> dict[str, Any] | None:
    """The answer stored under the claim, or None once the claim is gone or `until` passes.

    `until` is on the running loop's clock.
    """
    loop = asyncio.get_running_loop()
    while True:
        async with AsyncSessionLocal() as db:
            holder = await db.scalar(
                select(IRSession.opening_claim_turn_id).where(IRSession.id == session_id)
            )
            stored = await answered_turn(db, session_id, holder, project_id) if holder else None
        left = until - loop.time()
        if stored is not None or holder is None or left <= 0:
            return stored
        await asyncio.sleep(min(LOOK_EVERY_S, left))


async def joined(
    db: AsyncSession,
    session_id: str,
    *,
    turn_id: str | None,
    project_id: str | None,
    until: float,
) -> TurnResponse | None:
    """The opening another request claimed, as that request answered it, under this `turn_id`.

    Remembered under this request's own turn id when it has one, so its resend replays it.
    None when the claim was released without an opening or `until` passed first: nothing is
    written then, and the next request claims anew.
    """
    stored = await claimed_answer(session_id, project_id, until=until)
    if stored is None:
        return None
    reply = TurnResponse(**{**stored, "turn_id": turn_id or str(uuid.uuid4())})
    if turn_id:
        await remember_turn(
            db, session_id=session_id, turn_id=turn_id, response=reply.model_dump(mode="json")
        )
        await db.commit()
    return reply


async def wait_for_the_opening(
    db: AsyncSession, session: IRSession, project_id: str | None, since: datetime
) -> None:
    """Hold a team turn until the opening drafting on its session lands, at most the wait.

    The wait is counted from the claim (`since`), not from this turn, the way her
    ``KICKOFF_WAIT_MS`` is counted from the lease. The session is then read again, so the
    turn runs on the conversation that now holds the opening, and let go before the Guide.
    """
    wait = timedelta(milliseconds=get_settings().internalization_room_opening_wait_ms)
    left = (since + wait - datetime.now(UTC)).total_seconds()
    await claimed_answer(session.id, project_id, until=asyncio.get_running_loop().time() + left)
    await db.refresh(session)
    await db.commit()
