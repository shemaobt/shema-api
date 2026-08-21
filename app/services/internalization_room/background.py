from __future__ import annotations

import logging

from app.core.database import AsyncSessionLocal
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room.classify_coverage import classify_coverage
from app.services.internalization_room.prompts import get_prompt_text
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
