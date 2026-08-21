from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.db.models.internalization_room import IRPromptKey, IRSession
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.run_turn import run_turn
from app.services.internalization_room.sessions import DEFAULT_PERICOPE, get_session
from app.services.internalization_room.synthesize_facilitator_speech import (
    synthesize_facilitator_speech,
)

logger = logging.getLogger(__name__)


async def prepare_opening(panorama_session_id: str, pericope: str = DEFAULT_PERICOPE) -> None:
    """Write and voice the passage's first line while the team is still on the panorama.

    The opening is the only turn whose inputs are all known in advance — the team has not
    spoken, the coverage is untouched, the conversation is empty. Everything after it depends
    on what they say, so this is the one place where working ahead is possible at all.

    Failure here is silent on purpose: the prepared line is an optimisation, and the session
    opens perfectly well by writing it on demand.
    """
    try:
        async with AsyncSessionLocal() as db:
            outcome = await run_turn(
                transcript="",
                coverage_state={},
                messages=[],
                guide_prompt=await get_prompt_text(db, IRPromptKey.GUIDE),
                validator_prompt=await get_prompt_text(db, IRPromptKey.VALIDATOR),
                pericope_num=pericope,
                opening=True,
                already_met=True,
                settings=get_settings(),
            )
            if outcome.used_fail_safe:
                logger.info("Not keeping a fail-safe as the prepared opening")
                return
            speech, _ = await synthesize_facilitator_speech(outcome.speech)
            panorama = await get_session(db, panorama_session_id)
            panorama.prepared_speech = outcome.speech
            panorama.prepared_audio_key = speech.key
            await db.commit()
    except Exception:
        logger.exception("Could not prepare the opening for %s", pericope)


def hand_over(prepared: IRSession, opening: IRSession) -> bool:
    """Move a ready opening onto the session that will speak it, once and to the right passage.

    The panorama writes ahead without knowing which passage the team will pick, so the line
    it holds is always `DEFAULT_PERICOPE`'s: any other passage has to write its own rather
    than be given another passage's framing as if it were its own words. The source is
    cleared as it is given away, so a second session opened after the same panorama gets
    nothing here and writes on demand.
    """
    if not prepared.prepared_speech or not prepared.prepared_audio_key:
        return False
    if opening.pericope != DEFAULT_PERICOPE:
        return False
    opening.prepared_speech = prepared.prepared_speech
    opening.prepared_audio_key = prepared.prepared_audio_key
    prepared.prepared_speech = None
    prepared.prepared_audio_key = None
    return True


async def take_prepared(db: AsyncSession, session: IRSession) -> tuple[str, str] | None:
    """The line this session was handed, consumed once so a later turn never repeats it."""
    if not session.prepared_speech or not session.prepared_audio_key:
        return None
    speech, key = session.prepared_speech, session.prepared_audio_key
    session.prepared_speech = None
    session.prepared_audio_key = None
    await db.commit()
    return speech, key
