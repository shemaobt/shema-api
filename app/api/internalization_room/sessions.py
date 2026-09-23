import asyncio
import logging
import re
import uuid
from collections import OrderedDict
from functools import partial

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.api.internalization_room._deps import (
    device_project_dep,
    require_room_caller,
    room_caller_dep,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.core.room_enums import HaltKind
from app.core.stage_clock import count, stage, stopwatch
from app.db.models.device import Device
from app.db.models.internalization_room import IRPromptKey, IRSession, IRSessionStatus
from app.models.internalization_room import (
    BackTranslationProgress,
    CreateSessionRequest,
    FacilitatorHaltedDeviceView,
    FacilitatorSessionsResponse,
    FacilitatorSessionView,
    HardStretchView,
    NeedsPersonResponse,
    PersonArrivedResponse,
    SegmentView,
    SessionStateResponse,
    SpokenSegment,
    TurnResponse,
)
from app.services import internalization_room as room
from app.services.device.needs_person import clear_needs_person, devices_waiting_on_a_person
from app.services.internalization_room import halt
from app.services.internalization_room.background import settle_coverage
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.coverage import coverage_view
from app.services.internalization_room.hearing import HeardSpeech, heard_speech
from app.services.internalization_room.languages import LANGUAGE_NAMES
from app.services.internalization_room.live_turn import current_scene_id
from app.services.internalization_room.panorama_once import heard_panorama
from app.services.internalization_room.prepare_opening import (
    hand_over,
    prepare_opening,
    take_prepared,
)
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.run_turn import TurnOutcome, detects_peer_cue
from app.services.internalization_room.sessions import book_of, is_panorama
from app.services.internalization_room.turn_dedup import (
    answer_once,
    answered_turn,
    remember_turn,
)
from app.services.internalization_room.voice_handles import clip_url
from app.services.platform.tts import SpeechKey, Upload
from app.services.project.facilitated_scope import facilitated_project_ids
from app.services.project.team_names import team_names
from app.utils.stored_time import as_utc

logger = logging.getLogger(__name__)

router = APIRouter()

_SEGMENT_ROLES = ("panorama", "scene")


async def _clip_or_none(text: str, *, language: str, uploads: list[Upload]) -> str | None:
    try:
        entry, _ = await room.synthesize_facilitator_speech(
            text, language=language, uploads=uploads
        )
    except Exception:
        logger.warning("A movement of the opening could not be voiced; sending it whole")
        return None
    return entry.key


async def _voice_the_turn(
    outcome: room.TurnOutcome,
    *,
    language: str,
    uploads: list[Upload],
) -> tuple[SpeechKey | None, list[SpokenSegment]]:
    """The turn's audio: the whole line, and the opening's movements beside it.

    All of it at once — three short syntheses in parallel cost the wall clock of the
    slowest, where three in a row cost the sum and the room has ninety seconds before the
    app decides the network is gone. A movement that will not synthesize is dropped rather
    than raised: the whole line already succeeded, and one clip is the room's own fallback.
    """
    if outcome.fixed_line:
        return None, []

    async def whole_line() -> SpeechKey:
        entry, _ = await room.synthesize_facilitator_speech(
            outcome.speech, language=language, uploads=uploads
        )
        return entry

    async def movements() -> list[str | None]:
        return list(
            await asyncio.gather(
                *(
                    _clip_or_none(part, language=language, uploads=uploads)
                    for part in outcome.movements
                )
            )
        )

    voicing = asyncio.create_task(movements())
    try:
        whole = await whole_line()
    finally:
        parts = await voicing
    keys = [key for key in parts if key is not None]
    if len(keys) != len(_SEGMENT_ROLES):
        return whole, []
    return whole, [
        SpokenSegment(role=role, audio_url=clip_url(key))
        for role, key in zip(_SEGMENT_ROLES, keys, strict=True)
    ]


async def _write_the_turn(
    db: AsyncSession,
    session: IRSession,
    *,
    outcome: room.TurnOutcome,
    turn: room.ComprehensionTurn | None,
    opening: bool,
) -> IRSession:
    with stage("db_write"):
        if opening:
            await room.append_opening(
                db,
                session,
                guide_response=outcome.speech,
                outcome=outcome,
                scene=_scene_of(session),
                state=turn.state if turn is not None else None,
                commit=False,
            )
            return session
        return await room.append_exchange(
            db,
            session,
            team_utterance=outcome.transcript,
            guide_response=outcome.speech,
            outcome=outcome,
            scene=_scene_of(session, outcome.transcript),
            state=turn.state if turn is not None else None,
            commit=False,
        )


async def _upload(uploads: list[Upload]) -> None:
    with stage("upload"):
        await asyncio.gather(*(upload() for upload in uploads))


MAX_AUDIO_BYTES = 25 * 1024 * 1024

#: A session's language, once this process has read it. Neon sits in us-east-1 and every
#: session row carries a growing `messages`/`coverage_state` JSON blob, so the read that would
#: tell a turn its own language is the one costing 20-30 ms round trips each way; a later turn
#: for the same session can start transcription without waiting on it. Capped like
#: `platform/tts.py`'s `_FRESH`/`_KEPT`, so a long-lived worker serving many sessions does not
#: grow this without bound.
_LANGUAGE_MEMO_MAX = 1024
_LANGUAGE_MEMO: OrderedDict[str, tuple[str, str | None]] = OrderedDict()


def forget_session_languages() -> None:
    """Empty the memo, the way `tts.forget_what_is_kept` empties the clip caches between tests."""
    _LANGUAGE_MEMO.clear()


def _remember_language(session_id: str, language: str, project_id: str | None) -> None:
    _LANGUAGE_MEMO[session_id] = (language, project_id)
    _LANGUAGE_MEMO.move_to_end(session_id)
    while len(_LANGUAGE_MEMO) > _LANGUAGE_MEMO_MAX:
        _LANGUAGE_MEMO.popitem(last=False)


async def _read_capped_audio(file: UploadFile) -> bytes:
    audio_bytes = await file.read()
    count("upload_bytes", len(audio_bytes))
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")
    return audio_bytes


async def _timed_stt(
    audio_bytes: bytes, *, filename: str | None, mime_type: str | None, language: str
) -> HeardSpeech:
    with stage("stt"):
        return await heard_speech(
            audio_bytes, filename=filename, mime_type=mime_type, language=language
        )


async def _cancelled(task: asyncio.Task[HeardSpeech]) -> None:
    """Stop a transcription started ahead of the session read and read its outcome.

    A session the read could not find has nobody left to hear the transcript, so its task
    is stopped rather than left to run to an answer nobody reads. `asyncio.wait` rather than
    a plain `await`: this runs while unwinding from `get_session`'s own failure, and a plain
    `await task` inside `except BaseException: pass` would also swallow a cancellation aimed
    at this request itself, arriving at exactly this suspension point — `wait` never raises
    the waited task's own exception into its caller, so only that task's outcome is being
    read here, never the caller's. `task.exception()` marks a real failure as read without
    raising it; skipped when the task ended up cancelled, since reading it then would raise.
    """
    task.cancel()
    await asyncio.wait({task})
    if not task.cancelled():
        task.exception()


_CLIENT_TIMING = re.compile(r"[a-z_]{1,32}=[0-9]+(?:;[a-z_]{1,32}=[0-9]+)*")
_CLIENT_TIMING_LONGEST = 512


def _log_client_timing(session_id: str, client_timing: str) -> None:
    if len(client_timing) <= _CLIENT_TIMING_LONGEST and _CLIENT_TIMING.fullmatch(client_timing):
        logger.info("[client-timing] session=%s %s", session_id, client_timing)
    else:
        logger.warning("[client-timing] rejected session=%s", session_id)


def _scene_of(session: IRSession, team_utterance: str = "") -> str | None:
    """The scene the turn was read against, for the record; a panorama has none.

    The record is written before the exchange is appended, so the utterance being
    recorded is not in the stored history yet — it is handed in on its own. Without it
    the first turn of every session would be recorded with no scene, as if the team had
    not spoken, when the record is precisely about what they just said.
    """
    if is_panorama(session.pericope):
        return None
    history = list(session.messages or [])
    if team_utterance:
        history.append({"role": "team", "text": team_utterance})
    return current_scene_id(session.coverage_state or {}, session.pericope, history)


def _worth_settling(outcome: TurnOutcome, speech_heard: HeardSpeech) -> bool:
    """Whether the turn carries anything the coverage classifier should be reading.

    A fail-safe says the Guide could not phrase a reply, which is no evidence that the team
    said nothing, so what the team said decides rather than the state the room's own turn
    ended in. What the team said still has to be speech the room took up, which is what
    `reliable_bridge_speech` means: an uncertain transcript travels forward inside the very
    fail-safe asking the team to repeat it, and mother-tongue speech inside the one asking
    for the session's language back. Neither is an answer the room engaged with, and coverage
    only moves forward and feeds the Guide's next prompt, so neither bead comes back down.

    The opening used to earn an exception here by being an opening the Guide actually wrote,
    reaching `surfaced` on beads the team had not spoken a word toward. Coverage is
    `engaged`-only on the team's screen: a sentence the room wrote for itself, however many
    map elements it names, is not evidence of anything the team heard, so no turn with an
    empty transcript is worth settling any more, opening or not.
    """
    if outcome.transcript.strip():
        return speech_heard.reliable_bridge_speech
    return False


def _settle_later(
    background: BackgroundTasks,
    session: IRSession,
    *,
    turn_id: str,
    team_utterance: str,
    guide_response: str,
) -> bool:
    """Schedule the coverage classifier for a turn `_worth_settling` already cleared.

    Two doors used to reach here — the opening the panorama wrote ahead, and the line the
    room writes on demand. `3cfd823` (ENG-684) made the prepared door call unconditionally,
    so a pre-warmed opening's roughly ten map elements would not go unclassified, while the
    live door kept its guard and `_worth_settling` excused the opening from it. Coverage is
    `engaged`-only on the team's screen now: a line the room wrote for itself is not
    evidence of anything the team heard, whichever door it left by, so the prepared door no
    longer calls here at all, and this is reached only from the door `_worth_settling` guards.

    A panorama is still handed nothing: it has no coverage spine to settle against.
    """
    if is_panorama(session.pericope):
        return False
    background.add_task(
        settle_coverage,
        session_id=session.id,
        turn_id=turn_id,
        team_utterance=team_utterance,
        guide_response=guide_response,
        pericope_num=session.pericope,
    )
    return True


async def _state(db: AsyncSession, session: IRSession) -> SessionStateResponse:
    return SessionStateResponse(
        session_id=session.id,
        pericope=session.pericope,
        status=str(session.status),
        coverage=coverage_view(session),
        done=session.status is IRSessionStatus.DONE,
        back_translation=await _progress(db, session),
        language=session.language,
        halt=halt.standing(session),
    )


async def _progress(db: AsyncSession, session: IRSession) -> BackTranslationProgress:
    """What a tablet needs to pick a telling-back back up where it stopped.

    All of it was already on the session and none of it had a way out, so an app that
    forgot its session id — which is every restart, because the id lives only in memory —
    lost the retro entirely and had to record the rehearsal again.

    The stretches come from `final_segments` and nothing here repeats its rule: what a tablet
    resumes is the same reading the analyst gets.
    """
    state = room.back_translation_of(session)
    finding = room.the_finding_that_leads(state)
    return BackTranslationProgress(
        scope=state.scope,
        segments=[
            SegmentView(
                segment_id=segment.id,
                take_id=segment.take_id,
                starts_ms=segment.starts_ms,
                ends_ms=segment.ends_ms,
                pass_number=segment.pass_number,
                told=segment.transcript is not None,
            )
            for segment in await room.final_segments(db, session.id)
        ],
        checked=state.checked,
        finding_segment_id=finding.segment_id if finding else None,
        finding_kind=finding.kind.value if finding else None,
        superseded_attempts=len(state.superseded),
    )


@router.post("/sessions", response_model=SessionStateResponse, dependencies=[room_caller_dep])
async def create_session(
    payload: CreateSessionRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    project_id: str | None = device_project_dep,
    caller: Device | None = Depends(require_room_caller),
) -> SessionStateResponse:
    """Open a session, and end this tablet's halt if it was standing in one.

    The lift is here rather than in `create_session` because it is about the *caller* and
    not about the session: a room going again is evidence only for the tablet that went,
    and a lift keyed on the team would clear a halt because somebody else in the room
    started something. `caller` is the gate's own result — the credential is resolved once
    per request and FastAPI's dependency cache is what makes this and `device_project_dep`
    one query — so a caller on the shared room key names no device and lifts nothing.

    After the session exists, so a `create_session` that refuses leaves the halt standing:
    a room that could not open a session is still stopped.

    The opening is written ahead only for a panorama the team has not yet gone on from:
    that is the team about to enter the book, and the line is the passage's first. A team
    already inside the book that chose to hear the panorama again is there for the book's
    shape, not for the door into a passage, so nothing is written for it. What that costs
    is stated rather than waved away: `hand_over` would move the line to a bead opened after
    the second panorama too, and a team that does leave it into a passage hears an opening
    written live, with the wait the prepared one spares. A model call and a clip on every
    second hearing, most of which end on the wheel, is the dearer side of that trade.
    """
    session = await room.create_session(
        db,
        pericope=payload.pericope,
        after_panorama=payload.after_panorama or payload.after_session is not None,
        project_id=project_id,
        language=payload.language,
        chosen=payload.chosen,
    )
    if caller is not None:
        await clear_needs_person(db, caller.id)
    if payload.after_session:
        previous = await room.get_session(db, payload.after_session)
        if hand_over(previous, session):
            await db.commit()
    elif is_panorama(session.pericope) and not await heard_panorama(
        db, project_id=project_id, book=book_of(session.pericope)
    ):
        background.add_task(prepare_opening, session.id)
    return await _state(db, session)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionStateResponse,
    dependencies=[room_caller_dep],
)
async def read_session(session_id: str, db: AsyncSession = Depends(get_db)) -> SessionStateResponse:
    session = await room.get_session(db, session_id)
    return await _state(db, session)


@router.get("/facilitator/sessions", response_model=FacilitatorSessionsResponse)
async def facilitator_sessions(
    user: FacilitatorUser, db: AsyncSession = Depends(get_db)
) -> FacilitatorSessionsResponse:
    """The sessions waiting on a person, for the person they are waiting on.

    Halting had a writer and no reader: `needs_person` was written to the row and the only
    facilitator-facing list in the system was the open questions, which named no session.
    The two session-scoped facilitator routes are addressed by an id nobody could obtain,
    so a room that stopped for someone could not reach anyone.

    **Scoped to the caller's own teams**, and the reason the route first gave for needing
    no scope is worth correcting rather than deleting: it argued that this only makes
    discoverable what was already readable, since an id was never what kept the
    session-addressed routes shut. That was true where it was written. It is not true here
    — `…/{id}/takes` refuses a session of another team through
    `get_session_for_facilitator`, and `…/{id}/release` has refused one since ENG-563's
    composition. An unscoped list would announce the existence, the passage and the moment
    of other teams' sessions, and hand over ids their reader is refused.

    Gated on `FacilitatorUser` for the same reason every other route under `/facilitator`
    is: the app-wide gate it was written against no longer exists.

    **`devices` is the half a session id cannot reach** (ENG-624). A tablet whose session
    the server has forgotten, or whose build broke before one was opened, halts on itself
    rather than on a session, and that halt would otherwise be readable only from the team's
    devices panel — a screen a facilitator opens about one team they already suspect. This
    is the list they read to find out which team to go to. Scoped by the same rule as the
    sessions half — `facilitated_project_ids`, the ids in hand rather than `IN (SELECT …)`
    the planner cannot use.

    **Resolved twice, once per half, and that is the shape rather than an oversight.**
    `sessions_waiting_on_a_person` resolves its own scope inside its query and nothing
    memoises the answer, so this route makes the lookup a second time. Threading one answer
    through would mean widening that service's signature, which this slice does not touch;
    what it would save is one index lookup on `project_user_access`, a table with one row
    per team a person facilitates. Worth stating so the next reader does not take the two
    calls for a duplicate somebody missed.

    The moment is bound before it is read because the column is nullable and this list is
    the rows where it is not: the binding is the type system reading what the query already
    guarantees, not a filter with anything to drop. The team id on the sessions half is bound
    the same way and for the same reason — `confined_to` excludes a null project under either
    of its two shapes, so the `if` there drops nothing either.

    **`team_name` costs one more statement, and it is the field that makes the queue
    usable** (ENG-609). This is the one facilitator listing that crosses teams: every other
    one is about a team the caller named and can name back. A row carrying only an id does
    not answer the question this screen is opened to ask, which is which team to walk to.
    One statement for the page rather than a lookup per row.

    **`halt` and the stamps are additive** (ENG-609): which kind of halt is standing, and
    whether somebody has already been. A facilitator reading a queue with neither cannot tell
    a stopped room from one asking for a witness, nor one nobody has reached from one a
    colleague walked to five minutes ago.
    """
    scope = await facilitated_project_ids(db, user)
    waiting = await room.sessions_waiting_on_a_person(db, user)
    named = await team_names(db, (s.project_id for s in waiting if s.project_id is not None))
    marks = await room.hard_stretches_of(db, [session.id for session in waiting])
    return FacilitatorSessionsResponse(
        sessions=[
            FacilitatorSessionView(
                session_id=session.id,
                pericope=session.pericope,
                status=session.status.value,
                updated_at=session.updated_at.isoformat() if session.updated_at else "",
                project_id=team,
                team_name=named.get(team, ""),
                halt=halt.standing(session),
                attended_at=(
                    as_utc(session.attended_at).isoformat()
                    if session.attended_at is not None
                    else None
                ),
                attended_by=session.attended_by,
                person_arrived_at=(
                    as_utc(session.person_arrived_at).isoformat()
                    if session.person_arrived_at is not None
                    else None
                ),
                hard_stretches=[
                    HardStretchView(
                        segment_id=mark.segment_id,
                        tellings=mark.tellings,
                        crossed_at=as_utc(mark.crossed_at).isoformat(),
                    )
                    for mark in marks.get(session.id, [])
                ],
            )
            for session in waiting
            if (team := session.project_id) is not None
        ],
        devices=[
            FacilitatorHaltedDeviceView(
                device_id=device.id,
                label=device.label,
                since=as_utc(halted),
                attended_at=as_utc(device.attended_at) if device.attended_at else None,
                attended_by=device.attended_by,
            )
            for device in await devices_waiting_on_a_person(db, scope)
            if (halted := device.needs_person_since) is not None
        ],
    )


@router.post(
    "/sessions/{session_id}/needs-person",
    response_model=NeedsPersonResponse,
    dependencies=[room_caller_dep],
)
async def ask_for_a_person(
    session_id: str, db: AsyncSession = Depends(get_db)
) -> NeedsPersonResponse:
    """The room in front of the team decided it cannot go on without a person.

    `needs_person` had a consumer in the app and no producer here, so a room that had
    already halted still reported `in_progress` and no facilitator could be told.
    """
    session = await room.get_session(db, session_id)
    await room.mark_needs_person(db, session, kind=HaltKind.BLOCKING)
    return NeedsPersonResponse(
        session_id=session.id,
        needs_person=session.status is IRSessionStatus.NEEDS_PERSON,
    )


@router.post(
    "/sessions/{session_id}/person-arrived",
    response_model=PersonArrivedResponse,
    dependencies=[room_caller_dep],
)
async def a_person_arrived(
    session_id: str, db: AsyncSession = Depends(get_db)
) -> PersonArrivedResponse:
    """Somebody long-pressed the halted room to say they are standing in it (ENG-792).

    The halt says a person is needed; nothing said one had come. A facilitator reading the
    queue could not tell a room still waiting from one a colleague is already standing in, so
    two people walk to the same room while a third waits.

    Answered with the moment of the *first* press against this halt, so a team pressing again
    because nothing visibly happened is told the same thing every time. `person_arrived` is
    where that and the clearing on a new halt are argued.
    """
    session = await room.get_session(db, session_id)
    arrived = await room.person_arrived(db, session)
    return PersonArrivedResponse(
        session_id=session.id, person_arrived_at=as_utc(arrived).isoformat()
    )


async def _say_it_again(session: IRSession, *, turn_id: str | None) -> TurnResponse:
    """Where the room already was, for a team walking back in.

    No model, no new line, nothing appended: the last thing the Guide said, said again.
    The synthesiser is content-addressed, so the very same words come straight back out of
    the bucket — this costs one lookup and no waiting.
    """
    last = next(
        (
            message.get("text", "")
            for message in reversed(session.messages or [])
            if message.get("role") == "guide"
        ),
        "",
    )
    voiced = (
        (await room.synthesize_facilitator_speech(last, language=session.language))[0]
        if last
        else None
    )
    return TurnResponse(
        session_id=session.id,
        audio_url=clip_url(voiced.key) if voiced else "",
        transcript="",
        peer_cue=detects_peer_cue(last),
        coverage=coverage_view(session),
        done=(False if is_panorama(session.pericope) else room.session_is_done(session)),
        turn_id=turn_id or "",
    )


@router.post(
    "/sessions/{session_id}/turns",
    response_model=TurnResponse,
    dependencies=[room_caller_dep],
)
async def take_turn(
    session_id: str,
    background: BackgroundTasks,
    response: Response,
    file: UploadFile | None = File(default=None),
    turn_id: str | None = Form(default=None, max_length=64),
    client_timing: str | None = Form(default=None),
    project_id: str | None = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> TurnResponse:
    """One turn of the room: what the team just said goes in, the Guide's next line comes out.

    An opening is the session's first line, not merely a POST without audio. The app sends an
    audio-less turn again whenever a team walks back into a passage it left, and reading that
    as an opening had the Guide introduce itself and lay the whole passage out a second time —
    against a probe already waiting for a free retell, which the Validator then rejected, so
    the room answered a returning team with a canned line.

    The turn is voiced before any of it is written down. A probe is the room's authorization
    to assess the answer that comes next, so committing one for a turn whose synthesis then
    failed points that authorization at a question the team was never asked, and leaves the
    ledger holding evidence for an exchange that was never recorded. Speaking first costs
    nothing in the other direction: a clip reaches the team only as the handle in this
    response, so a request that fails after synthesis hands the app nothing to play.

    A turn never halts the session. The graceful pause is a spoken line like any other
    fail-safe, and the call for a person is the tablet's, on its own triggers.
    """
    if client_timing is not None:
        _log_client_timing(session_id, client_timing)
    answer = partial(
        _answer_the_turn,
        session_id=session_id,
        background=background,
        file=file,
        turn_id=turn_id,
        project_id=project_id,
    )
    with stopwatch("[turn-timing]", session_id) as clock:
        if turn_id:
            reply = await answer_once(session_id, turn_id, answer)
        else:
            reply = await answer(db)
    response.headers["Server-Timing"] = clock.server_timing()
    return reply


async def _answer_the_turn(
    db: AsyncSession,
    *,
    session_id: str,
    background: BackgroundTasks,
    file: UploadFile | None,
    turn_id: str | None,
    project_id: str | None,
) -> TurnResponse:
    bound_s = get_settings().internalization_room_turn_bound_ms / 1000
    deadline = asyncio.get_running_loop().time() + bound_s

    if turn_id:
        with stage("db_read"):
            replay = await answered_turn(db, session_id, turn_id, project_id)
        if replay is not None:
            return TurnResponse(**replay)

    stt: asyncio.Task[HeardSpeech] | None = None
    if file is not None:
        known = _LANGUAGE_MEMO.get(session_id)
        if known is not None and known[1] == project_id:
            audio_bytes = await _read_capped_audio(file)
            stt = asyncio.create_task(
                _timed_stt(
                    audio_bytes,
                    filename=file.filename,
                    mime_type=file.content_type,
                    language=known[0],
                )
            )

    try:
        with stage("db_read"):
            session = (
                await room.get_session_for_room_caller(db, session_id, project_id)
                if project_id is not None
                else await room.get_session(db, session_id)
            )
    except BaseException:
        if stt is not None:
            await _cancelled(stt)
        raise
    _remember_language(session_id, session.language, project_id)

    speech_heard = HeardSpeech()
    opening = file is None and not (session.messages or [])
    if stt is not None:
        speech_heard = await stt
    elif file is not None:
        audio_bytes = await _read_capped_audio(file)
        speech_heard = await _timed_stt(
            audio_bytes,
            filename=file.filename,
            mime_type=file.content_type,
            language=session.language,
        )
    transcript = speech_heard.text

    if file is None and not opening:
        return await _say_it_again(session, turn_id=turn_id)

    ready = await take_prepared(db, session) if opening else None
    if ready is not None:
        speech, audio_key = ready
        outcome = TurnOutcome(speech=speech, transcript="", peer_cue=detects_peer_cue(speech))
        session = await room.append_exchange(db, session, team_utterance="", guide_response=speech)
        reply = TurnResponse(
            session_id=session.id,
            audio_url=clip_url(audio_key),
            transcript="",
            peer_cue=outcome.peer_cue,
            coverage=coverage_view(session),
            done=False,
            turn_id=turn_id or str(uuid.uuid4()),
        )
        if turn_id:
            await remember_turn(
                db, session_id=session.id, turn_id=turn_id, response=reply.model_dump(mode="json")
            )
            await db.commit()
        return reply

    validator_prompt = get_prompt_text(IRPromptKey.VALIDATOR)
    turn: room.ComprehensionTurn | None = None
    try:
        async with asyncio.timeout_at(deadline):
            if is_panorama(session.pericope):
                book = book_of(session.pericope)
                outcome = await room.run_panorama_turn(
                    transcript=transcript,
                    messages=session.messages or [],
                    session_language=LANGUAGE_NAMES[session.language],
                    language_code=session.language,
                    panorama_prompt=get_prompt_text(IRPromptKey.BOOK_PANORAMA),
                    validator_prompt=validator_prompt,
                    book=book,
                    book_material=build_book_material(book),
                    opening=opening,
                    settings=get_settings(),
                    session_id=session.id,
                )
            else:
                turn = await room.run_comprehension_turn(
                    db,
                    session,
                    speech=speech_heard,
                    opening=opening,
                    guide_prompt=get_prompt_text(IRPromptKey.GUIDE),
                    validator_prompt=validator_prompt,
                    settings=get_settings(),
                )
                outcome = turn.outcome
    except TimeoutError as spent:
        raise UpstreamServiceError(f"o turno não respondeu em {bound_s:g} s") from spent

    uploads: list[Upload] = []
    try:
        with stage("voice"):
            voiced, segments = await _voice_the_turn(
                outcome, language=session.language, uploads=uploads
            )
    except BaseException:
        if uploads:
            await _upload(uploads)
        raise
    session, _ = await asyncio.gather(
        _write_the_turn(db, session, outcome=outcome, turn=turn, opening=opening),
        _upload(uploads),
    )

    response_turn_id = turn_id or str(uuid.uuid4())
    pending = False
    if _worth_settling(outcome, speech_heard):
        pending = _settle_later(
            background,
            session,
            turn_id=response_turn_id,
            team_utterance=outcome.transcript,
            guide_response=outcome.speech,
        )

    reply = TurnResponse(
        session_id=session.id,
        audio_url=clip_url(voiced.key) if voiced else "",
        fixed_line=outcome.fixed_line,
        transcript=outcome.transcript,
        peer_cue=outcome.peer_cue,
        used_fail_safe=outcome.used_fail_safe,
        degraded=outcome.degraded,
        coverage=coverage_view(session),
        done=(False if is_panorama(session.pericope) else room.session_is_done(session)),
        segments=segments,
        turn_id=response_turn_id,
        classification_pending=pending,
    )
    with stage("db_write"):
        if turn_id:
            await remember_turn(
                db, session_id=session.id, turn_id=turn_id, response=reply.model_dump(mode="json")
            )
        await db.commit()
    return reply
