from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy import (
    JSON,
    ColumnElement,
    Text,
    and_,
    case,
    cast,
    delete,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import InstrumentedAttribute, set_committed_value

from app.core.exceptions import (
    ConflictError,
    HaltMoved,
    NotFoundError,
    PassageClosed,
    ValidationError,
)
from app.core.room_enums import HaltKind
from app.core.served_books import SERVED_BOOKS
from app.core.stage_clock import current_clock
from app.db.insert_once import insert_once
from app.db.models.auth import User
from app.db.models.internalization_room import (
    IRSession,
    IRSessionStatus,
    IRTake,
    IRTakeKind,
    IRTeamSession,
)
from app.models.internalization_room import PlayedTake
from app.services.device.demo_team import is_the_demo_team
from app.services.internalization_room import halt, turn_instructions
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    CheckRound,
    SupersededAttempt,
    findings_after_a_part_is_recorded_again,
    joined_spans,
)
from app.services.internalization_room.canon.book_material import require_walkable
from app.services.internalization_room.canon.kept import deployed_pin, reading_the_canon_of
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_map, not_served
from app.services.internalization_room.canon.scene_ids import scene_ids_for
from app.services.internalization_room.coverage import (
    PANORAMA_PREFIX,
    floor_met,
    furthest,
    initial_state,
    is_panorama,
)
from app.services.internalization_room.coverage_events import record_transitions
from app.services.internalization_room.earlier_passages import earlier_passages as read_earlier
from app.services.internalization_room.entered import latest_entered_first
from app.services.internalization_room.fail_safe import FailSafe
from app.services.internalization_room.hearing import SentSceneRehearsal
from app.services.internalization_room.languages import floor, normalize, room_language
from app.services.internalization_room.live import live
from app.services.internalization_room.moment import moment_step
from app.services.internalization_room.passage_lines import PANORAMA
from app.services.internalization_room.progression import active_passage
from app.services.internalization_room.segments import (
    final_segments,
    retire_every_segment,
    retire_the_segments_of,
)
from app.services.internalization_room.synthesize_facilitator_speech import (
    facilitator_speech_key,
)
from app.services.internalization_room.takes import current_parts, takes_of
from app.services.internalization_room.validated_turn import TurnOutcome, _the_validators_words
from app.services.project.facilitated_scope import confined_to, readable_project_ids
from app.services.project.facilitates_project import facilitates_project
from app.services.project.reads_project import reads_project

logger = logging.getLogger(__name__)

PANORAMA_ALIAS = "OV"
#: How many tellings of one stretch make it a hard stretch. Three is ours — measured in the
#: field at six against three with the passage checked — and the signal is Marcia's ruling of
#: 08/09: "keep it, as you have it: a mark, never a wall". Nothing is refused at or past this
#: number and the next stretch is taken like any other; what the crossing leaves behind is a
#: row for the facilitator and for the consultant, cleared by nothing that follows.
RETELLS_BEFORE_A_WARNING = 3

#: Re-exported so the room's callers go on asking the session service what a panorama is.
#: The answer moved next to the coverage spine it is really about — see `coverage`.
__all__ = ["PANORAMA_ALIAS", "PANORAMA_PREFIX", "is_panorama"]


def book_of(pericope: str) -> str:
    return pericope[len(PANORAMA_PREFIX) :] if is_panorama(pericope) else load_map(pericope).book


def resolve_pericope(pericope: str) -> str:
    """`OV` alone, and `PANORAMA` (`"panorama"`, the id the wheel once put on the wire), are
    Ruth's Panorama, for a tablet that names no book. Every served book's own Panorama is
    `OV-<Book>` (ADR 0066).
    """
    if pericope in (PANORAMA_ALIAS, PANORAMA):
        return PANORAMA_PREFIX + ROOM_BOOK
    return pericope


async def create_session(
    db: AsyncSession,
    *,
    pericope: str | None = None,
    after_panorama: bool = False,
    project_id: str | None = None,
    language: str | None = None,
    earlier_passages: Mapping[str, str] | None = None,
) -> IRSession:
    """Open a session, on the passage this team is actually standing on.

    The meaning map is loaded before anything is written, so a passage or a Panorama of a
    book the room does not serve is refused before a session exists (ADR 0066). A panorama
    has no coverage spine and never completes: it prepares the team to enter the book, and
    asks no retelling of them.

    ``pericope`` is optional and its absence is a question, not a default. It used to be
    ``DEFAULT_PERICOPE``, so a room that did not name a passage was answered the first one
    with full confidence — every team, every time, fourteen passages deep into a book none of
    them had ever left. Naming one still works and is obeyed: resolution fills a silence, it
    does not overrule a request.

    ``language`` is which language the room will speak to this team, and it is decided here
    and nowhere later. The tablet reads it off its own locale and names it once; every turn on
    this session then answers in it. Carrying it per request instead would let the language
    move under a team because somebody opened the phone settings mid-passage. A caller that
    names none takes the floor; one that names a language the room does not speak is refused,
    because answering it in another language is a wrong answer the caller cannot detect.

    ``project_id`` is whose it is, when the device said so. Null is a normal answer, not a
    failure: the room app identifies itself with a device credential only from ENG-454 onward,
    and refusing a session without one would take every room in the field offline to gain a
    column value. Work with no project has no history to read, so it starts at the beginning.

    A new session starts fresh, as hers does (`freshState`, `src/session/store.ts`): every
    bead at not encountered, whatever the team's earlier sessions or coverage events hold.

    The pericope asked for is the pericope opened, the Panorama included: a team that already
    heard the book's panorama and asks for it again is opened the panorama (ENG-1237, folded
    from ENG-1282). Only a silence is filled, never a request overruled.

    Raises ``ConflictError`` when the team has closed every passage that opens in every served
    book and none was named. That is the end of the walk, and it is a defined state rather than
    a wrap-around: the request is well formed and the team exists, so 409 rather than 400 or
    404, and naming a passage is the way back in. The end it names is the end of the walkable
    books, the only end a team can reach — a passage `require_walkable` refuses can never be
    closed.

    ``earlier_passages`` is this team's status on each earlier passage of the book, kept on
    the session and never in its messages, so a session holding one has still not spoken. A
    caller that hands one in (the Golden door) is taken at its word; otherwise the room reads
    it itself when the session is created (`earlier_passages`), and again after a turn once it
    is five minutes old.
    """
    pericope, after_panorama, spoken = await _resolved(
        db,
        pericope=pericope,
        after_panorama=after_panorama,
        project_id=project_id,
        language=language,
        book=None,
    )
    session = await _minted(
        db,
        pericope=pericope,
        after_panorama=after_panorama,
        project_id=project_id,
        language=spoken,
        earlier_passages=earlier_passages,
    )
    await db.commit()
    await db.refresh(session)
    return session


async def open_session(
    db: AsyncSession,
    *,
    pericope: str | None = None,
    project_id: str,
    after_panorama: bool = False,
    language: str | None = None,
    after: IRSession | None = None,
) -> tuple[IRSession, bool]:
    """The session the room's open door returns, and whether this open created it.

    Every open asks the server, and the server answers with the session it holds for this
    team, pericope and language, whatever its state: a second tablet, a reinstall and a
    relaunch all land on the conversation the team was having. One is minted only when none
    exists, and then exactly once: the key is claimed in the same transaction that mints, and
    an open that loses the claim to another deletes its own row before anything is committed
    and returns the winner's, so no orphan is left. Deleted rather than rolled back, because a
    rollback would expire every row the caller already read on this session.

    A key nobody has claimed yet may still name stored sessions — written before the claim
    existed, or by a server still running the old door while the new one rolls out — and the
    one claimed is the latest the team entered, by ``updated_at``, then ``created_at``, then
    ``id`` (`_latest_stored`).

    The Panorama is opened by the same rule, so a team choosing to hear it again is returned
    the Panorama session it already has; replaying it is not this door's to decide.

    A resumed session keeps what it is, except the panorama mark: an open that says it came
    from the Panorama sets ``after_panorama`` on the session it lands on, or a pericope opened
    before the Panorama would leave `heard_panorama` false, and the route would write the
    Panorama's opening ahead again.

    A tablet that opens a session halted by its call for a person is back in the room, so the
    open writes what a landed turn writes for it (`_a_teams_return`): the halt lifts. A warning
    stands, because a facilitator's visit is its only exit (ADR 0039).

    An open that names no passage lands on the team's next passage of the book of the session
    it came from, ``after``, and of the team's Current book when it came from none (ADR 0066,
    ADR 0094).
    """
    pericope, after_panorama, spoken = await _resolved(
        db,
        pericope=pericope,
        after_panorama=after_panorama,
        project_id=project_id,
        language=language,
        book=book_of(after.pericope) if after is not None else None,
    )
    session = await _pointed(db, project_id, pericope, spoken)
    created = False
    if session is None:
        stored = await _latest_stored(db, project_id, pericope, spoken)
        created = stored is None
        session = stored or await _minted(
            db,
            pericope=pericope,
            after_panorama=after_panorama,
            project_id=project_id,
            language=spoken,
        )
        winner = await _claim(db, session)
        if winner != session.id:
            if created:
                await db.delete(session)
                await db.flush()
            session, created = await get_session(db, winner), False
    if after_panorama and not session.after_panorama:
        session.after_panorama = True
    if session.status is IRSessionStatus.NEEDS_PERSON:
        await db.execute(
            update(IRSession)
            .where(IRSession.id == session.id)
            .values(**_a_teams_return(session))
            .execution_options(synchronize_session=False)
        )
    await db.commit()
    await db.refresh(session)
    return session, created


async def _pointed(
    db: AsyncSession, project_id: str, pericope: str, language: str
) -> IRSession | None:
    """The live session the key's pointer names, or ``None`` when there is none to return.

    A pointer whose session is gone or archived is no pointer at all: left in place it would
    404 every open of that key for good, and beat the next claim. It is deleted by the session
    it names, so a pointer another open has just claimed again is never the one deleted.
    """
    claimed = await db.scalar(
        select(IRTeamSession.session_id).where(*_team_key(project_id, pericope, language))
    )
    if claimed is None:
        return None
    session = await db.scalar(select(IRSession).where(IRSession.id == claimed, live()))
    if session is None:
        await db.execute(
            delete(IRTeamSession).where(
                *_team_key(project_id, pericope, language), IRTeamSession.session_id == claimed
            )
        )
    return session


def _team_key(
    project_id: str | None, pericope: str, language: str
) -> tuple[ColumnElement[bool], ...]:
    return (
        IRTeamSession.project_id == project_id,
        IRTeamSession.pericope == pericope,
        IRTeamSession.language == language,
    )


async def _latest_stored(
    db: AsyncSession, project_id: str, pericope: str, language: str
) -> IRSession | None:
    """The team's stored session of this key: the latest one it entered, by `entered`'s rule,
    and the latest of any kind only when it entered none. The old door minted a session on
    every relaunch that the tablet then left empty, so the newest row is often a launch
    nobody entered, and resuming it would hand the team an empty conversation for good.
    """
    stored = await db.execute(
        select(IRSession)
        .where(
            IRSession.project_id == project_id,
            IRSession.pericope == pericope,
            IRSession.language == language,
            live(),
        )
        .order_by(*latest_entered_first())
        .limit(1)
    )
    return stored.scalar_one_or_none()


async def _claim(db: AsyncSession, session: IRSession) -> str:
    """Point the key at this session unless another open already did, and say who holds it."""
    await insert_once(
        db,
        IRTeamSession,
        {
            "project_id": session.project_id,
            "pericope": session.pericope,
            "language": session.language,
            "session_id": session.id,
        },
        conflict_on=["project_id", "pericope", "language"],
    )
    held = await db.execute(
        select(IRTeamSession.session_id).where(
            *_team_key(session.project_id, session.pericope, session.language)
        )
    )
    return held.scalar_one()


async def _resolved(
    db: AsyncSession,
    *,
    pericope: str | None,
    after_panorama: bool,
    project_id: str | None,
    language: str | None,
    book: str | None,
) -> tuple[str, bool, str]:
    """Which pericope, panorama mark and language an open is for, before anything is written."""
    if pericope is None:
        pericope = await active_passage(db, project_id=project_id, book=book)
        if pericope is None:
            raise ConflictError(
                "This team has finished every passage the book can walk; name one to open a session"
            )
    pericope = resolve_pericope(pericope)
    if is_panorama(pericope):
        if (book := book_of(pericope)) not in SERVED_BOOKS:
            raise ValidationError(not_served(book))
    else:
        require_walkable(load_map(pericope))
    spoken = normalize(language)
    if language is not None and spoken is None:
        raise ValidationError(f"The room does not speak {language!r}")
    return pericope, after_panorama, spoken or floor()


async def _minted(
    db: AsyncSession,
    *,
    pericope: str,
    after_panorama: bool,
    project_id: str | None,
    language: str,
    earlier_passages: Mapping[str, str] | None = None,
) -> IRSession:
    """A new session on a resolved pericope, flushed and not yet committed.

    Every bead starts at the canon's spine and nothing is laid over it. A panorama has no
    coverage spine and never completes: it prepares the team to enter the book, and asks no
    retelling of them.

    The earlier-passages stamp is the caller's when one is handed in, and otherwise read here,
    before the open claims its key: an open that loses the claim deletes this row, and its
    stamp with it.
    """
    stamp = (
        dict(earlier_passages)
        if earlier_passages
        else await read_earlier(db, project_id=project_id, pericope=pericope)
    )
    session = IRSession(
        project_id=project_id,
        pericope=pericope,
        status=IRSessionStatus.IN_PROGRESS,
        messages=[],
        after_panorama=after_panorama,
        coverage_state={} if is_panorama(pericope) else initial_state(pericope),
        back_translation={},
        language=language,
        comprehension={},
        earlier_passages=stamp,
        canon_pin=deployed_pin(),
    )
    db.add(session)
    await db.flush()
    return session


async def stored_as_done(db: AsyncSession, session_id: str) -> bool:
    """Whether the session is done as stored now, past the copy a request already holds."""
    status = await db.scalar(select(IRSession.status).where(IRSession.id == session_id))
    return status is IRSessionStatus.DONE


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


async def get_session_for_reader(db: AsyncSession, user: User, session_id: str) -> IRSession:
    """``get_session_for_facilitator`` for a read: a consultant reads every team's session.

    Read by ``get_session``, so an archived session is still served by its id (ADR 0052).
    """
    session = await get_session(db, session_id)
    if session.project_id is None or not await reads_project(db, user, session.project_id):
        raise NotFoundError(_no_such_session(session_id))
    return session


async def session_for_room_caller(db: AsyncSession, session_id: str, project_id: str) -> IRSession:
    """The session, if it belongs to the team of the tablet asking.

    Every team door reads a session through here. Somebody else's session is refused as not
    found, with the message `get_session_for_facilitator` gives, and so is a session that
    names no team at all — left by callers on the retired shared key, it is nobody's to reach
    (ADR 0057).
    """
    session = await _the_live_session(db, session_id)
    if session.project_id != project_id:
        raise NotFoundError(_no_such_session(session_id))
    return session


async def _the_live_session(db: AsyncSession, session_id: str) -> IRSession:
    """The session, refused as gone once a Zerar archived it, with the unknown session's own
    words: the tablet reads that as the session gone and returns to the Choice (ADR 0047).
    """
    session = await get_session(db, session_id)
    if session.archive_id is not None:
        raise NotFoundError(_no_such_session(session_id))
    return session


async def _land(
    db: AsyncSession, session: IRSession, values: dict[str, Any], *, commit: bool = True
) -> IRSession:
    """Write ``values`` to this session's row, refusing the write if another turn got there
    first (ENG-643).

    ``messages`` is whole-value JSON, computed from whatever the caller had read off
    ``session`` before calling this — so a plain UPDATE would let a turn that started a
    moment later, and committed a moment earlier, have its evidence silently written over.
    The WHERE clause below is the guard: it only lands while ``version`` is still what this
    ``session`` was read at, and the loser gets a raised conflict instead of a clean-looking
    overwrite. Mirrors the compare-and-swap `autosave_state.py` runs for the
    sound necklace's own document, generalised to whichever columns the caller is writing.

    A Zerar is a write too, and moves ``version``: a turn that resolved the session while it was
    live and lands after the Zerar finds nothing to land on, and is answered as the session
    gone, with the unknown session's words, rather than as another turn's conflict (ADR 0052).
    """
    await db.flush()
    stmt = (
        update(IRSession)
        .where(IRSession.id == session.id, IRSession.version == session.version)
        .values(**values, version=IRSession.version + 1)
        .returning(
            IRSession.version,
            IRSession.coverage_state,
            IRSession.status,
            IRSession.ended_at,
            IRSession.updated_at,
        )
        .execution_options(synchronize_session=False)
    )
    landed = (await db.execute(stmt)).one_or_none()
    if landed is None:
        await refuse_if_archived(db, session)
        # Nothing matched, so nothing is pending: leave the transaction to the caller's
        # teardown rather than rolling back a session shared with the rest of the request,
        # the way autosave_state.py's own version conflict does.
        raise ConflictError("This session was written to by another turn.")
    for key, value in {**values, **landed._mapping}.items():
        set_committed_value(session, key, value)
    if commit:
        await db.commit()
    return session


async def claim_the_version(db: AsyncSession, session: IRSession) -> None:
    """Take this session's version for a write that lands beside the session rather than on
    it, a release minted on it, so a Zerar or a turn that moved it first refuses this one the
    way `_land` refuses a turn (ADR 0066).

    `updated_at` is written its own value, as `prepare_opening` and the Zerar write it: the
    Desk reads it as the last time the team spoke, and a release a facilitator forced is not
    the team speaking.
    """
    await _land(db, session, {"updated_at": IRSession.updated_at}, commit=False)


async def refuse_if_archived(db: AsyncSession, session: IRSession) -> None:
    """Refuse a session a Zerar archived, as stored now and not as it was read, with the
    unknown session's words (ADR 0052)."""
    if await db.scalar(select(IRSession.archive_id).where(IRSession.id == session.id)):
        raise NotFoundError(_no_such_session(session.id))


async def append_exchange(
    db: AsyncSession,
    session: IRSession,
    *,
    team_utterance: str,
    guide_response: str,
    outcome: TurnOutcome | None = None,
    attempts: list[dict[str, Any]] | None = None,
    scene: str | None = None,
    told_back: str = "",
    commit: bool = True,
    scene_rehearsals: list[str] | None = None,
    opening_note: str = "",
    scene_rehearsal: SentSceneRehearsal | None = None,
) -> IRSession:
    """Append one team/guide turn to the transcript, and what containment did to it.

    The guide message says whether the draft passed, was mended, or gave way to a fixed
    line, and how many redrafts it cost. When a fixed line spoke, the message also keeps
    what her fail-safe spec asks of every firing — the pericope, the scene, the team's
    words, the Guide's draft, the Validator's verdict, its issues as text (problem, claim and
    explanation, nothing else a reply carried) and which family answered — so a session read
    back later never has to infer any of it. A turn that arrives with no outcome, the prepared
    opening, is written as it always was.

    A take that followed a cut keeps where the cut fell on this turn's guide entry, beside the
    hearing facts; the entry of the reply that was cut is never touched.

    In the telling-back round nobody speaks into the conversation, so no team turn is
    appended; what the team said there is the telling-back itself, and `told_back` is what
    the record keeps as the team's words when that round fires. It has no scene: the
    verdict is read against the stretches told, not against a pointer on the map.

    A turn that lands is the team's return, so it releases `NEEDS_PERSON`; with a tablet
    opening the session, it is the only way out of a blocking halt (ADR 0076). It never ends
    a warning (ENG-1163): a warning refuses nothing, so the team going on is no sign anybody
    came, and it stands until a facilitator attends the session. Only a halt already standing
    when the turn began is lifted: one the tablet raised while the Guide was still answering
    is a request nobody has answered yet. The visit's stamps are **not** cleared: who went
    and when is what the history is for.

    ``scene_rehearsals`` is the scenes whose scene rehearsal had reached the Guide as of this
    turn, kept on the Guide's entry, the one entry every turn has; an empty list is the fact
    that none had, and ``None`` keeps nothing. ``scene_rehearsal`` is the one a **Rehearsal
    turn** sent, kept on the same entry with the scene label as it stood at sending.

    What the room heard of the team's take — the language, its probability, the
    mother-tongue decision and the take's length — goes on the Guide's entry too, because a
    mother-tongue turn writes only her note and a missed one writes only «(inaudible)», her
    mark for a team that spoke and was not heard. Only a turn the room heard
    carries them; the opening and the telling-back verdict write none. What the Guide was
    handed as the team's turn rides with them: empty on a miss, which reached no Guide.

    The Guide's entry also keeps the rung that answered and the turn's recognition and reply
    times, when the turn has them, and always the key of the clip its line is voiced under,
    computed here from the words, so the facilitator plays the line the team heard without
    a second write once the voice is made.
    """
    messages: list[dict[str, Any]] = list(session.messages or [])
    stamp: dict[str, Any] = {"at": datetime.now(UTC).isoformat()}
    if told_back:
        stamp["told_back"] = True
    if opening_note:
        messages.append({"role": "team", "text": opening_note, "opening_note": True, **stamp})
    if outcome is not None and outcome.room_note:
        messages.append({"role": "team", "text": outcome.room_note, "room_note": True, **stamp})
    if team_utterance:
        messages.append({"role": "team", "text": team_utterance, **stamp})
    elif (
        outcome is not None
        and outcome.mother_tongue is not None
        and outcome.fixed_line.startswith(FailSafe.INAUDIBLE)
    ):
        messages.append({"role": "team", "text": "(inaudible)", **stamp})
    guide: dict[str, Any] = {"role": "guide", "text": guide_response, **stamp}
    if outcome is not None:
        guide["outcome"] = _containment_of(outcome)
        guide["redrafts"] = outcome.redrafts
        if outcome.used_fail_safe:
            guide.update(
                category=outcome.fixed_line[:1] or str(FailSafe.UNREPAIRABLE),
                fixed_line=outcome.fixed_line,
                pericope=session.pericope,
                scene=scene,
                team_utterance=team_utterance or told_back,
                draft=outcome.draft,
                verdict=outcome.verdict,
                issues=_the_validators_words(outcome.issues),
            )
        if outcome.mother_tongue is not None:
            guide.update(
                language=outcome.language,
                language_probability=outcome.language_probability,
                mother_tongue=outcome.mother_tongue,
                take_ms=outcome.take_ms,
                guide_heard=outcome.guide_heard,
            )
        if outcome.interrupted is not None:
            guide["interrupted"] = asdict(outcome.interrupted)
        if outcome.model is not None:
            guide["model"] = outcome.model
        guide.update(_the_turns_times())
    guide["voice_key"] = facilitator_speech_key(guide_response, language=session.language)
    kept = attempts or (outcome.attempts if outcome is not None else [])
    if kept:
        guide["attempts"] = kept
    if scene_rehearsals is not None:
        guide["scene_rehearsals"] = scene_rehearsals
    if scene_rehearsal is not None:
        guide["scene_rehearsal"] = scene_rehearsal.model_dump()
    if outcome is not None and outcome.accepted_ids:
        guide["accepted_ids"] = outcome.accepted_ids
    step = (
        None
        if is_panorama(session.pericope)
        else moment_step(
            session.messages or [],
            guide_response,
            fail_safe=outcome is not None and outcome.used_fail_safe,
            scenes=scene_ids_for(session.pericope),
            arriving=scene_rehearsal,
            reached=scene_rehearsals,
        )
    )
    if step is not None:
        guide["moment"] = step.as_json()
    messages.append(guide)
    values: dict[str, Any] = {"messages": messages, **_a_teams_return(session)}
    return await _land(db, session, values, commit=commit)


def _the_turns_times() -> dict[str, int]:
    """The take's recognition and the Guide's and the Validator's work together, in
    milliseconds, as the request's stage clock measured them; nothing a clock did not measure.
    """
    clock = current_clock()
    stages = clock.stages if clock is not None else {}
    times = {"recognition_ms": stages["stt"]} if "stt" in stages else {}
    replied = [stages[role] for role in ("guide", "validator") if role in stages]
    if replied:
        times["reply_ms"] = sum(replied)
    return times


def _a_teams_return(session: IRSession) -> dict[str, Any]:
    """What the team coming back to a room writes, as of the row ``session`` was read at.

    One rule for every return the team makes, a landed turn or a tablet opening the session
    again (ADR 0045). A blocking halt that was read lifts, guarded by ``halts_raised`` so a
    halt raised between the read and the write is a new ask and stands, and by the status so
    a lift that lost the race restores nothing.
    """
    if session.status is not IRSessionStatus.NEEDS_PERSON:
        return {}
    return {
        "status": case(
            (
                and_(
                    IRSession.status == IRSessionStatus.NEEDS_PERSON,
                    IRSession.halts_raised == session.halts_raised,
                ),
                halt.a_lift_restores(),
            ),
            else_=IRSession.status,
        ),
    }


def _containment_of(outcome: TurnOutcome) -> str:
    if outcome.used_fail_safe:
        return "fail_safe"
    if outcome.verdict == "correct":
        return "corrected"
    return "pass"


_STORED_JSON = Text().with_variant(JSONB(), "postgresql")


_TRIES = 5

_Stored = dict[str, Any]
_JSONColumn = InstrumentedAttribute[_Stored] | InstrumentedAttribute[_Stored | None]


async def _written_forward(
    db: AsyncSession,
    session_id: str,
    column: _JSONColumn,
    read: _Stored | None,
    onto: Callable[[_Stored | None], Awaitable[_Stored]],
) -> tuple[_Stored | None, _Stored]:
    for tries_left in reversed(range(_TRIES)):
        value = await onto(read)
        if value == read or await _written_unless_moved(db, session_id, column, read, value):
            return read, value
        if not tries_left:
            break
        logger.warning(
            "Session %s: a stale read of %s was refused and is redone on the fresh reading",
            session_id,
            column.key,
        )
        read = await db.scalar(select(column).where(IRSession.id == session_id))
    logger.warning(
        "Session %s: a stale read of %s was refused and the write gives up after %d tries",
        session_id,
        column.key,
        _TRIES,
    )
    raise ConflictError(f"Session {session_id}: {column.key} kept moving under every try")


async def _written_unless_moved(
    db: AsyncSession, session_id: str, column: _JSONColumn, read: _Stored | None, value: _Stored
) -> bool:
    unmoved: ColumnElement[bool] = cast(column, _STORED_JSON).is_not_distinct_from(
        cast(literal(read, JSON), _STORED_JSON)
    )
    if read is None:
        unmoved = or_(column.is_(None), unmoved)
    written = await db.execute(
        update(IRSession)
        .where(IRSession.id == session_id, unmoved)
        .values({column: value})
        .execution_options(synchronize_session=False)
    )
    return written.rowcount == 1


async def apply_coverage(
    db: AsyncSession,
    session_id: str,
    coverage_state: dict[str, str],
    *,
    retellings: dict[str, Any] | None = None,
) -> IRSession:
    """Store the tracker after the off-path classifier ran.

    Closes the session when the completion floor is met, and leaves an event behind for
    every bead that moved — the merge is compared against what is stored before anything
    is written, so a classifier round that reports no news costs no rows.

    Merged against what is stored now, not written over it. The snapshot this was computed
    from is a Gemini round trip old, and a second turn may have settled in the meantime; a
    blind overwrite let the older reading win and darkened a bead the team had already
    earned.

    Closing is the one end this schema knows (ENG-451, ENG-1263): the floor was met, an event
    at an instant, written into ``ended_at`` here while the status becomes ``done``. Nothing
    else ends a session; an idle one is simply in progress. The ``IN_PROGRESS`` guard is what
    keeps the stamp a single instant: the classifier goes on settling whatever turns were
    already in flight when the floor was met, and a stamp on every one of them would grow the
    conversation's length after the team had finished.
    """
    session = await get_session(db, session_id)

    async def onto(read: dict[str, Any] | None) -> dict[str, str]:
        return furthest(read or {}, coverage_state, pericope_num=session.pericope)

    kept, settled = await _written_forward(
        db, session.id, IRSession.coverage_state, session.coverage_state, onto
    )
    record_transitions(db, session, before=kept or {}, after=settled)
    set_committed_value(session, "coverage_state", settled)
    if retellings:

        async def told(read: dict[str, Any] | None) -> dict[str, Any]:
            return {**(read or {}), **retellings}

        _, retold = await _written_forward(
            db, session.id, IRSession.retellings, session.retellings, told
        )
        set_committed_value(session, "retellings", retold)
    if not is_panorama(session.pericope) and session_is_done(session) and session.ended_at is None:
        await db.execute(
            update(IRSession)
            .where(IRSession.id == session.id, IRSession.ended_at.is_(None))
            .values(
                status=case(
                    (
                        IRSession.status == IRSessionStatus.IN_PROGRESS,
                        literal(IRSessionStatus.DONE, IRSession.status.type),
                    ),
                    else_=IRSession.status,
                ),
                ended_at=datetime.now(UTC),
            )
            .execution_options(synchronize_session=False)
        )
    await db.commit()
    await db.refresh(session)
    return session


def was_opened(session: IRSession) -> bool:
    """Whether the session holds a Guide line: a room note or a team entry alone does not open it.

    Every reader asks this: the session state, the turn door, the Opening's write and the
    hand-over of a prepared one.
    """
    return any(line.get("role") == "guide" for line in session.messages or [])


def the_opening_note(session: IRSession) -> str:
    language = room_language(session.language)
    if is_panorama(session.pericope):
        return turn_instructions.panorama_note(book_of(session.pericope), language)
    return turn_instructions.opening_note(session.pericope, language)


async def append_opening(
    db: AsyncSession,
    session: IRSession,
    *,
    guide_response: str,
    outcome: TurnOutcome | None = None,
    attempts: list[dict[str, Any]] | None = None,
    scene: str | None = None,
    commit: bool = True,
) -> bool:
    """The opening written as the Guide's first line, or dropped when the Guide has spoken first.

    The opening is read off an empty session and only comes back to be written after the
    Guide has answered, which in the room has taken eleven minutes: long enough for the
    tablet to give up, the team to speak, and the Guide's answer to their turn to be stored
    first. Written then, it stood behind that answer as a line the Guide never said in that
    order; refused by the row's version instead, it was gone and the tablet was never told. So
    the session is read again here, and an opening that finds the Guide's line already stored
    is dropped from the record and logged — the tablet still hears the line it asked for. A
    team entry with no Guide line does not open the session, so the opening is written behind
    it.
    """
    await db.refresh(session, ["messages", "version"])
    if was_opened(session):
        await db.refresh(session)
        logger.warning(
            "The opening of session %s landed after the session was opened; dropped, not appended",
            session.id,
        )
        return False
    await append_exchange(
        db,
        session,
        team_utterance="",
        guide_response=guide_response,
        outcome=outcome,
        attempts=attempts,
        scene=scene,
        commit=commit,
        opening_note=the_opening_note(session),
    )
    return True


def session_is_done(session: IRSession) -> bool:
    """The advance gate: the coverage floor, and nothing the team said about rehearsing.

    Her room calls a passage done when every element has the status its kind needs, and
    reads neither practice, a report nor the team's words.
    """
    with reading_the_canon_of(session.canon_pin):
        return floor_met(session.coverage_state or {}, session.pericope)


async def sessions_waiting_on_a_person(db: AsyncSession, user: User) -> list[IRSession]:
    """The sessions that need somebody, among the caller's own teams, newest first.

    Three things wait on a person and no fourth one does: a room that halted asked for
    someone to come, a room under a standing warning asked for someone to come and watch
    while it goes on (ENG-1163 — the warning is not a status, so it is named here beside the
    two states), and a finished passage is waiting to be carried into Refine through the
    release route. Any other session still under way is waiting on the team, not on the
    facilitator.

    **Scoped to the teams the caller reads, and a team is a project.** The route this
    feeds was written to make halted rooms discoverable, on the argument that an id was
    never what kept the session routes shut — obscurity was not the access rule. That was
    true where it was written and stopped being true here: both routes addressed by a
    session id now refuse a session belonging to another team, `…/takes` through
    `get_session_for_reader` and `…/release` since ENG-563's composition. So an
    unscoped list would no longer be surfacing what was already readable. It would be
    announcing the existence, the passage and the moment of other teams' sessions — and
    handing over ids their reader cannot open.

    Scoped the way ENG-452 scoped the inbox, deliberately and not a second time from
    scratch: the ids in hand rather than `IN (SELECT …)`, which the planner cannot use.
    A session with no `project_id` belongs to no team and reaches nobody, which is the
    same rule questions follow — unowned is nobody's, not everybody's.

    The halves drain differently, and only the halts drain at all. A facilitator marking the
    room attended drains both: a warning ends, and a halted room is listed only while nobody
    is marked as having gone, though its status stays the team's to lift (ADR 0076). `DONE` is
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
            or_(
                and_(
                    IRSession.status == IRSessionStatus.NEEDS_PERSON,
                    IRSession.attended_at.is_(None),
                ),
                IRSession.status == IRSessionStatus.DONE,
                halt.a_warning_stands(),
            ),
            live(),
            confined_to(IRSession.project_id, await readable_project_ids(db, user)),
        )
        .order_by(IRSession.updated_at.desc())
    )
    return list(result.scalars())


async def mark_needs_person(db: AsyncSession, session: IRSession) -> IRSession:
    """Halt the room with a blocking halt: it cannot go on until a person comes.

    A closed passage refuses the ask and writes nothing (ADR 0044), even one closed after
    ``session`` was read.

    ``halts_raised`` counts blocking halts only: it is how a landing turn tells the halt it
    began in from one raised while the Guide was answering, and a warning is neither.

    **A new ask is an unattended ask**, so the update that raises the halt also clears the
    visit that answered the previous one, and the room is back on the queue. It clears it in
    the same statement so a visit that landed after ``session`` was read is cleared too. A
    warning that visit ended stays ended: once the stamps go the visit can no longer be
    undone, so what it ended is final.
    """
    halted = await db.execute(
        update(IRSession)
        .where(IRSession.id == session.id, IRSession.ended_at.is_(None))
        .values(
            status=IRSessionStatus.NEEDS_PERSON,
            halts_raised=IRSession.halts_raised + 1,
            warned_at=case((IRSession.attended_at.is_not(None), None), else_=IRSession.warned_at),
            attended_at=None,
            attended_by=None,
        )
        .execution_options(synchronize_session=False)
    )
    if halted.rowcount == 0:
        raise PassageClosed("The passage is closed and no longer asks for a person.")
    _a_new_ask(session, kind=HaltKind.BLOCKING)
    if await is_the_demo_team(db, session.project_id):
        await db.flush()
        await db.refresh(session, ["status", "halts_raised", "warned_at", "attended_at"])
        return await attend(
            db, session, by=None, halts_raised=session.halts_raised, warned_at=session.warned_at
        )
    return await _written(db, session, commit=True)


async def raise_a_warning(
    db: AsyncSession, session: IRSession, *, commit: bool = True
) -> IRSession:
    """Call somebody over without stopping the room: a stretch crossed into a hard stretch.

    **The status is not written** (ENG-1163). A warning refuses nothing, so the session stays
    where it was — in progress, or done — and the warning stands beside it until a facilitator
    attends the session (``halt.standing``). A new warning is an unattended one, so the update
    that raises it also clears the visit that answered the previous halt, in the same
    statement so a visit that landed after ``session`` was read is cleared too.
    """
    await db.execute(
        update(IRSession)
        .where(IRSession.id == session.id)
        .values(warned_at=datetime.now(UTC), attended_at=None, attended_by=None)
        .execution_options(synchronize_session=False)
    )
    await db.refresh(session, ["warned_at", "attended_at", "attended_by"])
    _a_new_ask(session, kind=HaltKind.WARNING)
    if await is_the_demo_team(db, session.project_id):
        _visited(session, by=None)
    return await _written(db, session, commit=commit)


def _a_new_ask(session: IRSession, *, kind: HaltKind) -> None:
    """What every halt writes, whichever its kind.

    The kind is written on every halt and cleared by none — see ``halt.last``. The visit is
    cleared by each kind's own update, in ``mark_needs_person`` and ``raise_a_warning``.
    """
    session.halt_kind = kind.value
    session.person_arrived_at = None


async def _written(db: AsyncSession, session: IRSession, *, commit: bool) -> IRSession:
    """Close the halt's write, or leave the transaction open when ``commit`` is False.

    ``commit=False`` leaves the transaction open so a caller can write more in it. The mark of a
    hard stretch is the one that needs it: the row that records the crossing and the halt that
    asks for somebody are one fact, and committed apart a failure between them leaves a stretch
    marked hard in a room that never asked for anybody.
    """
    if commit:
        await db.commit()
        await db.refresh(session)
    else:
        await db.flush()
        await db.refresh(session, ["halts_raised"])
    return session


async def person_arrived(db: AsyncSession, session: IRSession) -> datetime:
    """Somebody long-pressed this halted room to say they are here (ENG-792).

    **First press wins.** The moment records when a person reached the room, and one that
    moved on every press would record the last time a hand touched the screen instead — a
    team pressing again because nothing visibly happened would keep resetting the one fact
    the Desk reads off this row.

    The moment belongs to the halt it answers, so every new halt clears it: a room that
    stopped again is asking again, and carrying the arrival forward would show the new halt as
    already answered by somebody who came for the old one.

    Not gated on the room being halted. A press can only come from a screen that is showing
    the halt, and refusing one that arrives just as a turn lands would lose the arrival of a
    person who is standing in the room either way.

    Answers the moment rather than the row, the way ``record_needs_person`` does on the device
    side: the caller wants the one thing this writes, and a row typed as nullable would make
    every caller handle a null this function has just ruled out.
    """
    if session.person_arrived_at is None:
        session.person_arrived_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(session)
    return session.person_arrived_at


async def attend(
    db: AsyncSession,
    session: IRSession,
    *,
    by: str | None,
    halts_raised: int,
    warned_at: datetime | None,
) -> IRSession:
    """A facilitator says they went to this room: a Visit, which writes nothing on the status.

    The visit is the only exit a warning has (ADR 0039): it ends because ``attended_at`` is now
    set, and undoing the visit brings it back, except on a demo team, whose undo is attended
    again at once (ADR 0064). A blocking halt is the team's to lift, and the
    visit only takes the room off the queue (ADR 0076).

    **It names the halt it answers** (ADR 0091): ``halts_raised`` and ``warned_at`` as the
    Desk read them. The count moves with a blocking halt only (ADR 0039), and ``warned_at``
    with a warning. The stamp is written only while both are still the room's, in the same
    statement, so a halt raised after the read is never hidden by a visit to the one before.

    **Idempotent, keeping the first stamp.** Two taps are one visit, and a stamp that moved on
    every tap would record when somebody last touched the Desk rather than when they went to
    the room — and the moment of the visit is the whole of what this field is for.

    ``by`` is None when nobody went: the server stamps a demo team's halt itself (ADR 0064).

    ``updated_at`` is written its own value: a visit is not the team's act, and the team's
    Current book reads its latest session by that column (ADR 0094).
    """
    visited = await db.execute(
        update(IRSession)
        .where(
            IRSession.id == session.id,
            _the_halt_named(halts_raised, warned_at),
            IRSession.attended_at.is_(None),
        )
        .values(attended_at=datetime.now(UTC), attended_by=by, updated_at=IRSession.updated_at)
        .execution_options(synchronize_session=False)
    )
    return await _visit_written(
        db, session, written=visited.rowcount, halts_raised=halts_raised, warned_at=warned_at
    )


def _visited(session: IRSession, *, by: str | None) -> None:
    """What a visit writes, leaving the transaction open: the stamp, and nothing else."""
    if session.attended_at is None:
        session.attended_at = datetime.now(UTC)
        session.attended_by = by


async def unattend(
    db: AsyncSession, session: IRSession, *, halts_raised: int, warned_at: datetime | None
) -> IRSession:
    """Withdraw the mark: nobody went. The stamps clear and the status is not written.

    A halted room is back on the queue, and a warning the visit ended stands again: it stands
    while ``warned_at`` is set and nobody is marked as having gone. A demo team's halt is
    stamped again by the server at once, because it never calls a person (ADR 0064); a visit
    to a demo room that never halted clears like any other. Whether a halt stands is read in
    the statement that clears, so a halt raised or lifted after ``session`` was read is the
    one it answers.

    Like the visit, it names the halt the Desk read (ADR 0091): an undo of a visit to an older
    halt would clear a colleague's visit to the newer one.

    ``updated_at`` is left as it was, as the visit left it (ADR 0094). The demo read comes
    before the clear, because a read flushes what is pending and the flush would move it.
    """
    demo = await is_the_demo_team(db, session.project_id)
    stamped_again = literal(datetime.now(UTC), IRSession.attended_at.type)
    cleared = await db.execute(
        update(IRSession)
        .where(
            IRSession.id == session.id,
            _the_halt_named(halts_raised, warned_at),
            IRSession.attended_at.is_not(None),
        )
        .values(
            attended_at=case((halt.stands_once_unattended(), stamped_again), else_=None)
            if demo
            else None,
            attended_by=None,
            updated_at=IRSession.updated_at,
        )
        .execution_options(synchronize_session=False)
    )
    return await _visit_written(
        db, session, written=cleared.rowcount, halts_raised=halts_raised, warned_at=warned_at
    )


def _the_halt_named(halts_raised: int, warned_at: datetime | None) -> ColumnElement[bool]:
    return and_(
        IRSession.halts_raised == halts_raised,
        IRSession.warned_at.is_not_distinct_from(warned_at),
    )


async def _visit_written(
    db: AsyncSession,
    session: IRSession,
    *,
    written: int,
    halts_raised: int,
    warned_at: datetime | None,
) -> IRSession:
    """Close a visit's or an undo's write; one that wrote nothing is refused if the halt moved.

    Nothing written with the halt unchanged is the second tap, or the undo of a visit nobody
    made, and answers the row as it stands.
    """
    if written == 0:
        await db.refresh(session, ["halts_raised", "warned_at"])
        if (session.halts_raised, session.warned_at) != (halts_raised, warned_at):
            raise HaltMoved(session.halts_raised, session.warned_at)
    await db.commit()
    await db.refresh(session)
    return session


def back_translation_of(session: IRSession) -> BackTranslationState:
    return BackTranslationState.model_validate(session.back_translation or {})


_Kept = TypeVar("_Kept")


def _less(items: list[_Kept], taken: list[_Kept]) -> list[_Kept]:
    left = list(items)
    for one in taken:
        if one in left:
            left.remove(one)
    return left


def _standing_forward(read: list[_Kept], wanted: list[_Kept], fresh: list[_Kept]) -> list[_Kept]:
    if fresh == read:
        return wanted
    return [*_less(fresh, _less(read, wanted)), *_less(wanted, read)]


def _rounds_forward(
    read: list[CheckRound], wanted: list[CheckRound], fresh: list[CheckRound]
) -> list[CheckRound]:
    before = {one.at: one for one in read}
    stamped = {one.at: one for one in wanted if one.at in before and one != before[one.at]}
    kept = [
        one.model_copy(update=_changed(before[one.at], stamped[one.at]))
        if one.at in stamped
        else one
        for one in fresh
    ]
    return [*kept, *(one for one in wanted if one.at not in before)]


def _changed(read: CheckRound, wanted: CheckRound) -> dict[str, Any]:
    return {name: value for name, value in vars(wanted).items() if getattr(read, name) != value}


def _played_forward(
    read: list[PlayedTake], wanted: list[PlayedTake], fresh: list[PlayedTake]
) -> list[PlayedTake]:
    return fresh if wanted == read else _added_up(fresh, wanted)


def _added_up(stored: list[PlayedTake], reported: list[PlayedTake]) -> list[PlayedTake]:
    by_take = {entry.take_id: entry for entry in stored}
    for entry in reported:
        earlier = by_take.get(entry.take_id, PlayedTake(take_id=entry.take_id))
        by_take[entry.take_id] = PlayedTake(
            take_id=entry.take_id,
            played_ranges=joined_spans([*earlier.played_ranges, *entry.played_ranges]),
            clip_duration_ms=max(earlier.clip_duration_ms, entry.clip_duration_ms),
        )
    return list(by_take.values())


def _merged_forward(
    read: BackTranslationState, wanted: BackTranslationState, fresh: BackTranslationState
) -> BackTranslationState:
    for name in vars(wanted).keys() - {
        "findings",
        "nuances",
        "checks",
        "played_by_take",
        "pauses_moved",
    }:
        if getattr(wanted, name) != getattr(read, name):
            setattr(fresh, name, getattr(wanted, name))
    fresh.pauses_moved += wanted.pauses_moved - read.pauses_moved
    fresh.played_by_take = _played_forward(
        read.played_by_take, wanted.played_by_take, fresh.played_by_take
    )
    fresh.findings = _standing_forward(read.findings, wanted.findings, fresh.findings)
    fresh.nuances = _standing_forward(read.nuances, wanted.nuances, fresh.nuances)
    fresh.checks = _rounds_forward(read.checks, wanted.checks, fresh.checks)
    return fresh


async def save_back_translation(
    db: AsyncSession,
    session: IRSession,
    state: BackTranslationState,
    *,
    commit: bool = True,
    rule: Callable[[BackTranslationState], Awaitable[None]] | None = None,
) -> IRSession:
    """Write the telling-back state, merged onto what is stored if another write landed first.

    ``rule`` is what the caller decided on the state it read, applied again to the state about to
    be stored: the merged one when another write landed first, the one as written when none did.

    ``commit=False`` leaves the transaction open for a caller composing several writes into one
    — the captured telling, where the stretch row, this state and the mark are one fact.
    """
    base = back_translation_of(session)
    written = state.model_dump(mode="json")

    async def onto(read: dict[str, Any] | None) -> dict[str, Any]:
        if read == session.back_translation:
            if rule is None:
                return written
            as_written = BackTranslationState.model_validate(written)
            await rule(as_written)
            return as_written.model_dump(mode="json")
        merged = _merged_forward(base, state, BackTranslationState.model_validate(read or {}))
        if rule is not None:
            await rule(merged)
        return merged.model_dump(mode="json")

    _, written = await _written_forward(
        db, session.id, IRSession.back_translation, session.back_translation, onto
    )
    set_committed_value(session, "back_translation", written)
    for name, value in vars(BackTranslationState.model_validate(written)).items():
        if getattr(state, name) != value:
            setattr(state, name, value)
    if commit:
        await db.commit()
        await db.refresh(session)
    else:
        await db.flush()
    return session


async def report_playback(
    db: AsyncSession,
    session: IRSession,
    state: BackTranslationState,
    *,
    played_by_take: list[PlayedTake],
    played_ranges: list[tuple[int, int]],
    clip_duration_ms: int | None,
) -> BackTranslationState:
    """Add what the tablet played of each rehearsal part to what is stored, per take.

    **A report with parts adds to what is stored, per take** (ADR 0074). The tablet reports as
    each part ends and on leaving, so a report names the parts it holds and no more; replacing
    on it erased a part an earlier report heard, and one tablet's report erased another's on the
    same session, and it adds up again when another report landed first. A take's spans are kept
    joined only where they touch, so the rule can still see a gap, and its length is the
    longest reported, so a zero never replaces a measurement. That length is stored and
    never read as is: every reader goes through `part_length`, and asks of the current parts
    only, so the entry of a part recorded again stays stored and is never read again.

    **A report with no part named takes nothing away.** An older build sends the flat pair and
    nothing else, and the two builds meet on one session when a team changes tablet mid-passage.
    Overwriting on that press erased a report that had a subject and re-blocked a session that
    was ready — the older build cannot say what it did not measure, and silence about the parts
    is not a claim that none was played. The flat numbers are still stored, as the record of
    that press.

    The flat pair is stored beside it for the record, as the older builds send it, and the
    stamp of which recordings the session was standing on is kept for the reason it was taken:
    a stretch names the recording it is a slice of, checked when it was captured, and that
    answer does not move, while "the newest take" does — `created_at` is stamped when the
    upload lands and the tablet's outbox drains whenever the link comes back, so an abandoned
    rehearsal can be written down after the one that replaced it. Neither is evidence, and
    `unheard_parts` reads neither.
    """
    told = await final_segments(db, session.id)
    if played_by_take:
        state.played_by_take = _added_up(state.played_by_take, played_by_take)
    state.played_ranges = [[start, end] for start, end in played_ranges]
    state.clip_duration_ms = clip_duration_ms
    state.played_take_ids = sorted({segment.take_id for segment in told})
    await save_back_translation(db, session, state)
    return state


async def retire_the_part_recorded_again(
    db: AsyncSession, session: IRSession, take: IRTake
) -> None:
    """A rehearsal take landing under a number an earlier take holds is that part again.

    The verb has no route of its own and no flag: the tablet already sends every part under
    `parte-N` with the number beside it, so a second take under N is the team recording part N
    again and nothing else could be. It sits here rather than in `store_take`, which is a storage
    primitive that knows nothing of parts: the two routes that keep a telling of a stretch store
    through it as well, and a room verb inside it would run on every take the room keeps.

    What it takes: the stretches whose recording is one of the *other* takes of that number,
    divided parents and their pieces alike; the findings that pointed at them, a **Swap** whole;
    and the check, which starts over because the passage the team is standing on has changed.
    Zero is a number the text seam uses, so it counts; a take with none is the rehearsal told
    whole, which is one part of its own, so a second take with none is that part again and
    retires the stretches of the first. The part that now stands is a current part no standing
    stretch is a slice of, and `terminei` refuses the check and names it (ADR 0027) until the
    team tells it back.

    What it leaves: the other parts' stretches, their words and their listening. A part recorded
    again is unheard by construction — a new take is a recording nobody has played — so the
    gate reopens for it without anything being cleared here. `analysed_segment_ids` is left
    where it is: the reading it names no longer matches the stretches that stand, so the next
    `terminei` asks the analyst again, which is the answer this wants.

    **Only the take that is the part now.** The tablet re-sends bytes without asking whether
    they landed and its outbox drains whenever the link comes back, so what arrives here can be
    a recording the team replaced long ago — `store_take` answers it with the row that already
    exists, which is indistinguishable from a fresh one. Read as a re-recording it would abandon
    the part standing now and take the check with it, which is the team losing the work they had
    just done to a request carrying nothing new. Which take is the part is `current_parts`, the
    same answer the **Packet** is built on, and it is asked here before anything is retired.

    **A part whose stretches did not move leaves the check alone.** Re-sending the bytes of the
    part that *is* standing reaches here and finds the earlier takes already retired; so does a
    part recorded twice before anybody told it back. Neither changed the reading, so neither
    un-checks it.

    The rows and the state commit together. Apart, a failure between them leaves the room
    carrying findings about audio nobody will hear again, which is the state this exists to
    make unreachable.
    """
    if take.kind is not IRTakeKind.ENSAIO:
        return

    takes = await takes_of(db, session.id)
    if take.id not in {part.id for part in current_parts(takes)}:
        return

    earlier = {
        other.id
        for other in takes
        if other.kind is IRTakeKind.ENSAIO and other.ordinal == take.ordinal and other.id != take.id
    }
    retired = await retire_the_segments_of(db, session.id, take_ids=earlier)
    if not retired:
        return

    retired_ids = {row.id for row in retired}

    async def recorded_again(standing: BackTranslationState) -> None:
        standing.findings = findings_after_a_part_is_recorded_again(standing.findings, retired_ids)
        standing.nuances = [one for one in standing.nuances if one.segment_id not in retired_ids]
        standing.checked = False
        standing.verdict = None

    state = back_translation_of(session)
    await recorded_again(state)
    await save_back_translation(db, session, state, commit=False, rule=recorded_again)
    await db.commit()
    await db.refresh(session)


async def start_the_translation_over(db: AsyncSession, session: IRSession) -> None:
    async def started_over(standing: BackTranslationState) -> None:
        archived = standing.superseded[-1]
        archived.findings = [
            *archived.findings,
            *(one for one in standing.findings if one not in archived.findings),
        ]
        rounds = {one.at: one for one in archived.checks} | {one.at: one for one in standing.checks}
        archived.checks = list(rounds.values())
        standing.findings = []
        standing.nuances = []
        standing.checks = []
        standing.checked = False
        standing.checked_at = None
        standing.verdict = None
        standing.analysed_segment_ids = None

    state = back_translation_of(session)
    state.superseded = [*state.superseded, SupersededAttempt()]
    await started_over(state)
    await retire_every_segment(db, session.id)
    await save_back_translation(db, session, state, rule=started_over)
