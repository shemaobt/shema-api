from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.sound_necklace import SessionStep, SnSession, SnSessionState
from app.services.sound_necklace.lock_fence import not_locked_by_other, raise_if_locked_by_other


class StateVersionConflict(ConflictError):
    """A writer saved from a version that is no longer current.

    Carries the version the loser has to reload from; the router turns it into the
    409 body.
    """

    def __init__(self, current_version: int) -> None:
        super().__init__("The session was saved elsewhere. Reload it before saving again.")
        self.current_version = current_version


def step_for(fields: Mapping[str, Any]) -> SessionStep:
    """The station this state would open at.

    Mirrors the SPA's ``stepFor``: the dashboard needs a station at a glance, and the
    state document is the only place that knows it. Takes the already-parsed fields —
    the document itself is never re-read, only stored.

    Only the body is a validated object; every field inside it is an untyped extra, so
    ``whole`` is whatever the client sent.
    """
    mode = fields.get("mode")
    if mode == "triagem":
        return SessionStep.TRIAGE
    if mode == "segmentacao":
        return SessionStep.PHRASES
    if mode == "mapeamento":
        return SessionStep.CONVERSATION
    whole = fields.get("whole")
    confirmed = whole.get("confirmed") if isinstance(whole, Mapping) else False
    return SessionStep.CUT if confirmed else SessionStep.LISTEN


async def autosave_state(
    db: AsyncSession,
    session: SnSession,
    *,
    document: str,
    fields: Mapping[str, Any],
    expected_version: int | None,
    actor_user_id: str,
) -> tuple[int, datetime]:
    """Store the state document verbatim; return its new version and save time.

    ``document`` is written as the exact bytes that arrived. The SPA re-reads it under
    a strict schema, so anything this API re-serialized — key order, float formatting,
    an added field — would come back as an unresumable session. ``fields`` is the same
    document already parsed, used only to derive the station.

    With ``expected_version``, the write only lands while that version is still
    current; a writer who lost the race is refused rather than silently clobbering work
    it never saw.

    The new version comes back from the UPDATE itself: reading it afterwards could pick
    up a concurrent writer's version instead of this one, and handing that back as the
    caller's own would let a later guarded write clobber the very work the guard exists
    to protect.

    The lease guard rides in the same statement for the same reason it exists at all: a
    tab that checked the lock and then wrote would be racing the takeover it meant to
    catch. It only bites while somebody else holds a live lease, so a session nobody
    locked autosaves exactly as it did before.
    """
    now = datetime.now(UTC)
    stmt = update(SnSessionState).where(
        SnSessionState.session_id == session.id,
        not_locked_by_other(session.id, actor_user_id, now),
    )
    if expected_version is not None:
        stmt = stmt.where(SnSessionState.version == expected_version)
    stmt = (
        stmt.values(state=document, version=SnSessionState.version + 1, updated_at=now)
        .returning(SnSessionState.version)
        .execution_options(synchronize_session=False)
    )

    version = (await db.execute(stmt)).scalar_one_or_none()
    if version is None:
        # Nothing matched, so nothing is pending: leave the transaction to the caller's
        # teardown rather than rolling back a session shared with the rest of the request.
        # Which guard refused it is only decided here, on the path that already lost.
        await raise_if_locked_by_other(db, session.id, actor_user_id)
        raise StateVersionConflict(await _current_version(db, session.id))

    session.current_step = step_for(fields)
    session.updated_at = now
    await db.commit()
    return version, now


async def _current_version(db: AsyncSession, session_id: str) -> int:
    result = await db.execute(
        select(SnSessionState.version).where(SnSessionState.session_id == session_id)
    )
    return result.scalar_one()
