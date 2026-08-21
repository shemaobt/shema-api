from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.coverage import floor_met, furthest, initial_state
from app.services.internalization_room.coverage_events import record_transitions
from app.services.project.facilitates_project import facilitates_project

DEFAULT_PERICOPE = "P01"
PANORAMA_PREFIX = "OV-"
PANORAMA_ALIAS = "OV"
MAX_RETELLS = 3


def is_panorama(pericope: str) -> bool:
    """`OV-Ruth` addresses the book itself rather than one of its passages."""
    return pericope.startswith(PANORAMA_PREFIX)


def book_of(pericope: str) -> str:
    return pericope[len(PANORAMA_PREFIX) :] if is_panorama(pericope) else load_map(pericope).book


def resolve_pericope(pericope: str) -> str:
    """`OV` alone is the panorama of whichever book the room serves, so a client can ask
    for it without naming the book — the canon stays entirely on this side."""
    if pericope == PANORAMA_ALIAS:
        return PANORAMA_PREFIX + book_of(DEFAULT_PERICOPE)
    return pericope


async def create_session(
    db: AsyncSession,
    *,
    pericope: str = DEFAULT_PERICOPE,
    after_panorama: bool = False,
    project_id: str | None = None,
) -> IRSession:
    """Open a session on a passage, or on the panorama of a book.

    The meaning map is loaded before anything is written, so unapproved or unsupported
    canon is refused before a session exists. A panorama has no coverage spine and never
    completes: it prepares the team to enter the book, and asks no retelling of them.

    ``project_id`` is whose it is, when the device said so. Null is a normal answer, not a
    failure. The room app identifies itself with a device credential only from ENG-454
    onward, and refusing a session without one would take every room in the field offline
    to gain a column value.
    """
    pericope = resolve_pericope(pericope)
    panorama = is_panorama(pericope)
    if not panorama:
        load_map(pericope)
    session = IRSession(
        project_id=project_id,
        pericope=pericope,
        status=IRSessionStatus.IN_PROGRESS,
        messages=[],
        after_panorama=after_panorama,
        # A panorama has no coverage spine and never completes: it prepares the team to enter
        # the book, and asks no retelling of them.
        coverage_state={} if panorama else initial_state(pericope),
        kept_takes={},
        back_translation={},
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: str) -> IRSession:
    result = await db.execute(select(IRSession).where(IRSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundError(_no_such_session(session_id))
    return session


def _no_such_session(session_id: str) -> str:
    """One message for absent, unowned, and somebody else's. See ENG-534."""
    return f"Internalization room session {session_id} not found"


async def get_session_for_facilitator(db: AsyncSession, user: User, session_id: str) -> IRSession:
    """The session, if it belongs to a team this facilitator facilitates.

    What hangs off a session is what the team recorded, so reaching one that is not yours
    reaches their rehearsal audio. A session with no ``project_id`` is refused for the
    reason ``get_question_for_facilitator`` gives: unowned is nobody's, not everybody's.
    """
    session = await get_session(db, session_id)
    if session.project_id is None or not await facilitates_project(db, user, session.project_id):
        raise NotFoundError(_no_such_session(session_id))
    return session


async def append_exchange(
    db: AsyncSession,
    session: IRSession,
    *,
    team_utterance: str,
    guide_response: str,
) -> IRSession:
    """Append one team/guide turn to the transcript.

    A turn that lands is the proof a person came back, so it also releases
    `NEEDS_PERSON` — nothing else ever writes `IN_PROGRESS` a second time.
    """
    messages: list[dict[str, Any]] = list(session.messages or [])
    if team_utterance:
        messages.append({"role": "team", "text": team_utterance})
    messages.append({"role": "guide", "text": guide_response})
    session.messages = messages
    # A turn that lands is the proof a person came back. `NEEDS_PERSON` had no way out of
    # itself — nothing anywhere wrote `IN_PROGRESS` a second time — so the app's resume
    # was contradicted by the next state poll thirty seconds later, in a loop, for the
    # rest of the session: the person arrives, the team speaks, the room halts again.
    if session.status is IRSessionStatus.NEEDS_PERSON:
        session.status = IRSessionStatus.IN_PROGRESS
    await db.commit()
    await db.refresh(session)
    return session


async def apply_coverage(
    db: AsyncSession, session_id: str, coverage_state: dict[str, str]
) -> IRSession:
    """Store the tracker after the off-path classifier ran.

    Closes the session when the completion floor is met, and leaves an event behind for
    every bead that moved — the merge is compared against what is stored before anything
    is written, so a classifier round that reports no news costs no rows.
    """
    session = await get_session(db, session_id)
    # Merged against what is stored now, not written over it. The snapshot this was
    # computed from is a Gemini round trip old, and a second turn may have settled in the
    # meantime; a blind overwrite let the older reading win and darkened a bead the team
    # had already earned.
    kept = session.coverage_state or {}
    settled = furthest(kept, coverage_state, pericope_num=session.pericope)
    record_transitions(db, session, before=kept, after=settled)
    session.coverage_state = settled
    if (
        not is_panorama(session.pericope)
        and floor_met(session.coverage_state, session.pericope)
        and session.status is IRSessionStatus.IN_PROGRESS
    ):
        session.status = IRSessionStatus.DONE
    await db.commit()
    await db.refresh(session)
    return session


async def mark_needs_person(db: AsyncSession, session: IRSession) -> IRSession:
    session.status = IRSessionStatus.NEEDS_PERSON
    await db.commit()
    await db.refresh(session)
    return session


def back_translation_of(session: IRSession) -> BackTranslationState:
    return BackTranslationState.model_validate(session.back_translation or {})


async def save_back_translation(
    db: AsyncSession, session: IRSession, state: BackTranslationState
) -> IRSession:
    session.back_translation = state.model_dump(mode="json")
    await db.commit()
    await db.refresh(session)
    return session


async def begin_back_translation_again(
    db: AsyncSession, session: IRSession
) -> BackTranslationState:
    """Throw the telling-back away and start over on a freshly recorded clip.

    Only the re-record reaches here. Telling one stretch again does not pass through: it
    adds a chunk beside the others, and its budget is counted where that happens.
    """
    state = back_translation_of(session)
    # The retell count carries across. `BackTranslationState(scope=...)` takes every other
    # default, so it went back to zero — and re-recording is a room-key route the team
    # drives by voice. The budget that exists so a loop cannot be a loop was reachable by
    # tapping "record again", which is exactly the tap a stuck team makes.
    await save_back_translation(
        db,
        session,
        BackTranslationState(scope=state.scope, retells=state.retells),
    )
    return back_translation_of(session)
