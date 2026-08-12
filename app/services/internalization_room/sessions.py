from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.coverage import floor_met, initial_state

DEFAULT_PERICOPE = "P01"
PANORAMA_PREFIX = "OV-"
PANORAMA_ALIAS = "OV"


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
    db: AsyncSession, *, pericope: str = DEFAULT_PERICOPE, after_panorama: bool = False
) -> IRSession:
    pericope = resolve_pericope(pericope)
    panorama = is_panorama(pericope)
    if not panorama:
        load_map(pericope)  # refuse unapproved or unsupported canon before a session exists
    session = IRSession(
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
    await db.commit()
    await db.refresh(session)
    return session


async def apply_coverage(
    db: AsyncSession, session_id: str, coverage_state: dict[str, str]
) -> IRSession:
    """Store the tracker after the off-path classifier ran.

    Closes the session when the completion floor is met.
    """
    session = await get_session(db, session_id)
    session.coverage_state = coverage_state
    if (
        not is_panorama(session.pericope)
        and floor_met(coverage_state, session.pericope)
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
