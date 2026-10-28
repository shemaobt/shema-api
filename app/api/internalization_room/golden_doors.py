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

import re
import time
import uuid
from functools import partial

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room.sessions import _scene_of, _worth_settling, draft_the_turn_as_text
from app.api.internalization_room.text_seam import (
    _collecting_model_calls,
    _language_code,
    _the_runner_key,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import ConflictError, ValidationError
from app.db.models.internalization_room import IRPromptKey, IRSession, IRSessionStatus
from app.models.internalization_room_golden_doors import (
    GoldenRehearsalRequest,
    GoldenRehearsalResponse,
    GoldenRehearsalSendRequest,
    GoldenSessionRequest,
    GoldenSessionResponse,
    GoldenTurnRequest,
    GoldenTurnResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room import scene_rehearsals as scenes
from app.services.internalization_room.background import settle_coverage
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.canon.scene_ids import scene_ids_for
from app.services.internalization_room.golden_rehearsal import keep_a_golden_rehearsal
from app.services.internalization_room.hearing import HeardSpeech, SentSceneRehearsal
from app.services.internalization_room.name_check import hear_the_names, stored_opening_note
from app.services.internalization_room.passage_turn import accepted_send_backs
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.session_turns import last_turn_number
from app.services.internalization_room.sessions import the_opening_note, was_opened
from app.services.internalization_room.turn.speech import mother_tongue_note, scene_rehearsal_note

router = APIRouter()


async def require_golden_runner(authorization: str | None = Header(default=None)) -> None:
    scheme, _, token = (authorization or "").partition(" ")
    _the_runner_key(token.strip() if scheme.lower() == "bearer" else None, "Authorization")


golden_runner_dep = Depends(require_golden_runner)

_HER_COUNT = re.compile(r"\((\d+) (?:frases|phrases)\)")


def _heard(payload: GoldenTurnRequest, *, language: str) -> HeardSpeech:
    """Her turn mapped onto what the transcriber would have handed over.

    The opening has no team side. A mother-tongue note carries the one fact the recognizer
    reports about such a take — a language that is not the session's — and nothing invented
    about how sure it was or which language it was; `und` is the code the room's own tests
    give an undetermined language. Her `teamText`, empty or not, is the
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
            take_ms=take_ms,
            interrupted=cut,
        )
    if payload.teamText is None and payload.roomNote is None and not cut:
        raise ValidationError("no teamText or roomNote")
    return HeardSpeech(text=payload.teamText or "", bridge_language=language, interrupted=cut)


def _scene_rehearsals(
    payload: GoldenTurnRequest | GoldenRehearsalSendRequest, pericope: str
) -> list[str] | None:
    """Her carried list of rehearsed scenes, refused when it names a scene the passage lacks."""
    if payload.sceneRehearsals is None:
        return None
    unknown = sorted(set(payload.sceneRehearsals) - set(scene_ids_for(pericope)))
    if unknown:
        raise ValidationError(f"{pericope} has no scene {', '.join(unknown)}")
    return payload.sceneRehearsals


def _her_rehearsal(text: str) -> tuple[int, str] | None:
    """Her `rehearsalTeamText` read back: the frases her note counts, one without a count, and
    the pieces behind the note."""
    counted = _HER_COUNT.search(text.partition("]")[0])
    frases = int(counted.group(1)) if counted else 1
    for code in ("pt", "en"):
        note = scene_rehearsal_note(code, frases)
        pieces = text[len(note) :].strip()
        if text.startswith(note) and pieces:
            return frases, pieces
    return None


def _the_scene_that_entered(carried: list[str] | None, session: IRSession) -> str | None:
    """The one scene the carried list gained since the last turn that carried one."""
    before: list[str] = next(
        (
            m["scene_rehearsals"]
            for m in reversed(session.messages or [])
            if m.get("scene_rehearsals") is not None
        ),
        [],
    )
    entered = [scene for scene in carried or [] if scene not in before]
    return entered[0] if len(entered) == 1 else None


def _as_a_rehearsal_arriving(
    heard: HeardSpeech, carried: list[str] | None, session: IRSession
) -> HeardSpeech:
    """A team turn whose words open with her rehearsal note is a scene rehearsal arriving: the
    turn is handed the pieces and the rehearsal, and the room renders her note once, in front."""
    rehearsal = _her_rehearsal(heard.text)
    if rehearsal is None:
        return heard
    frases, pieces = rehearsal
    return heard.model_copy(
        update={
            "text": pieces,
            "scene_rehearsal": SentSceneRehearsal(
                rehearsal_id="",
                n=0,
                frases=frases,
                scene=_the_scene_that_entered(carried, session),
            ),
        }
    )


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
    "/golden/rehearsal",
    response_model=GoldenRehearsalResponse,
    dependencies=[golden_runner_dep],
    include_in_schema=False,
)
async def keep_golden_rehearsal(
    payload: GoldenRehearsalRequest, db: AsyncSession = Depends(get_db)
) -> GoldenRehearsalResponse:
    session = await room.get_session(db, payload.sessionId)
    rehearsal = await keep_a_golden_rehearsal(
        db, session, scene=payload.sceneId, pieces=payload.pieces
    )
    return GoldenRehearsalResponse(rehearsalId=rehearsal.id)


@router.post(
    "/golden/rehearsal/send",
    response_model=GoldenTurnResponse,
    dependencies=[golden_runner_dep],
    include_in_schema=False,
)
async def send_golden_rehearsal(
    payload: GoldenRehearsalSendRequest, db: AsyncSession = Depends(get_db)
) -> GoldenTurnResponse:
    session = await room.get_session(db, payload.sessionId)
    rehearsal = await scenes.scene_rehearsal_in_session(db, session.id, payload.rehearsalId)
    with reading_the_canon_of(session.canon_pin):
        rehearsed = _scene_rehearsals(payload, session.pericope)
    bound_s = get_settings().internalization_room_turn_bound_ms / 1000
    background = BackgroundTasks()
    started = time.monotonic()
    with _collecting_model_calls() as calls:
        await scenes.send_the_scene_rehearsal(
            db,
            session,
            rehearsal,
            turn_id=payload.turnId,
            closes=None if payload.closes is None else str(payload.closes),
            project_id="",
            bound_s=bound_s,
            draft=partial(
                draft_the_turn_as_text,
                db,
                session,
                background=background,
                opening=False,
                halted=session.status is IRSessionStatus.NEEDS_PERSON,
                bound_s=bound_s,
                scene_rehearsals=rehearsed,
            ),
        )
        await background()
    await db.refresh(session)
    *_, guide = session.messages
    return GoldenTurnResponse(
        guideText=guide["text"],
        outcome=guide["outcome"],
        transcript=guide["guide_heard"],
        complete=await room.stored_as_done(db, session.id),
        latencyMs=round((time.monotonic() - started) * 1000),
        usage=calls,
        acceptedIds=guide.get("accepted_ids", []),
        acceptedSendBacks=len(
            accepted_send_backs(guide.get("attempts", []), guide.get("accepted_ids", []))
        ),
    )


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
    if opening and was_opened(session):
        raise ConflictError("session already open")
    heard = _heard(payload, language=session.language)
    with reading_the_canon_of(session.canon_pin):
        rehearsed = _scene_rehearsals(payload, session.pericope)
    heard = _as_a_rehearsal_arriving(heard, rehearsed, session)
    await db.commit()

    started = time.monotonic()
    with reading_the_canon_of(session.canon_pin), _collecting_model_calls() as calls:
        outcome = await room.run_comprehension_turn(
            db,
            session,
            speech=heard,
            opening=opening,
            guide_prompt=get_prompt_text(IRPromptKey.GUIDE),
            validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
            settings=get_settings(),
            scene_rehearsals=rehearsed,
        )
        session = await room.append_exchange(
            db,
            session,
            team_utterance=outcome.transcript,
            guide_response=outcome.speech,
            outcome=outcome,
            scene=_scene_of(session, outcome.transcript),
            scene_rehearsal=heard.scene_rehearsal,
            scene_rehearsals=rehearsed,
            opening_note=the_opening_note(session) if opening else "",
            commit=False,
        )
        hear_the_names(
            db,
            session,
            team=stored_opening_note(session) if opening else outcome.transcript,
            voice=outcome.speech,
        )
        await db.commit()
        if _worth_settling(outcome, heard):
            await settle_coverage(
                session_id=session.id,
                turn_id=str(uuid.uuid4()),
                turn_number=last_turn_number(session),
                team_utterance=outcome.transcript,
                guide_response=outcome.speech,
                pericope_num=session.pericope,
            )
    return GoldenTurnResponse(
        guideText=outcome.speech,
        outcome=room.outcome_tag(outcome),
        transcript=outcome.guide_heard,
        complete=await room.stored_as_done(db, session.id),
        latencyMs=round((time.monotonic() - started) * 1000),
        usage=calls,
        acceptedIds=outcome.accepted_ids,
    )
