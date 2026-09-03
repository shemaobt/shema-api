from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.db.models.internalization_room import IRPromptKey, IRSession
from app.services.internalization_room.languages import LANGUAGE_NAMES
from app.services.internalization_room.progression import active_passage
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.run_turn import OPENING_BUDGET, run_turn
from app.services.internalization_room.sessions import get_session, is_panorama
from app.services.internalization_room.synthesize_facilitator_speech import (
    synthesize_facilitator_speech,
)

logger = logging.getLogger(__name__)


async def prepare_opening(panorama_session_id: str, pericope: str | None = None) -> None:
    """Write and voice the passage's first line while the team is still on the panorama.

    The opening is the only turn whose inputs are all known in advance — the team has not
    spoken, the coverage is untouched, the conversation is empty. Everything after it depends
    on what they say, so this is the one place where working ahead is possible at all.

    Which passage it writes for is resolved from the panorama's own team, so a team six
    passages into the book gets the opening of the passage they are about to enter rather than
    the first one's. A team that has finished the book gets nothing prepared, which is the same
    outcome as any other failure here: the session writes its own line on demand.

    The passage is written down beside the line. What it is for is `hand_over`; why it cannot
    be derived instead is on the column.

    Failure here is silent on purpose: the prepared line is an optimisation, and the session
    opens perfectly well without one.
    """
    try:
        async with AsyncSessionLocal() as db:
            panorama = await get_session(db, panorama_session_id)
            spoken = panorama.language
            if pericope is None:
                pericope = await active_passage(db, project_id=panorama.project_id)
            if pericope is None:
                logger.info("Nothing left to prepare: the team has closed every passage")
                return
            outcome = await run_turn(
                transcript="",
                coverage_state={},
                messages=[],
                guide_prompt=await get_prompt_text(IRPromptKey.GUIDE),
                validator_prompt=await get_prompt_text(IRPromptKey.VALIDATOR),
                pericope_num=pericope,
                opening=True,
                already_met=True,
                session_language=LANGUAGE_NAMES[spoken],
                language_code=spoken,
                settings=get_settings(),
                budget=OPENING_BUDGET,
            )
            if outcome.used_fail_safe:
                logger.info("Not keeping a fail-safe as the prepared opening")
                return
            speech, _ = await synthesize_facilitator_speech(outcome.speech, language=spoken)
            panorama = await get_session(db, panorama_session_id)
            panorama.prepared_speech = outcome.speech
            panorama.prepared_audio_key = speech.key
            panorama.prepared_pericope = pericope
            await db.commit()
    except Exception:
        logger.exception("Could not prepare the opening for %s", pericope)


def hand_over(prepared: IRSession, opening: IRSession) -> bool:
    """Move a ready opening onto the session that will speak it, once and to the right passage.

    The line is written from one passage's meaning map, and the panorama writes it before the
    team has entered anything. Handing it to whatever session came next meant a team on one
    passage heard another's opening as their own framing — delivered as the passage's words,
    to people who cannot read and have no way to check. And the source was never cleared, so
    the same line went to every session after it.

    The passage is compared against the one recorded when the line was written, never against
    a fresh resolution: the two differ exactly when the team's history moved while the panorama
    was playing, which is the case this guard exists for.

    A line with no passage recorded is refused. That is every row written before ENG-450, and
    the bias is the floor's: what is unknown is not waved through. The cost is one session
    writing its own opening.

    A line written in another language is refused on the same grounds as another passage's.
    The two sessions can differ — a panorama opened on a tablet set to one language, the
    passage entered after somebody changed that setting — and handing the line over anyway
    would have a team meet their passage's framing in a language the rest of the session does
    not speak.
    """
    if not prepared.prepared_speech or not prepared.prepared_audio_key:
        return False
    if prepared.prepared_pericope is None or prepared.prepared_pericope != opening.pericope:
        return False
    if prepared.language != opening.language:
        return False
    opening.prepared_speech = prepared.prepared_speech
    opening.prepared_audio_key = prepared.prepared_audio_key
    # Spent. Working ahead buys one opening, not one per session that mentions the
    # panorama.
    prepared.prepared_speech = None
    prepared.prepared_audio_key = None
    prepared.prepared_pericope = None
    return True


async def take_prepared(db: AsyncSession, session: IRSession) -> tuple[str, str] | None:
    """The line this session was handed, consumed once so a later turn never repeats it.

    A panorama is handed nothing, even when a ready line is sitting on its own row — that row
    is the parking place `prepare_opening` writes to, and `hand_over` is the only way out of
    it. Reading it here opened the book by telling a team that had chosen no passage how the
    first one begins, and spent the line doing it, so the passage they went on to choose paid
    the wait this whole mechanism exists to spare them.
    """
    if is_panorama(session.pericope):
        return None
    if not session.prepared_speech or not session.prepared_audio_key:
        return None
    speech, key = session.prepared_speech, session.prepared_audio_key
    session.prepared_speech = None
    session.prepared_audio_key = None
    session.prepared_pericope = None
    await db.commit()
    return speech, key
