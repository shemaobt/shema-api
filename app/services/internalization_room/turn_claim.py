"""The one claim on a session's turn, held on the session's own row (ADR 0053, ADR 0079).

Her kickoff lease (`src/session/leases.ts`), taken by every turn that writes the conversation:
the opening, a team turn and a scene rehearsal's «terminei». One request answers a turn of the
session at a time; another turn that arrives meanwhile waits for its reply and runs after it,
on the conversation that holds it.

On the row and not in this process, because two tablets can reach two Cloud Run instances
and the in-process registry `answer_once` keeps would never let them meet. A conditional
UPDATE and not ``SELECT … FOR UPDATE``: the lock does nothing on SQLite, and held across the
Guide it would pin a pooled connection for the whole turn bound. A request that loses the
claim therefore polls the row, on a session of its own each look, so nothing is held between
looks.

A claim older than the turn bound plus thirty seconds (her ``KICKOFF_LEASE_TTL_MS`` against
``maxDuration``) belongs to a request the deployment has already killed, and is no claim.
Neither is one whose answer is already stored under its turn id: the turn it names has landed.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import ColumnElement, Update, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import TurnCollision, UpstreamServiceError
from app.core.stage_clock import stage
from app.db.models.internalization_room import IRSession, IRTurn
from app.models.internalization_room import TurnResponse
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.turn_dedup import answered_turn, remember_turn

#: How often a waiting request looks at the claim (her ``KICKOFF_POLL_MS``).
_LOOK_EVERY_S = 1.0
#: How much longer than the turn bound a claim outlives the request that took it.
_OUTLIVES_THE_BOUND = timedelta(seconds=30)


class Draft(Protocol):
    """The turn's own work: the Guide, the voice and the landing, under the bound it is given."""

    def __call__(
        self, *, speech_heard: HeardSpeech, turn_id: str | None, deadline: float
    ) -> Awaitable[TurnResponse]: ...


@dataclass(frozen=True)
class TurnClaim:
    """One request answering a turn of the session: the turn id its answer will be stored
    under, and when it claimed."""

    turn_id: str
    claimed_at: datetime


async def answer_under_the_turn_claim(
    db: AsyncSession,
    session: IRSession,
    *,
    opening: bool,
    turn_id: str | None,
    project_id: str,
    hearing: asyncio.Task[HeardSpeech] | None,
    deadline: float,
    bound_s: float,
    draft: Draft,
    heard: HeardSpeech | None = None,
) -> TurnResponse:
    """Answer this turn under the session's turn claim, one turn of the session at a time.

    The team's words are heard first (`hearing`, or `heard` when they were built rather than
    heard), then the claim is taken under the turn id the answer will be stored by (`turn_id`,
    or one minted for a tablet that sent none). The request that wins reads the session again,
    so it runs on the conversation with every reply that landed before it, and answers the
    turn already stored under its id when a run of the same turn on another instance landed
    first. A holder that ends without an answer releases its claim.

    A request that finds the claim held loses it one of three ways:

    - A request for the opening answers the holder's stored answer under its own `turn_id`,
      or a turn that did not answer when the claim is released first or `deadline` passes.
    - A request under the holder's own turn id, a resend on another instance, answers that
      turn's stored answer, or a turn that did not answer when `deadline` passes.
    - Any other turn waits for the holder's reply, then claims again. Its wait ends at the
      first claim it found plus the opening wait (`internalization_room_opening_wait_ms`):
      on a session still empty the holder is the opening, and the turn runs on the
      conversation as it stands; on any other it is refused `TurnCollision`, with nothing
      stored and nothing voiced.

    A claim that dies while it is waited on is claimed again. A request that waited gets its
    whole bound (`bound_s`) from the moment it wins, as `deadline`; the same bound dates a
    claim, which is dead once older than it and thirty seconds more.
    """
    if heard is not None:
        speech_heard = heard
    else:
        speech_heard = await hearing if hearing is not None else HeardSpeech()
    session_id, claimed_as = session.id, turn_id or str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    waited, ends = False, None
    while (claimed_at := await _claim(db, session_id, claimed_as, bound_s)) is None:
        holder = await _holder(session_id)
        if holder is None or not _live(holder, bound_s):
            continue
        waited = True
        if opening:
            with stage("turn_wait"):
                joined = await _joined(
                    db,
                    session_id,
                    holder,
                    turn_id=turn_id,
                    project_id=project_id,
                    until=deadline,
                    bound_s=bound_s,
                )
            if joined is not None:
                return joined
            continue
        if holder.turn_id == claimed_as:
            with stage("turn_wait"):
                rejoined = await _rejoined(
                    session_id, holder, project_id=project_id, until=deadline, bound_s=bound_s
                )
            if rejoined is not None:
                return rejoined
            continue
        if ends is None:
            ends = loop.time() + _wait_left(holder)
        with stage("turn_wait"):
            stored, now = await _looked_after(
                session_id, holder, project_id, until=ends, bound_s=bound_s
            )
        if stored is None and _still_held(now, holder, bound_s):
            return await _past_the_wait(db, session, speech_heard, claimed_as, bound_s, draft)

    claim = TurnClaim(claimed_as, claimed_at)
    try:
        await db.refresh(session)
        stored = await answered_turn(db, session_id, claimed_as, project_id)
        await db.commit()
        if stored is not None:
            await _release(session_id, claim)
            return TurnResponse(**stored)
        if waited:
            deadline = loop.time() + bound_s
        with reading_the_canon_of(session.canon_pin):
            return await draft(speech_heard=speech_heard, turn_id=claimed_as, deadline=deadline)
    except BaseException:
        await db.rollback()
        await _release(session_id, claim)
        raise


def oldest_live_claim(bound_s: float) -> datetime:
    """The claim time before which a claim belongs to a request that can no longer be running."""
    return datetime.now(UTC) - timedelta(seconds=bound_s) - _OUTLIVES_THE_BOUND


def _live(claim: TurnClaim, bound_s: float) -> bool:
    return claim.claimed_at >= oldest_live_claim(bound_s)


def _still_held(now: TurnClaim | None, holder: TurnClaim, bound_s: float) -> bool:
    return now == holder and _live(holder, bound_s)


def _set_claim(*where: ColumnElement[bool], turn_id: str | None, at: datetime | None) -> Update:
    """The one write of the claim's two columns, which never counts as the team's activity.

    `updated_at` is written its own value and `version` is left alone: the Desk reads the one,
    and `_land` guards the conversation with the other.
    """
    return (
        update(IRSession)
        .where(*where)
        .values(
            opening_claim_turn_id=turn_id, opening_claimed_at=at, updated_at=IRSession.updated_at
        )
        .execution_options(synchronize_session=False)
    )


async def _claim(
    db: AsyncSession, session_id: str, turn_id: str, bound_s: float
) -> datetime | None:
    """Claim the session's turn under `turn_id`, committed alone; when it was claimed, or None
    while another claim stands."""
    at = datetime.now(UTC)
    claimed = await db.execute(
        _set_claim(
            IRSession.id == session_id,
            or_(
                IRSession.opening_claim_turn_id.is_(None),
                IRSession.opening_claimed_at < oldest_live_claim(bound_s),
                exists().where(
                    IRTurn.session_id == IRSession.id,
                    IRTurn.turn_id == IRSession.opening_claim_turn_id,
                ),
            ),
            turn_id=turn_id,
            at=at,
        )
    )
    await db.commit()
    return at if claimed.rowcount == 1 else None


async def _release(session_id: str, claim: TurnClaim) -> None:
    """Free the claim this holder took, once its own work is rolled back.

    Guarded on the holder's turn id and claim time, so a holder that outlived its claim never
    clears the claim of a request that took it over, under the same turn id or another (ADR
    0043's rule). On a session of its own, because the holder's may be the very thing that
    failed — and only after the holder rolled back: a failure after the turn was written but
    before it was committed leaves the holder holding the session's row, and the release would
    wait on it for good.
    """
    async with AsyncSessionLocal() as own:
        await own.execute(
            _set_claim(
                IRSession.id == session_id,
                IRSession.opening_claim_turn_id == claim.turn_id,
                IRSession.opening_claimed_at == claim.claimed_at,
                turn_id=None,
                at=None,
            )
        )
        await own.commit()


async def _holder(session_id: str) -> TurnClaim | None:
    """The claim standing on the session's row now, live or not, read on a session of its own."""
    async with AsyncSessionLocal() as db:
        turn_id, claimed_at = (
            await db.execute(
                select(IRSession.opening_claim_turn_id, IRSession.opening_claimed_at).where(
                    IRSession.id == session_id
                )
            )
        ).one()
    return None if turn_id is None or claimed_at is None else TurnClaim(turn_id, claimed_at)


def _wait_left(holder: TurnClaim) -> float:
    """What is left, in seconds, of the opening wait counted from `holder`'s claim (her
    ``KICKOFF_WAIT_MS``)."""
    wait = timedelta(milliseconds=get_settings().internalization_room_opening_wait_ms)
    return (holder.claimed_at + wait - datetime.now(UTC)).total_seconds()


async def _looked_after(
    session_id: str, holder: TurnClaim, project_id: str, *, until: float, bound_s: float
) -> tuple[dict[str, Any] | None, TurnClaim | None]:
    """The answer stored under `holder`'s turn id, and the claim as last seen, once that answer
    is stored, `holder` no longer holds the claim live, or `until` passes.

    `until` is on the running loop's clock.
    """
    loop = asyncio.get_running_loop()
    while True:
        now = await _holder(session_id)
        async with AsyncSessionLocal() as db:
            stored = await answered_turn(db, session_id, holder.turn_id, project_id)
        left = until - loop.time()
        if stored is not None or not _still_held(now, holder, bound_s) or left <= 0:
            return stored, now
        await asyncio.sleep(min(_LOOK_EVERY_S, left))


async def _joined(
    db: AsyncSession,
    session_id: str,
    holder: TurnClaim,
    *,
    turn_id: str | None,
    project_id: str,
    until: float,
    bound_s: float,
) -> TurnResponse | None:
    """The opening another request claimed, as that request answered it, under this `turn_id`.

    Remembered under this request's own turn id when it has one, so its resend replays it.
    A turn that did not answer when the claim was released without an answer or `until`
    passed first: nothing is written then, and the next request claims anew. None when the
    claim died or was taken over meanwhile, to be claimed again.
    """
    stored, now = await _looked_after(session_id, holder, project_id, until=until, bound_s=bound_s)
    if stored is None and (now is None or _still_held(now, holder, bound_s)):
        raise UpstreamServiceError("a abertura desta sessão não chegou")
    if stored is None:
        return None
    reply = TurnResponse(**{**stored, "turn_id": turn_id or str(uuid.uuid4())})
    if turn_id:
        await remember_turn(
            db, session_id=session_id, turn_id=turn_id, response=reply.model_dump(mode="json")
        )
        await db.commit()
    return reply


async def _rejoined(
    session_id: str, holder: TurnClaim, *, project_id: str, until: float, bound_s: float
) -> TurnResponse | None:
    """This very turn, as the run that claimed it on another instance answered it.

    Nothing to remember: it is stored under this turn id already. A turn that did not answer
    when `until` passes first; None when the claim was released, died or was taken over, to
    be claimed again.
    """
    stored, now = await _looked_after(session_id, holder, project_id, until=until, bound_s=bound_s)
    if stored is not None:
        return TurnResponse(**stored)
    if _still_held(now, holder, bound_s):
        raise UpstreamServiceError("o turno reenviado não chegou")
    return None


async def _past_the_wait(
    db: AsyncSession,
    session: IRSession,
    speech_heard: HeardSpeech,
    turn_id: str,
    bound_s: float,
    draft: Draft,
) -> TurnResponse:
    """A turn whose wait ran out with the claim still held.

    On a session still empty the holder is the opening (ADR 0053): the turn runs, unclaimed,
    on the conversation as it stands, and the late opening is then dropped from the record.
    On any other the turn is refused as a collision.
    """
    await db.refresh(session)
    await db.commit()
    if session.messages:
        raise TurnCollision(f"Another turn of session {session.id} is still being answered")
    deadline = asyncio.get_running_loop().time() + bound_s
    with reading_the_canon_of(session.canon_pin):
        return await draft(speech_heard=speech_heard, turn_id=turn_id, deadline=deadline)
