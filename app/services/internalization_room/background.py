from __future__ import annotations

import logging

from app.core.database import AsyncSessionLocal
from app.core.exceptions import TranscriptionDefect
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room.classify_coverage import classify_coverage
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.questions import get_question, transcribe_for_the_desk
from app.services.internalization_room.sessions import apply_coverage, get_session

logger = logging.getLogger(__name__)


async def settle_coverage(
    *, session_id: str, team_utterance: str, guide_response: str, pericope_num: str
) -> None:
    """Advance the tracker after the reply has already shipped.

    Deliberately off the voice path: the team hears the Guide first and the beads settle
    during their reflection pause. Opens its own database session because the request
    that scheduled this has already been answered and closed.
    """
    try:
        async with AsyncSessionLocal() as db:
            session = await get_session(db, session_id)
            classifier_prompt = await get_prompt_text(db, IRPromptKey.COVERAGE_CLASSIFIER)
            updated = await classify_coverage(
                coverage_state=session.coverage_state or {},
                team_utterance=team_utterance,
                guide_response=guide_response,
                classifier_prompt=classifier_prompt,
                pericope_num=pericope_num,
            )
            await apply_coverage(db, session_id, updated)
    except Exception:
        logger.exception("Coverage settle failed for session %s", session_id)


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
            await transcribe_for_the_desk(db, await get_question(db, question_id), audio)
    except TranscriptionDefect:
        logger.exception("Transcription of question %s broke on our side", question_id)
    except Exception:
        logger.exception("Transcription of question %s failed", question_id)
