from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.calibration import BridgeMode, is_selected_bridge_mode
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.session_readiness import (
    evaluate_session_comprehension,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.coverage import floor_met, furthest, initial_state

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
    bridge_mode: str | None = None,
) -> IRSession:
    pericope = resolve_pericope(pericope)
    panorama = is_panorama(pericope)
    if not panorama:
        load_map(pericope)  # refuse unapproved or unsupported canon before a session exists
    if bridge_mode is not None and not is_selected_bridge_mode(bridge_mode):
        raise ValidationError(f"Unknown bridge mode {bridge_mode!r}")
    if bridge_mode is None:
        bridge_mode = (
            BridgeMode.CALIBRATION_PENDING.value if panorama else BridgeMode.ADAPTIVE.value
        )
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
        bridge_mode=bridge_mode,
        comprehension={},
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

    Closes the session when the completion floor is met.
    """
    session = await get_session(db, session_id)
    # Merged against what is stored now, not written over it. The snapshot this was
    # computed from is a Gemini round trip old, and a second turn may have settled in the
    # meantime; a blind overwrite let the older reading win and darkened a bead the team
    # had already earned.
    session.coverage_state = furthest(
        session.coverage_state or {},
        coverage_state,
        pericope_num=session.pericope,
    )
    if (
        not is_panorama(session.pericope)
        and session_is_done(session)
        and session.status is IRSessionStatus.IN_PROGRESS
    ):
        session.status = IRSessionStatus.DONE
    await db.commit()
    await db.refresh(session)
    return session


async def set_bridge_mode(db: AsyncSession, session: IRSession, mode: str) -> IRSession:
    if not is_selected_bridge_mode(mode) and mode != BridgeMode.CALIBRATION_PENDING.value:
        raise ValidationError(f"Unknown bridge mode {mode!r}")
    session.bridge_mode = mode
    await db.commit()
    await db.refresh(session)
    return session


def comprehension_of(session: IRSession) -> ComprehensionState:
    return ComprehensionState.model_validate(session.comprehension or {})


async def save_comprehension(
    db: AsyncSession, session: IRSession, state: ComprehensionState
) -> IRSession:
    session.comprehension = state.model_dump(mode="json")
    await db.commit()
    await db.refresh(session)
    return session


def semantics_ready(session: IRSession) -> bool:
    """Whether the comprehension side of the gate is met — calibration done, readiness not
    `needs_more_work` (which already folds in per-scene mother-tongue practice)."""
    if session.bridge_mode == BridgeMode.CALIBRATION_PENDING.value:
        return False
    state = comprehension_of(session)
    readiness = evaluate_session_comprehension(
        checkpoints=list(checkpoints_for(session.pericope)),
        scene_ids=scene_ids_for(session.pericope),
        ledger=state.ledger,
        practiced_scene_ids=state.practiced_scene_ids,
    )
    return readiness.evaluation.outcome.value != "needs_more_work"


def session_is_done(session: IRSession) -> bool:
    """The full advance gate: coverage floor, semantic readiness with practice, and the
    team's explicit recording consent. Coverage bookkeeping alone can no longer end the
    interview — that is what let bridge-limited teams be judged on Portuguese output."""
    return (
        floor_met(session.coverage_state or {}, session.pericope)
        and semantics_ready(session)
        and comprehension_of(session).recording_consent_given
    )


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
