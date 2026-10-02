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

import logging
import secrets
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room.sessions import _scene_of, _worth_settling
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
    GoldenSessionRequest,
    GoldenSessionResponse,
    GoldenTurnRequest,
    GoldenTurnResponse,
    ModelCall,
)
from app.services import internalization_room as room
from app.services.internalization_room.background import settle_coverage
from app.services.internalization_room.comprehension.checkpoints import scene_ids_for
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.languages import LANGUAGE_NAMES, normalize
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.turn.speech import interrupted_note, mother_tongue_note

router = APIRouter()

#: The header the back-translation seam reads the runner key in. The Golden doors read the
#: same key as her runner sends it, a bearer credential.
ACCESS_CODE_HEADER = "X-Access-Code"


def _the_runner_key(presented: str | None, header: str) -> None:
    """The runner at a seam's door — and no door at all where no key was configured.

    Production sets no key, so every door behind it answers there as a route that does not
    exist: a 401 would announce a credential worth guessing at on a public deployment, and a
    400 naming the missing variable would say what to set. Only a deployment somebody pointed
    a runner at has anything here to refuse. One rule, whichever header the door reads.
    """
    configured = get_settings().internalization_room_runner_key
    if not configured:
        raise NotFoundError("Not Found")
    if not presented or not secrets.compare_digest(presented.encode(), configured.encode()):
        raise AuthenticationError(f"Missing or invalid {header} header")


async def require_runner(
    x_access_code: str | None = Header(default=None, alias=ACCESS_CODE_HEADER),
) -> None:
    _the_runner_key(x_access_code, ACCESS_CODE_HEADER)


async def require_golden_runner(authorization: str | None = Header(default=None)) -> None:
    scheme, _, token = (authorization or "").partition(" ")
    _the_runner_key(token.strip() if scheme.lower() == "bearer" else None, "Authorization")


runner_dep = Depends(require_runner)
golden_runner_dep = Depends(require_golden_runner)

#: The calls the turn in flight has made, when a turn is collecting them. A context variable
#: because the record is written by `call_agent` deep inside the turn, on the same task, and
#: two runners driving two sessions at once must not read each other's calls.
_COLLECTING: ContextVar[list[ModelCall] | None] = ContextVar(
    "internalization_room_text_seam_calls", default=None
)


class _ModelCalls(logging.Handler):
    """Reads each answered call off the usage line `call_agent` already writes.

    Not a second ledger: the room reports what a call cost in exactly one place, and this is
    that line read back for the runner instead of only for the operator's grep. A record that
    names a rung without token counts is the ladder stepping down, not a call answered.
    """

    def emit(self, record: logging.LogRecord) -> None:
        calls = _COLLECTING.get()
        written = record.__dict__
        if calls is None or "input_tokens" not in written:
            return
        calls.append(
            ModelCall(
                role=written["role"],
                rung=written["rung"],
                input_tokens=written["input_tokens"],
                output_tokens=written["output_tokens"],
                cache_read_tokens=written["cache_read_tokens"],
                cache_write_tokens=written["cache_write_tokens"],
                latency_ms=written.get("latency_ms"),
                cost_usd=written.get("cost_usd"),
            )
        )


logging.getLogger("app.services.internalization_room.llm").addHandler(_ModelCalls())


@contextmanager
def _collecting_model_calls() -> Iterator[list[ModelCall]]:
    calls: list[ModelCall] = []
    token = _COLLECTING.set(calls)
    try:
        yield calls
    finally:
        _COLLECTING.reset(token)


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


def _heard(payload: GoldenTurnRequest, *, language: str) -> HeardSpeech:
    """The team's side of the turn as the transcriber would have handed it over.

    The opening has no team side. A mother-tongue note carries the one fact the recognizer
    reports about such a take — a confident detection of a language that is not the
    session's — over the room's own note for it, and nothing invented about which language it
    was; `und` is the code the room's own tests give an undetermined language. An interruption
    puts her note in front of whatever words came with it, as her app does. Her `noteText` is
    not read: the room renders its own notes, and the response's `transcript` says which.
    """
    if payload.roomNote == "session_start":
        return HeardSpeech(bridge_language=language)
    cut = payload.interrupted or payload.roomNote == "interrupted"
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
    said = [interrupted_note(language)] if cut else []
    if payload.teamText and payload.teamText.strip():
        said.append(payload.teamText)
    if not said:
        raise ValidationError("no teamText or roomNote")
    return HeardSpeech(text=" ".join(said), bridge_language=language)


def _scene_rehearsals(payload: GoldenTurnRequest, pericope: str) -> list[str] | None:
    """Her carried list of rehearsed scenes, refused when it names a scene the passage lacks."""
    if payload.sceneRehearsals is None:
        return None
    unknown = sorted(set(payload.sceneRehearsals) - set(scene_ids_for(pericope)))
    if unknown:
        raise ValidationError(f"{pericope} has no scene {', '.join(unknown)}")
    return payload.sceneRehearsals


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
        turn = await room.run_comprehension_turn(
            db,
            session,
            speech=heard,
            opening=opening,
            guide_prompt=get_prompt_text(IRPromptKey.GUIDE),
            validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
            settings=get_settings(),
        )
        outcome = turn.outcome
        session = await room.append_exchange(
            db,
            session,
            team_utterance=outcome.transcript,
            guide_response=outcome.speech,
            outcome=outcome,
            scene=_scene_of(session, outcome.transcript),
            state=turn.state,
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
        transcript=outcome.room_note or outcome.transcript,
        complete=await room.stored_as_done(db, session.id),
        latencyMs=round((time.monotonic() - started) * 1000),
        usage=calls,
    )
