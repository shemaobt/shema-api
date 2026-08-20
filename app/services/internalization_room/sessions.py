from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_map
from app.services.internalization_room.coverage import floor_met, furthest, initial_state
from app.services.internalization_room.coverage_events import record_transitions
from app.services.internalization_room.progression import active_passage

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
    for it without naming the book — the canon stays entirely on this side.

    It expanded through `book_of(DEFAULT_PERICOPE)`, which asked a passage what book it
    belonged to in order to learn the only book there is. `ROOM_BOOK` is not that constant
    under another name: a book is not a passage, the room serves one, and `elements_for`,
    `labelled_elements` and `run_turn` already take it as a parameter.
    """
    if pericope == PANORAMA_ALIAS:
        return PANORAMA_PREFIX + ROOM_BOOK
    return pericope


async def create_session(
    db: AsyncSession,
    *,
    pericope: str | None = None,
    after_panorama: bool = False,
    project_id: str | None = None,
) -> IRSession:
    """Open a session, on the passage this team is actually standing on.

    ``pericope`` is optional and its absence is a question, not a default. It used to be
    ``DEFAULT_PERICOPE``, so a room that did not name a passage was answered the first one
    with full confidence — every team, every time, fourteen passages deep into a book none of
    them had ever left. Naming one still works and is obeyed: resolution fills a silence, it
    does not overrule a request.

    ``project_id`` is whose it is, when the device said so. Null is a normal answer, not a
    failure: the room app identifies itself with a device credential only from ENG-454 onward,
    and refusing a session without one would take every room in the field offline to gain a
    column value. Work with no project has no history to read, so it starts at the beginning.

    Raises ``ConflictError`` when the team has closed every passage and none was named. That
    is the end of the book, and it is a defined state rather than a wrap-around: the request
    is well formed and the team exists, so 409 rather than 400 or 404, and naming a passage is
    the way back in.
    """
    if pericope is None:
        pericope = await active_passage(db, project_id=project_id)
        if pericope is None:
            raise ConflictError(
                "This team has finished every passage of the book; name one to open a session"
            )
    pericope = resolve_pericope(pericope)
    panorama = is_panorama(pericope)
    if not panorama:
        load_map(pericope)  # refuse unapproved or unsupported canon before a session exists
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
        raise NotFoundError(f"Internalization room session {session_id} not found")
    return session


async def append_exchange(
    db: AsyncSession,
    session: IRSession,
    *,
    team_utterance: str,
    guide_response: str,
) -> IRSession:
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
