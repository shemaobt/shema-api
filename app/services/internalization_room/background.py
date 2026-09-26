from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import TranscriptionDefect
from app.core.stage_clock import count, stage, stopwatch
from app.db.models.internalization_room import IRPromptKey, IRSegment, IRSession, IRTake
from app.models.internalization_room import CoverageFrame
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    CorrectionAhead,
    CorrectionToVerify,
    ReadAhead,
    analyse_telling_back,
    correction_to_verify,
    findings_after_correction,
    rehearsed_parts,
    untold_parts,
    verify_correction,
)
from app.services.internalization_room.classify_coverage import classify_coverage
from app.services.internalization_room.coverage import coverage_view
from app.services.internalization_room.coverage_channel import publish
from app.services.internalization_room.languages import LANGUAGE_NAMES
from app.services.internalization_room.part_names import addresses_for, scene_titles
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.questions import get_question, transcribe_for_the_desk
from app.services.internalization_room.segments import (
    final_segments,
    first_untold,
    retired_segments,
    told_back,
)
from app.services.internalization_room.sessions import (
    apply_coverage,
    back_translation_of,
    get_session,
    save_back_translation,
)
from app.services.internalization_room.takes import current_parts, takes_of
from app.services.internalization_room.usage import counted_for

logger = logging.getLogger(__name__)

_reading: dict[str, tuple[list[str], asyncio.Task[BackTranslationState | None]]] = {}


async def settle_coverage(
    *,
    session_id: str,
    turn_id: str,
    team_utterance: str,
    guide_response: str,
    pericope_num: str,
    opening: bool = False,
) -> None:
    """Advance the tracker after the reply has already shipped.

    Deliberately off the voice path: the team hears the Guide first and the beads settle
    during their reflection pause. Opens its own database session because the request
    that scheduled this has already been answered and closed.

    It opens its own usage ledger for the same reason. This runs inside the request's own
    context, so the answered turn's ledger is still in scope and a call made under it would
    be written into a total already logged. Its own book also puts the classifier's money
    where it belongs — on the session, which is what pays for it — without adding a turn the
    team did not take.
    """
    with stopwatch("[coverage-timing]", session_id):
        try:
            with counted_for(session_id):
                async with AsyncSessionLocal() as db:
                    session = await get_session(db, session_id)
                coverage_state = session.coverage_state or {}
                classifier_prompt = get_prompt_text(IRPromptKey.COVERAGE_CLASSIFIER)
                updated = await classify_coverage(
                    coverage_state=coverage_state,
                    team_utterance=team_utterance,
                    guide_response=guide_response,
                    classifier_prompt=classifier_prompt,
                    pericope_num=pericope_num,
                    opening=opening,
                    session_language=LANGUAGE_NAMES[session.language],
                )
                async with AsyncSessionLocal() as db:
                    settled = await apply_coverage(db, session_id, updated)
            settled_frame = CoverageFrame(
                turn_id=turn_id, status="settled", coverage=coverage_view(settled)
            )
            count("delivered", publish(session_id, settled_frame))
        except Exception:
            logger.exception("Coverage settle failed for session %s", session_id)
            failed_frame = CoverageFrame(turn_id=turn_id, status="failed", coverage=None)
            count("delivered", publish(session_id, failed_frame))


async def transcribe_question(*, question_id: str, audio: bytes) -> None:
    """Read a raised hand back in text after the hand has already come down.

    Off the request for the same reason the coverage settle is: what the team waits on has
    to be what the team is waiting *for*. The transcript is the Desk's, and making a room
    hold still for a provider — a client built with a 120 s read timeout — charges the wait
    to people who cannot see what is happening and cannot check whether their question
    arrived. The question is committed before this runs, so the worst this can cost is the
    text.

    Opens its own database session because the request that scheduled it has already been
    answered and closed, the same way `settle_coverage` does.

    **A transcriber that is broken for everyone is silent here**, and that is worth saying
    plainly rather than trusting to a log nobody reads: with no caller left, nothing turns
    a systematic failure into an answer somebody sees. What makes it detectable is the row
    — a question with audio and a null `transcript`, older than some floor, is a query, and
    a whole inbox of them is the shape of this failing. Telemetry for it belongs in ENG-482
    (CS-06), not here.
    """
    try:
        async with AsyncSessionLocal() as db:
            question = await get_question(db, question_id)
            spoken = (await get_session(db, question.session_id)).language
            await db.commit()
            await transcribe_for_the_desk(db, question, audio, language=spoken)
    except TranscriptionDefect:
        logger.exception("Transcription of question %s broke on our side", question_id)
    except Exception:
        logger.exception("Transcription of question %s failed", question_id)


async def read_ahead(*, session_id: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            session = await get_session(db, session_id)
            state = back_translation_of(session)
            final = await final_segments(db, session_id)
            told = told_back(final)
            key = [segment.id for segment in told]
            outrun = _reading.get(session_id)
            if outrun is not None and outrun[0] != key:
                outrun[1].cancel()
            takes = await takes_of(db, session_id)
            if first_untold(final) is not None or untold_parts(
                current_parts(takes), rehearsed_parts(final)
            ):
                return
            retired = await retired_segments(db, session_id)
            correction = correction_to_verify(state, told, retired)
            running: asyncio.Task[BackTranslationState | None]
            with counted_for(session_id):
                if correction is not None:
                    running = asyncio.create_task(
                        _verify_and_keep(db, session, state, told, retired, takes, correction)
                    )
                else:
                    running = asyncio.create_task(_read_and_keep(db, session, state, told))
                _reading[session_id] = (key, running)
                try:
                    await asyncio.wait([running])
                finally:
                    if _reading.get(session_id) == (key, running):
                        del _reading[session_id]
    except Exception:
        logger.exception("Reading ahead failed for session %s", session_id)


async def _read_and_keep(
    db: AsyncSession, session: IRSession, state: BackTranslationState, told: list[IRSegment]
) -> BackTranslationState | None:
    try:
        read = await analyse_telling_back(
            segments=told,
            scope=state.scope or session.pericope,
            pericope_num=session.pericope,
            analyst_prompt=get_prompt_text(IRPromptKey.BT_ANALYST),
            session_language=LANGUAGE_NAMES[session.language],
            language_code=session.language,
            settings=get_settings(),
            session_id=session.id,
        )
        if read is None:
            return None
        ahead = ReadAhead(segment_ids=[segment.id for segment in told], findings=read.findings)
        await db.refresh(session)
        kept = back_translation_of(session)
        kept.read_ahead = ahead
        await save_back_translation(db, session, kept)
        return kept
    except Exception:
        logger.exception("Reading ahead failed for session %s", session.id)
        return None


async def _verify_and_keep(
    db: AsyncSession,
    session: IRSession,
    state: BackTranslationState,
    told: list[IRSegment],
    retired: list[IRSegment],
    takes: list[IRTake],
    correction: CorrectionToVerify,
) -> BackTranslationState | None:
    try:
        checked = await verify_correction(
            findings=correction.findings,
            earlier=correction.earlier,
            corrected=correction.corrected,
            chunk=correction.chunk,
            scope=state.scope or session.pericope,
            pericope_num=session.pericope,
            correction_prompt=get_prompt_text(IRPromptKey.BT_CORRECTION),
            session_language=LANGUAGE_NAMES[session.language],
            addresses=addresses_for(
                told,
                current_parts(takes),
                scene_titles(session),
                session.language,
                superseded=retired,
            ),
            settings=get_settings(),
            session_id=session.id,
        )
        if checked is None:
            return None
        ahead = CorrectionAhead(
            segment_ids=[segment.id for segment in told],
            resolved=checked.resolved,
            findings=checked.findings,
        )
        await db.refresh(session)
        kept = back_translation_of(session)
        kept.correction_ahead = ahead
        await save_back_translation(db, session, kept)
        if not findings_after_correction(state.findings, checked, correction.corrected):
            return await _read_and_keep(db, session, kept, told) or kept
        return kept
    except Exception:
        logger.exception("Reading ahead failed for session %s", session.id)
        return None


async def _joined_ahead(
    session_id: str, state: BackTranslationState, told: list[IRSegment]
) -> None:
    running = _reading.get(session_id)
    if running is None or running[0] != [segment.id for segment in told]:
        return
    with stage("read_ahead"):
        await asyncio.wait([running[1]])
    kept = None if running[1].cancelled() else running[1].result()
    if kept is not None:
        state.read_ahead = kept.read_ahead
        state.correction_ahead = kept.correction_ahead


async def the_reading_ahead(
    session_id: str, state: BackTranslationState, told: list[IRSegment]
) -> ReadAhead | None:
    await _joined_ahead(session_id, state, told)
    return state.read_ahead_of(told)


async def the_correction_ahead(
    session_id: str, state: BackTranslationState, told: list[IRSegment]
) -> CorrectionAhead | None:
    await _joined_ahead(session_id, state, told)
    return state.correction_ahead_of(told)
