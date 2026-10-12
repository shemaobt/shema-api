"""The Golden doors: a sentence in, the room's turn out, no microphone anywhere.

A turn only existed in this room if a person spoke it into a tablet, so whether our voice
behaves like the one that passed her five golden sessions could only be argued, never run.
These are the two doors her runner drives, `/golden/session` and `/golden/turn`, in her
field names and with her meaning: the real Guide, the real Validator, the real ladder, the
real pinned map. Only STT and TTS sit outside it — the team's words arrive as text in
the place the transcriber's would, and the Guide's words leave as text where the synthesiser
would have been asked for a clip.

They are a test surface and not a product one. They exist only where a runner key is
configured, which production never sets, and nothing on a tablet knows their paths.
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room.sessions import _scene_of, _worth_settling
from app.api.internalization_room.text_seam import (
    _collecting_model_calls,
    _language_code,
    _outcome_tag,
    _the_runner_key,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import ConflictError, ValidationError
from app.db.models.internalization_room import IRPromptKey
from app.models.internalization_room_golden_doors import (
    GoldenSessionRequest,
    GoldenSessionResponse,
    GoldenTurnRequest,
    GoldenTurnResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.background import settle_coverage
from app.services.internalization_room.comprehension.checkpoints import scene_ids_for
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.turn.speech import mother_tongue_note

router = APIRouter()


async def require_golden_runner(authorization: str | None = Header(default=None)) -> None:
    scheme, _, token = (authorization or "").partition(" ")
    _the_runner_key(token.strip() if scheme.lower() == "bearer" else None, "Authorization")


golden_runner_dep = Depends(require_golden_runner)


def _heard(payload: GoldenTurnRequest, *, language: str) -> HeardSpeech:
    """Her turn mapped onto what the transcriber would have handed over.

    The opening has no team side. A mother-tongue note carries the one fact the recognizer
    reports about such a take — a confident detection of a language that is not the
    session's — and nothing invented about which language it was; `und` is the code the
    room's own tests give an undetermined language. Her `teamText`, empty or not, is the
    team's words. The room renders its own notes, so her `noteText` is not read; the
    response's `transcript` says what the Guide was handed. A turn with neither words nor a
    room note is refused.
    """
    cut = payload.interrupted or payload.roomNote == "interrupted"
    if payload.roomNote == "session_start":
        return HeardSpeech(bridge_language=language)
    if payload.roomNote == "mother_tongue":
        take_ms = payload.seconds * 1000 if payload.seconds else None
        return HeardSpeech(
            text=mother_tongue_note(language, take_ms),
            bridge_language=language,
            language_code="und",
            language_probability=1.0,
            take_ms=take_ms,
            interrupted=cut,
        )
    if payload.teamText is None and payload.roomNote is None and not cut:
        raise ValidationError("no teamText or roomNote")
    return HeardSpeech(text=payload.teamText or "", bridge_language=language, interrupted=cut)


def _scene_rehearsals(payload: GoldenTurnRequest, pericope: str) -> list[str] | None:
    """Her carried list of rehearsed scenes, refused when it names a scene the passage lacks."""
    if payload.sceneRehearsals is None:
        return None
    unknown = sorted(set(payload.sceneRehearsals) - set(scene_ids_for(pericope)))
    if unknown:
        raise ValidationError(f"{pericope} has no scene {', '.join(unknown)}")
    return payload.sceneRehearsals


@router.post(
    "/golden/session",
    response_model=GoldenSessionResponse,
    dependencies=[golden_runner_dep],
    include_in_schema=False,
)
async def open_golden_session(
    payload: GoldenSessionRequest, db: AsyncSession = Depends(get_db)
) -> GoldenSessionResponse:
    session = await room.create_session(
        db,
        pericope=payload.pericopeId,
        language=_language_code(payload.language),
        earlier_passages=payload.earlierPassages,
    )
    return GoldenSessionResponse(sessionId=session.id)


@router.post(
    "/golden/turn",
    response_model=GoldenTurnResponse,
    dependencies=[golden_runner_dep],
    include_in_schema=False,
)
async def play_golden_turn(
    payload: GoldenTurnRequest, db: AsyncSession = Depends(get_db)
) -> GoldenTurnResponse:
    """One turn of the room with the team's words, or a room note, already in hand.

    The same turn `take_turn` runs, minus the two things that sit outside it: nothing is
    transcribed, because the words arrived as text, and nothing is synthesized, because the
    words leave as text. `session_start` is the opening — the session's very first line, which
    belongs to the Guide — and an opening on a session that has already spoken is refused the
    way her app refuses it, rather than read as a returning team.

    The beads settle before the answer goes back rather than behind it. On a tablet the
    classifier runs during the team's reflection pause and the next turn arrives seconds
    later, so the Guide's coverage block is what the app would show; a runner's next turn
    arrives the instant this one returns, and a classifier still running would leave the
    Guide reading the beads of the turn before. Her runner runs it inline for the same reason.
    Its calls are counted with the turn's — the same money, as her cost line adds them.
    """
    session = await room.get_session(db, payload.sessionId)
    opening = payload.roomNote == "session_start"
    if opening and session.messages:
        raise ConflictError("session already open")
    heard = _heard(payload, language=session.language)
    rehearsed = _scene_rehearsals(payload, session.pericope)
    await db.commit()

    started = time.monotonic()
    with _collecting_model_calls() as calls:
        outcome = await room.run_comprehension_turn(
            db,
            session,
            speech=heard,
            opening=opening,
            guide_prompt=get_prompt_text(IRPromptKey.GUIDE),
            validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
            settings=get_settings(),
        )
        session = await room.append_exchange(
            db,
            session,
            team_utterance=outcome.transcript,
            guide_response=outcome.speech,
            outcome=outcome,
            scene=_scene_of(session, outcome.transcript),
            scene_rehearsals=rehearsed,
        )
        if _worth_settling(outcome, heard):
            await settle_coverage(
                session_id=session.id,
                turn_id=str(uuid.uuid4()),
                team_utterance=outcome.transcript,
                guide_response=outcome.speech,
                pericope_num=session.pericope,
            )
    return GoldenTurnResponse(
        guideText=outcome.speech,
        outcome=_outcome_tag(outcome),
        transcript=outcome.guide_heard,
        complete=await room.stored_as_done(db, session.id),
        latencyMs=round((time.monotonic() - started) * 1000),
        usage=calls,
    )
