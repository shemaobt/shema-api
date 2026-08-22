import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import room_key_dep
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRPromptKey, IRSession, IRSessionStatus
from app.models.internalization_room import (
    BackTranslationProgress,
    CoverageView,
    CreateSessionRequest,
    NeedsPersonResponse,
    SessionStateResponse,
    SpokenSegment,
    TurnResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.background import settle_coverage
from app.services.internalization_room.calibration import (
    BRIDGE_CALIBRATION_QUESTION,
    BridgeMode,
    bridge_calibration_acknowledgement,
    resolve_bridge_mode_for_turn,
    resolve_one_shot_calibration,
)
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.canon.elements import absence_index
from app.services.internalization_room.coverage import counts
from app.services.internalization_room.hearing import HeardSpeech, heard_speech
from app.services.internalization_room.prepare_opening import (
    hand_over,
    prepare_opening,
    take_prepared,
)
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.run_turn import TurnOutcome, detects_peer_cue
from app.services.internalization_room.sessions import (
    DEFAULT_PERICOPE,
    book_of,
    is_panorama,
)
from app.services.internalization_room.voice_handles import clip_url
from app.services.platform.tts import SynthesizedSpeech

logger = logging.getLogger(__name__)

router = APIRouter()

_SEGMENT_ROLES = ("panorama", "scene")


async def _clip_or_none(text: str) -> str | None:
    try:
        entry, _ = await room.synthesize_facilitator_speech(text)
    except Exception:
        logger.warning("A movement of the opening could not be voiced; sending it whole")
        return None
    return entry.key


async def _voice_the_turn(
    outcome: room.TurnOutcome,
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
        entry, _ = await room.synthesize_facilitator_speech(outcome.speech)
        return entry

    async def movements() -> list[str | None]:
        return list(await asyncio.gather(*(_clip_or_none(part) for part in outcome.movements)))

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


def _state(session: IRSession) -> SessionStateResponse:
    return SessionStateResponse(
        session_id=session.id,
        pericope=session.pericope,
        status=str(session.status),
        coverage=_coverage_view(session),
        done=session.status is IRSessionStatus.DONE,
        back_translation=_progress(session),
        bridge_mode=session.bridge_mode,
    )


def _progress(session: IRSession) -> BackTranslationProgress:
    """What a tablet needs to pick a telling-back back up where it stopped.

    All of it was already on the session and none of it had a way out, so an app that
    forgot its session id — which is every restart, because the id lives only in memory —
    lost the retro entirely and had to record the rehearsal again.
    """
    state = room.back_translation_of(session)
    finding = state.current_finding
    return BackTranslationProgress(
        scope=state.scope,
        passes=[chunk.pass_number for chunk in state.chunks],
        spans=[[chunk.starts_ms or 0, chunk.ends_ms or 0] for chunk in state.chunks],
        retells=state.retells,
        checked=state.checked,
        finding_chunk=finding.chunk if finding else None,
        finding_kind=finding.kind.value if finding else None,
        superseded_attempts=len(state.superseded),
    )


@router.post("/sessions", response_model=SessionStateResponse, dependencies=[room_key_dep])
async def create_session(
    payload: CreateSessionRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> SessionStateResponse:
    session = await room.create_session(
        db,
        pericope=payload.pericope or DEFAULT_PERICOPE,
        after_panorama=payload.after_panorama or payload.after_session is not None,
        bridge_mode=payload.bridge_mode,
    )
    if payload.after_session:
        previous = await room.get_session(db, payload.after_session)
        if hand_over(previous, session):
            await db.commit()
    elif is_panorama(session.pericope):
        background.add_task(prepare_opening, session.id)
    return _state(session)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionStateResponse,
    dependencies=[room_key_dep],
)
async def read_session(session_id: str, db: AsyncSession = Depends(get_db)) -> SessionStateResponse:
    session = await room.get_session(db, session_id)
    return _state(session)


@router.post(
    "/sessions/{session_id}/needs-person",
    response_model=NeedsPersonResponse,
    dependencies=[room_key_dep],
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
    voiced = (await room.synthesize_facilitator_speech(last))[0] if last else None
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
    dependencies=[room_key_dep],
)
async def take_turn(
    session_id: str,
    background: BackgroundTasks,
    file: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
) -> TurnResponse:
    """One turn of the room: what the team just said goes in, the Guide's next line comes out.

    An opening is the session's first line, not merely a POST without audio. The app sends an
    audio-less turn again whenever a team walks back into a passage it left, and reading that
    as an opening had the Guide introduce itself and lay the whole passage out a second time —
    against a probe already waiting for a free retell, which the Validator then rejected, so
    the room answered a returning team with a canned line.
    """
    session = await room.get_session(db, session_id)

    speech_heard = HeardSpeech()
    opening = file is None and not (session.messages or [])
    if file is not None:
        audio_bytes = await file.read()
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise ValidationError("Audio payload exceeds 25 MB limit")
        speech_heard = await heard_speech(
            audio_bytes, filename=file.filename, mime_type=file.content_type
        )
    transcript = speech_heard.text

    if file is None and not opening:
        return await _say_it_again(session)

    ready = await take_prepared(db, session) if opening else None
    if ready is not None:
        speech, audio_key = ready
        outcome = TurnOutcome(speech=speech, transcript="", peer_cue=detects_peer_cue(speech))
        session = await room.append_exchange(db, session, team_utterance="", guide_response=speech)
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
    if is_panorama(session.pericope):
        if not opening and session.bridge_mode == BridgeMode.CALIBRATION_PENDING.value:
            choice_speech = "" if not speech_heard.reliable_bridge_speech else transcript
            resolved = resolve_one_shot_calibration(choice_speech)
            session = await room.set_bridge_mode(db, session, resolved.mode.value)
            outcome = TurnOutcome(
                speech=bridge_calibration_acknowledgement(resolved.mode),
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
                outcome.speech = f"{outcome.speech} {BRIDGE_CALIBRATION_QUESTION}"
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
        session = await room.set_bridge_mode(db, session, turn.bridge_mode)
        session = await room.save_comprehension(db, session, turn.state)

    voiced, segments = await _voice_the_turn(outcome)
    session = await room.append_exchange(
        db,
        session,
        team_utterance=outcome.transcript,
        guide_response=outcome.speech,
    )

    if not outcome.used_fail_safe and not is_panorama(session.pericope):
        background.add_task(
            settle_coverage,
            session_id=session.id,
            team_utterance=outcome.transcript,
            guide_response=outcome.speech,
            pericope_num=session.pericope,
        )

    return TurnResponse(
        session_id=session.id,
        audio_url=clip_url(voiced.key) if voiced else "",
        fixed_line=outcome.fixed_line,
        transcript=outcome.transcript,
        peer_cue=outcome.peer_cue,
        used_fail_safe=outcome.used_fail_safe,
        coverage=_coverage_view(session),
        done=(False if is_panorama(session.pericope) else room.session_is_done(session)),
        bridge_mode=session.bridge_mode,
        segments=segments,
    )
