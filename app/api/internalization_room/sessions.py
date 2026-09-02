import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.api.internalization_room._deps import device_project_dep, room_caller_dep
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRPromptKey, IRSession, IRSessionStatus
from app.models.internalization_room import (
    BackTranslationProgress,
    CoverageView,
    CreateSessionRequest,
    FacilitatorSessionsResponse,
    FacilitatorSessionView,
    NeedsPersonResponse,
    SegmentView,
    SessionStateResponse,
    SpokenSegment,
    TurnResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.background import settle_coverage
from app.services.internalization_room.calibration import (
    BridgeMode,
    bridge_calibration_acknowledgement,
    bridge_calibration_question,
    resolve_bridge_mode_for_turn,
    resolve_one_shot_calibration,
)
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.canon.elements import absence_index
from app.services.internalization_room.coverage import counts
from app.services.internalization_room.hearing import HeardSpeech, heard_speech
from app.services.internalization_room.languages import LANGUAGE_NAMES
from app.services.internalization_room.prepare_opening import (
    hand_over,
    prepare_opening,
    take_prepared,
)
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.run_turn import TurnOutcome, detects_peer_cue
from app.services.internalization_room.sessions import book_of, is_panorama
from app.services.internalization_room.voice_handles import clip_url
from app.services.platform.tts import SynthesizedSpeech

logger = logging.getLogger(__name__)

router = APIRouter()

_SEGMENT_ROLES = ("panorama", "scene")


async def _clip_or_none(text: str, *, language: str) -> str | None:
    try:
        entry, _ = await room.synthesize_facilitator_speech(text, language=language)
    except Exception:
        logger.warning("A movement of the opening could not be voiced; sending it whole")
        return None
    return entry.key


async def _voice_the_turn(
    outcome: room.TurnOutcome,
    *,
    language: str,
) -> tuple[SynthesizedSpeech | None, list[SpokenSegment]]:
    """The turn's audio: the whole line, and the opening's movements beside it.

    All of it at once — three short syntheses in parallel cost the wall clock of the
    slowest, where three in a row cost the sum and the room has ninety seconds before the
    app decides the network is gone. A movement that will not synthesize is dropped rather
    than raised: the whole line already succeeded, and one clip is the room's own fallback.
    """
    if outcome.fixed_line:
        return None, []

    async def whole_line() -> SynthesizedSpeech:
        entry, _ = await room.synthesize_facilitator_speech(outcome.speech, language=language)
        return entry

    async def movements() -> list[str | None]:
        return list(
            await asyncio.gather(
                *(_clip_or_none(part, language=language) for part in outcome.movements)
            )
        )

    whole, parts = await asyncio.gather(whole_line(), movements())
    keys = [key for key in parts if key is not None]
    if len(keys) != len(_SEGMENT_ROLES):
        return whole, []
    return whole, [
        SpokenSegment(role=role, audio_url=clip_url(key))
        for role, key in zip(_SEGMENT_ROLES, keys, strict=True)
    ]


MAX_AUDIO_BYTES = 25 * 1024 * 1024


def _coverage_view(session: IRSession) -> CoverageView:
    numbers = counts(session.coverage_state or {})
    return CoverageView(
        engaged=numbers["engaged"],
        surfaced=numbers["surfaced"],
        total=numbers["total"],
        absence_index=-1 if is_panorama(session.pericope) else absence_index(session.pericope),
    )


def _worth_settling(outcome: TurnOutcome, speech_heard: HeardSpeech, *, opening: bool) -> bool:
    """Whether the turn carries anything the coverage classifier should be reading.

    A fail-safe says the Guide could not phrase a reply, which is no evidence that the team
    said nothing, so what the team said decides rather than the state the room's own turn
    ended in. What the team said still has to be speech the room took up, which is what
    `reliable_bridge_speech` means: an uncertain transcript travels forward inside the very
    fail-safe asking the team to repeat it, and mother-tongue speech inside the one asking
    for the session's language back. Neither is an answer the room engaged with, and coverage
    only moves forward and feeds the Guide's next prompt, so neither bead comes back down.

    The opening is the one turn with beads to name and no utterance behind it, and it earns
    that exception by being an opening the Guide actually wrote. It reaches `surfaced`, which
    stays below `floor_met`, so settling it neither closes a passage nor stands in for the
    team retelling it — while a fail-safe opening is the same contentless fixed line as any
    other, the one `prepare_opening` throws away rather than keep.
    """
    if outcome.transcript.strip():
        return speech_heard.reliable_bridge_speech
    return opening and not outcome.used_fail_safe


def _settle_later(
    background: BackgroundTasks,
    session: IRSession,
    *,
    team_utterance: str,
    guide_response: str,
) -> None:
    """Hand the exchange to the off-path classifier, from whichever exit voiced it.

    A turn leaves this router by two doors — the opening the panorama wrote ahead, and the
    line the room writes on demand — and only the second one ever asked. A prepared opening
    names around ten map elements (ENG-684), so a team whose opening had been pre-warmed lost
    all of them before saying a word, and nothing said so.

    A panorama is still handed nothing: it has no coverage spine to settle against.
    """
    if is_panorama(session.pericope):
        return
    background.add_task(
        settle_coverage,
        session_id=session.id,
        team_utterance=team_utterance,
        guide_response=guide_response,
        pericope_num=session.pericope,
    )


async def _state(db: AsyncSession, session: IRSession) -> SessionStateResponse:
    return SessionStateResponse(
        session_id=session.id,
        pericope=session.pericope,
        status=str(session.status),
        coverage=_coverage_view(session),
        done=session.status is IRSessionStatus.DONE,
        back_translation=await _progress(db, session),
        bridge_mode=session.bridge_mode,
        language=session.language,
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
    finding = state.current_finding
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
        retells=state.retells,
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
) -> SessionStateResponse:
    session = await room.create_session(
        db,
        pericope=payload.pericope,
        after_panorama=payload.after_panorama or payload.after_session is not None,
        project_id=project_id,
        bridge_mode=payload.bridge_mode,
        language=payload.language,
    )
    if payload.after_session:
        previous = await room.get_session(db, payload.after_session)
        if hand_over(previous, session):
            await db.commit()
    elif is_panorama(session.pericope):
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
    """
    return FacilitatorSessionsResponse(
        sessions=[
            FacilitatorSessionView(
                session_id=session.id,
                pericope=session.pericope,
                status=session.status.value,
                updated_at=session.updated_at.isoformat() if session.updated_at else "",
            )
            for session in await room.sessions_waiting_on_a_person(db, user)
        ]
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
    await room.mark_needs_person(db, session)
    return NeedsPersonResponse(
        session_id=session.id,
        needs_person=session.status is IRSessionStatus.NEEDS_PERSON,
    )


async def _say_it_again(session: IRSession) -> TurnResponse:
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
        coverage=_coverage_view(session),
        done=(False if is_panorama(session.pericope) else room.session_is_done(session)),
        bridge_mode=session.bridge_mode,
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
    """
    session = await room.get_session(db, session_id)

    speech_heard = HeardSpeech()
    opening = file is None and not (session.messages or [])
    if file is not None:
        audio_bytes = await file.read()
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise ValidationError("Audio payload exceeds 25 MB limit")
        speech_heard = await heard_speech(
            audio_bytes,
            filename=file.filename,
            mime_type=file.content_type,
            language=session.language,
        )
    transcript = speech_heard.text

    if file is None and not opening:
        return await _say_it_again(session)

    ready = await take_prepared(db, session) if opening else None
    if ready is not None:
        speech, audio_key = ready
        outcome = TurnOutcome(speech=speech, transcript="", peer_cue=detects_peer_cue(speech))
        session = await room.append_exchange(db, session, team_utterance="", guide_response=speech)
        _settle_later(background, session, team_utterance="", guide_response=speech)
        return TurnResponse(
            session_id=session.id,
            audio_url=clip_url(audio_key),
            transcript="",
            peer_cue=outcome.peer_cue,
            coverage=_coverage_view(session),
            done=False,
            bridge_mode=session.bridge_mode,
        )

    validator_prompt = await get_prompt_text(db, IRPromptKey.VALIDATOR)
    turn: room.ComprehensionTurn | None = None
    if is_panorama(session.pericope):
        if not opening and session.bridge_mode == BridgeMode.CALIBRATION_PENDING.value:
            choice_speech = "" if not speech_heard.reliable_bridge_speech else transcript
            resolved = resolve_one_shot_calibration(choice_speech)
            session = await room.set_bridge_mode(db, session, resolved.mode.value)
            outcome = TurnOutcome(
                speech=bridge_calibration_acknowledgement(resolved.mode, session.language),
                transcript=transcript,
            )
        else:
            if not opening and transcript.strip():
                switched = resolve_bridge_mode_for_turn(BridgeMode(session.bridge_mode), transcript)
                if switched.explicit:
                    session = await room.set_bridge_mode(db, session, switched.mode.value)
            book = book_of(session.pericope)
            outcome = await room.run_panorama_turn(
                transcript=transcript,
                messages=session.messages or [],
                session_language=LANGUAGE_NAMES[session.language],
                language_code=session.language,
                panorama_prompt=await get_prompt_text(db, IRPromptKey.BOOK_PANORAMA),
                validator_prompt=validator_prompt,
                book=book,
                book_material=build_book_material(book),
                opening=opening,
                settings=get_settings(),
                budget=room.OPENING_BUDGET if opening else room.TURN_BUDGET,
            )
            if (
                opening
                and not outcome.used_fail_safe
                and session.bridge_mode == BridgeMode.CALIBRATION_PENDING.value
            ):
                outcome.speech = f"{outcome.speech} {bridge_calibration_question(session.language)}"
    else:
        turn = await room.run_comprehension_turn(
            db,
            session,
            speech=speech_heard,
            opening=opening,
            guide_prompt=await get_prompt_text(db, IRPromptKey.GUIDE),
            validator_prompt=validator_prompt,
            settings=get_settings(),
        )
        outcome = turn.outcome

    voiced, segments = await _voice_the_turn(outcome, language=session.language)
    if turn is not None:
        session = await room.set_bridge_mode(db, session, turn.bridge_mode)
        session = await room.save_comprehension(db, session, turn.state)
    session = await room.append_exchange(
        db,
        session,
        team_utterance=outcome.transcript,
        guide_response=outcome.speech,
    )
    if outcome.needs_person:
        session = await room.mark_needs_person(db, session)

    if _worth_settling(outcome, speech_heard, opening=opening):
        _settle_later(
            background,
            session,
            team_utterance=outcome.transcript,
            guide_response=outcome.speech,
        )

    return TurnResponse(
        session_id=session.id,
        audio_url=clip_url(voiced.key) if voiced else "",
        fixed_line=outcome.fixed_line,
        transcript=outcome.transcript,
        peer_cue=outcome.peer_cue,
        used_fail_safe=outcome.used_fail_safe,
        degraded=outcome.degraded,
        coverage=_coverage_view(session),
        done=(False if is_panorama(session.pericope) else room.session_is_done(session)),
        bridge_mode=session.bridge_mode,
        segments=segments,
    )
