"""The text seam: a sentence in, the room's turn out, no microphone anywhere.

A turn only existed in this room if a person spoke it into a tablet, so whether our voice
behaves like the one that passed her five golden sessions could only be argued, never run.
This is the entry her runner drives: the real Guide, the real Validator, the real ladder,
the real pinned map. Only STT and TTS sit outside it — the team's words arrive as text in
the place the transcriber's would, and the Guide's words leave as text where the synthesiser
would have been asked for a clip.

It is a test seam and not a product surface. It exists only where a runner key is configured,
which production never sets, and nothing on a tablet knows its paths.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.db.models.internalization_room import IRPromptKey
from app.models.internalization_room_text_seam import (
    OpenTextSessionRequest,
    TextSessionResponse,
    TextTurnRequest,
    TextTurnResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.languages import LANGUAGE_NAMES, normalize
from app.services.internalization_room.prompts import get_prompt_text

router = APIRouter()

#: The header her runner already presents to her app. The same name here is what lets one
#: base URL be the only thing that changes between her stack and this one.
ACCESS_CODE_HEADER = "X-Access-Code"


async def require_runner(
    x_access_code: str | None = Header(default=None, alias=ACCESS_CODE_HEADER),
) -> None:
    """The runner at the seam's door — and no door at all where no key was configured.

    Production sets no key, so the seam answers there as a route that does not exist: a 401
    would announce a credential worth guessing at on a public deployment, and a 400 naming
    the missing variable would say what to set. Only a deployment somebody pointed a runner
    at has anything here to refuse.
    """
    configured = get_settings().internalization_room_runner_key
    if not configured:
        raise NotFoundError("Not Found")
    if not x_access_code or not secrets.compare_digest(x_access_code, configured):
        raise AuthenticationError(f"Missing or invalid {ACCESS_CODE_HEADER} header")


runner_dep = Depends(require_runner)


def _outcome_tag(outcome: room.TurnOutcome) -> str:
    """The tag the judge is defined against, read off what the turn already records.

    A turn that fell to a pre-approved line says so. A voiced turn carrying the Validator's
    issues is one the Validator mended: its contract lists no issues on a `pass`, and the only
    other verdict that voices anything is `correct`, which lists every problem it repaired.
    """
    if outcome.used_fail_safe:
        return "fail_safe"
    if outcome.issues:
        return "corrected"
    return "pass"


def _language_code(named: str) -> str:
    """The room's code for a language named either way her scripts and our app name it."""
    code = normalize(named)
    if code is not None:
        return code
    spoken = named.casefold()
    for candidate, name in LANGUAGE_NAMES.items():
        if name.casefold() in spoken and normalize(candidate) is not None:
            return candidate
    raise ValidationError(f"The room does not speak {named!r}")


@router.post("/text-seam/session", response_model=TextSessionResponse, dependencies=[runner_dep])
async def open_text_session(
    payload: OpenTextSessionRequest, db: AsyncSession = Depends(get_db)
) -> TextSessionResponse:
    session = await room.create_session(
        db, pericope=payload.pericopeId, language=_language_code(payload.language)
    )
    return TextSessionResponse(
        sessionId=session.id, pericopeId=session.pericope, language=session.language
    )


@router.post("/text-seam/turn", response_model=TextTurnResponse, dependencies=[runner_dep])
async def take_text_turn(
    payload: TextTurnRequest, db: AsyncSession = Depends(get_db)
) -> TextTurnResponse:
    """One turn of the room with the team's words already in hand.

    The same turn `take_turn` runs, minus the two things that sit outside it: nothing is
    transcribed, because the words arrived as text, and nothing is synthesized, because the
    words leave as text. A kickoff is the opening — the session's very first line, which
    belongs to the Guide — and a kickoff on a session that has already spoken is refused the
    way her app refuses it, rather than read as a returning team.
    """
    session = await room.get_session(db, payload.sessionId)
    if payload.kickoff and session.messages:
        raise ConflictError("session already open")
    if not payload.kickoff and payload.text is None:
        raise ValidationError("no text or kickoff")

    turn = await room.run_comprehension_turn(
        db,
        session,
        speech=HeardSpeech(text=payload.text or "", bridge_language=session.language),
        opening=payload.kickoff,
        guide_prompt=get_prompt_text(IRPromptKey.GUIDE),
        validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
        settings=get_settings(),
    )
    outcome = turn.outcome
    session = await room.save_comprehension(db, session, turn.state)
    session = await room.append_exchange(
        db, session, team_utterance=outcome.transcript, guide_response=outcome.speech
    )
    return TextTurnResponse(
        sessionId=session.id,
        transcript=outcome.transcript,
        guideText=outcome.speech,
        outcome=_outcome_tag(outcome),
    )
