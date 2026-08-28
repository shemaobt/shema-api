from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.models.auth import User
from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    SupersededAttempt,
)
from app.services.internalization_room.calibration import BridgeMode, is_selected_bridge_mode
from app.services.internalization_room.canon.book_material import require_walkable
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_map
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.session_readiness import (
    evaluate_session_comprehension,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.coverage import (
    PANORAMA_PREFIX,
    floor_met,
    furthest,
    initial_state,
    is_panorama,
)
from app.services.internalization_room.coverage_events import record_transitions
from app.services.internalization_room.progression import active_passage
from app.services.internalization_room.segments import final_segments, retire_every_segment
from app.services.project.facilitated_scope import confined_to, facilitated_project_ids
from app.services.project.facilitates_project import facilitates_project

PANORAMA_ALIAS = "OV"
MAX_RETELLS = 3

#: Re-exported so the room's callers go on asking the session service what a panorama is.
#: The answer moved next to the coverage spine it is really about — see `coverage`.
__all__ = ["PANORAMA_ALIAS", "PANORAMA_PREFIX", "is_panorama"]


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
    bridge_mode: str | None = None,
) -> IRSession:
    """Open a session, on the passage this team is actually standing on.

    The meaning map is loaded before anything is written, so unapproved or unsupported
    canon is refused before a session exists — and so is a passage whose preservation layer
    nobody has written, which would otherwise be walked against a completion floor missing
    its top row. A panorama has no coverage spine and never completes: it prepares the team
    to enter the book, and asks no retelling of them.

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
        require_walkable(load_map(pericope))
    if bridge_mode is not None and not is_selected_bridge_mode(bridge_mode):
        raise ValidationError(f"Unknown bridge mode {bridge_mode!r}")
    if bridge_mode is None:
        bridge_mode = (
            BridgeMode.CALIBRATION_PENDING.value if panorama else BridgeMode.ADAPTIVE.value
        )
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

    Merged against what is stored now, not written over it. The snapshot this was computed
    from is a Gemini round trip old, and a second turn may have settled in the meantime; a
    blind overwrite let the older reading win and darkened a bead the team had already
    earned.

    Closing is the one end this schema stamps (ENG-451). A session ends either because the
    floor was met — an event, at an instant, written into ``ended_at`` here — or because
    nobody came back to it, which is derived from its last activity at read time and left
    unwritten, because the limit that decides it is not agreed with the room app. The
    ``IN_PROGRESS`` guard is what keeps the stamp a single instant: the classifier goes on
    settling whatever turns were already in flight when the floor was met, and a stamp on
    every one of them would grow the conversation's length after the team had finished.
    """
    session = await get_session(db, session_id)
    kept = session.coverage_state or {}
    settled = furthest(kept, coverage_state, pericope_num=session.pericope)
    record_transitions(db, session, before=kept, after=settled)
    session.coverage_state = settled
    if (
        not is_panorama(session.pericope)
        and session_is_done(session)
        and session.status is IRSessionStatus.IN_PROGRESS
    ):
        session.status = IRSessionStatus.DONE
        session.ended_at = datetime.now(UTC)
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


async def sessions_waiting_on_a_person(db: AsyncSession, user: User) -> list[IRSession]:
    """The sessions that need somebody, among the caller's own teams, newest first.

    Two states wait on a person and no third one does: a room that halted asked for
    someone to come, and a finished passage is waiting to be carried into Refine through
    the release route. A session still under way is waiting on the team, not on the
    facilitator.

    **Scoped to the teams the caller facilitates, and a team is a project.** The route this
    feeds was written to make halted rooms discoverable, on the argument that an id was
    never what kept the session routes shut — obscurity was not the access rule. That was
    true where it was written and stopped being true here: both routes addressed by a
    session id now refuse a session belonging to another team, `…/takes` through
    `get_session_for_facilitator` and `…/release` since ENG-563's composition. So an
    unscoped list would no longer be surfacing what was already readable. It would be
    announcing the existence, the passage and the moment of other teams' sessions — and
    handing over ids their reader cannot open.

    Scoped the way ENG-452 scoped the inbox, deliberately and not a second time from
    scratch: the ids in hand rather than `IN (SELECT …)`, which the planner cannot use.
    A session with no `project_id` belongs to no team and reaches nobody, which is the
    same rule questions follow — unowned is nobody's, not everybody's.

    The two halves drain differently, and only one of them drains at all. `NEEDS_PERSON`
    lifts itself the moment a turn lands, so a resumed room leaves on its own. `DONE` is
    terminal — nothing in this service writes a status back out of it, and reading the
    release does not mark a session as carried — so that half grows once per finished
    passage and never shrinks. At pilot volume that is a short list; it is not a shape
    that holds if the room outgrows the pilot, and the answer then is a state for
    "carried", not a page limit that would read as an empty queue.

    Newest first, because this is read as a queue.
    """
    result = await db.execute(
        select(IRSession)
        .where(
            IRSession.status.in_((IRSessionStatus.NEEDS_PERSON, IRSessionStatus.DONE)),
            confined_to(IRSession.project_id, await facilitated_project_ids(db, user)),
        )
        .order_by(IRSession.updated_at.desc())
    )
    return list(result.scalars())


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
    """Start the telling-back over on a freshly recorded clip, archiving the old attempt.

    Only the re-record reaches here. Telling one stretch again does not pass through: it
    adds a stretch beside the others, and its budget is counted where that happens.

    The replaced attempt is kept, clearly marked as superseded, rather than erased: its
    stretches and findings are the history the Refine artifact carries, and the team's open
    questions must survive their own retake. The stretches stay where they are and stop
    counting — nothing takes their place, because the clip they explained was thrown away —
    and only what was never theirs is copied in here.
    """
    state = back_translation_of(session)
    told = await final_segments(db, session.id)
    superseded = list(state.superseded)
    if told or state.findings:
        superseded.append(
            SupersededAttempt(
                findings=state.findings,
                evidence_sufficient=state.evidence_sufficient,
                played_ranges=state.played_ranges,
                clip_duration_ms=state.clip_duration_ms,
            )
        )
    await retire_every_segment(db, session.id)
    # The retell count carries across. `BackTranslationState(scope=...)` takes every other
    # default, so it went back to zero — and re-recording is a room-key route the team
    # drives by voice. The budget that exists so a loop cannot be a loop was reachable by
    # tapping "record again", which is exactly the tap a stuck team makes.
    await save_back_translation(
        db,
        session,
        BackTranslationState(scope=state.scope, retells=state.retells, superseded=superseded),
    )
    return back_translation_of(session)
