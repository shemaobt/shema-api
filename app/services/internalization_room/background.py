from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import update

from app.core.database import AsyncSessionLocal
from app.core.exceptions import TranscriptionDefect
from app.core.stage_clock import count, stopwatch
from app.db.models.internalization_room import IRPromptKey, IRSession
from app.models.internalization_room import CoverageFrame
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.classify_coverage import (
    KeptRecording,
    Retelling,
    classify_coverage,
)
from app.services.internalization_room.coverage import coverage_view
from app.services.internalization_room.coverage_channel import publish
from app.services.internalization_room.earlier_passages import earlier_passages
from app.services.internalization_room.languages import LANGUAGE_NAMES, room_language
from app.services.internalization_room.nudge_channel import nudge
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.questions import get_question, transcribe_for_the_desk
from app.services.internalization_room.sessions import apply_coverage, get_session
from app.services.internalization_room.takes import extension, recording_digest, store_recording
from app.services.internalization_room.usage import counted_for

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HeardTake:
    audio: bytes
    content_type: str


async def _kept(session_id: str, take: HeardTake) -> KeptRecording:
    sha256 = recording_digest(take.audio)
    stored = await store_recording(
        take.audio,
        key=(
            f"internalization-room/takes/{session_id}/kept/{sha256}/"
            f"conto.{extension(take.content_type)}"
        ),
        sha256=sha256,
        content_type=take.content_type,
    )
    return KeptRecording(storage_key=stored.storage_key, content_type=stored.content_type)


async def _retold(
    session_id: str, turn_number: int, heard: list[Retelling], take: HeardTake | None
) -> dict[str, Any]:
    retold: dict[str, Any] = {}
    for told in heard:
        if told.approved and take is not None:
            try:
                told = told.model_copy(update={"kept": await _kept(session_id, take)})
            except Exception:
                logger.exception("The kept take of session %s did not reach the bucket", session_id)
        retold[str(turn_number)] = told.model_dump(exclude_none=True)
    return retold


async def settle_coverage(
    *,
    session_id: str,
    turn_id: str,
    turn_number: int,
    team_utterance: str,
    guide_response: str,
    pericope_num: str,
    take: HeardTake | None = None,
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
                heard: list[Retelling] = []
                with reading_the_canon_of(session.canon_pin):
                    updated = await classify_coverage(
                        coverage_state=coverage_state,
                        team_utterance=team_utterance,
                        guide_response=guide_response,
                        classifier_prompt=classifier_prompt,
                        pericope_num=pericope_num,
                        session_language=LANGUAGE_NAMES[room_language(session.language)],
                        on_retelling=heard.append,
                    )
                    retold = await _retold(session_id, turn_number, heard, take)
                    async with AsyncSessionLocal() as db:
                        settled = await apply_coverage(db, session_id, updated, retellings=retold)
            settled_frame = CoverageFrame(
                turn_id=turn_id, status="settled", coverage=coverage_view(settled)
            )
            count("delivered", publish(session_id, settled_frame))
        except Exception:
            logger.exception("Coverage settle failed for session %s", session_id)
            failed_frame = CoverageFrame(turn_id=turn_id, status="failed", coverage=None)
            count("delivered", publish(session_id, failed_frame))


async def read_the_earlier_passages_again(*, session_id: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            session = await get_session(db, session_id)
            stamp = await earlier_passages(
                db,
                project_id=session.project_id,
                pericope=session.pericope,
                prior=session.earlier_passages,
            )
            if stamp is None:
                return
            await db.execute(
                update(IRSession)
                .where(IRSession.id == session_id)
                .values(earlier_passages=stamp, updated_at=IRSession.updated_at)
            )
            await db.commit()
    except Exception:
        logger.exception("Reading the earlier passages again failed for session %s", session_id)


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
            session = await get_session(db, question.session_id)
            spoken = room_language(session.language)
            team_id = session.project_id
            await db.commit()
            await transcribe_for_the_desk(db, question, audio, language=spoken)
            if question.transcript is not None:
                nudge(team_id, "hands")
    except TranscriptionDefect:
        logger.exception("Transcription of question %s broke on our side", question_id)
    except Exception:
        logger.exception("Transcription of question %s failed", question_id)
