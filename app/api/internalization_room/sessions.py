from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import device_project_dep, room_key_dep
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
    TurnResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.background import settle_coverage
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.canon.elements import absence_index
from app.services.internalization_room.coverage import counts, floor_met
from app.services.internalization_room.hearing import heard
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

router = APIRouter()

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
    )


@router.post("/sessions", response_model=SessionStateResponse, dependencies=[room_key_dep])
async def create_session(
    payload: CreateSessionRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    project_id: str | None = device_project_dep,
) -> SessionStateResponse:
    session = await room.create_session(
        db,
        pericope=payload.pericope or DEFAULT_PERICOPE,
        after_panorama=payload.after_panorama or payload.after_session is not None,
        project_id=project_id,
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


@router.post(
    "/sessions/{session_id}/turns",
    response_model=TurnResponse,
    dependencies=[room_key_dep],
)
async def take_turn(
    session_id: str,
    background: BackgroundTasks,
    response: Response,
    file: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
) -> TurnResponse:
    session = await room.get_session(db, session_id)

    transcript = ""
    opening = file is None
    if file is not None:
        audio_bytes = await file.read()
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise ValidationError("Audio payload exceeds 25 MB limit")
        transcript = await heard(audio_bytes, filename=file.filename, mime_type=file.content_type)

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
        )

    validator_prompt = await get_prompt_text(db, IRPromptKey.VALIDATOR)
    if is_panorama(session.pericope):
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
        )
    else:
        outcome = await room.run_turn(
            transcript=transcript,
            coverage_state=session.coverage_state or {},
            messages=session.messages or [],
            guide_prompt=await get_prompt_text(db, IRPromptKey.GUIDE),
            validator_prompt=validator_prompt,
            pericope_num=session.pericope,
            opening=opening,
            already_met=session.after_panorama,
            settings=get_settings(),
        )

    voiced = (
        None
        if outcome.fixed_line
        else (await room.synthesize_facilitator_speech(outcome.speech))[0]
    )
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
        done=(
            False
            if is_panorama(session.pericope)
            else floor_met(session.coverage_state or {}, session.pericope)
        ),
    )
