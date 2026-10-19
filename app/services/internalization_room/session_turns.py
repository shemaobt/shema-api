from __future__ import annotations

import re
from datetime import datetime
from typing import Any, NamedTuple

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.internalization_room import IRSession
from app.models.internalization_room import (
    BoundaryTurn,
    SessionBoundaryTurnsResponse,
    SessionTurn,
    SessionTurnsResponse,
    TurnMomentStep,
    TurnOutcomeCode,
    TurnTeamSide,
    TurnTraceStep,
    TurnVoiceSide,
)
from app.services.internalization_room.conversation import the_conversation
from app.services.internalization_room.name_check import stored_opening_note
from app.services.internalization_room.synthesize_facilitator_speech import (
    synthesize_facilitator_speech,
)
from app.services.internalization_room.voice_handles import turn_audio_url
from app.services.oral_collector import gcs_utils
from app.services.platform.tts import MIME_TYPE, is_stored

LISTEN_MINUTES = 15

_OUTCOMES: dict[str, TurnOutcomeCode] = {
    "pass": "validated",
    "corrected": "corrected",
    "fail_safe": "fail_safe",
}

_JS_SPACE = (
    "[\\t\\n\\v\\f\\r \\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]"
)
_PYTHON_ONLY_FOLDS = str.maketrans("\u0130\u0131\u017f\u212a", "\x00\x00\x00\x00")
_JS_WORD = "[A-Za-z0-9_]"
_JS_EDGE = f"(?:(?<={_JS_WORD})(?!{_JS_WORD})|(?<!{_JS_WORD})(?={_JS_WORD}))"


def _as_javascript(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern.replace(r"\s", _JS_SPACE).replace(r"\b", _JS_EDGE), re.IGNORECASE)


_SELF_NAME = _as_javascript(r"\b(facilitador(a)?\s+digital|digital\s+facilitator)\b")
_HANDS_OFF = [
    _as_javascript(pattern)
    for pattern in (
        r"\b(seu|sua|de\s+vocês|de\s+voces|ao|para\s+o|para\s+a|pro|pra|com\s+o|com\s+a)\s+facilitador(a)?\b",
        r"\bfacilitador(a)?\s+(humano|humana|de\s+vocês|de\s+voces|da\s+equipe)\b",
        r"\b(seu|sua|de\s+vocês|de\s+voces|ao|para\s+o|para\s+a|pro|pra|com\s+o|com\s+a)\s+consultor(a)?\b",
        r"\b(your|the|a)\s+(human\s+)?facilitator\b",
        r"\b(your|the|a)\s+(human\s+)?consultant\b",
        r"\b(passagem|história|historia|texto)\s+não\s+(nos\s+)?(conta|diz|fala|mostra|revela|responde|explica)",
        r"\bnão\s+(nos\s+)?(conta|diz)\s+isso\b",
        r"\bisso\s+a\s+(história|historia|passagem)\s+não\s+conta\b",
        r"\b(passagem|história|historia)\s+(fica|está|esta)\s+(em\s+silêncio|em\s+silencio|calada|quieta)\b",
        r"\bnão\s+temos\s+como\s+saber\b",
        r"\b(passage|story|text)\s+(does\s*n['\u2019]?t|doesn['\u2019]?t|does\s+not|is\s+quiet|stays\s+quiet|is\s+silent)\b",
        r"\b(does\s+not|doesn['\u2019]?t)\s+tell\s+us\b",
    )
]


def is_boundary_turn(outcome: TurnOutcomeCode, text: str, *, opening: bool) -> bool:
    """Marcia's boundary turn (`src/observe/dossier.ts` at 18fa7c4, `isBoundaryTurn`): a fail-safe,
    or a line past the opening that hands the question to the team's own facilitator or names
    the passage's silence, read with the Guide's own name taken out.
    """
    if outcome == "fail_safe":
        return True
    if opening:
        return False
    spoken = _SELF_NAME.sub(" ", text.translate(_PYTHON_ONLY_FOLDS))
    return any(pattern.search(spoken) for pattern in _HANDS_OFF)


def turns_of(session: IRSession) -> SessionTurnsResponse:
    """The session's turns, oldest first, as the team's side and the voice's side of each.

    The opening has no team side.
    """
    return SessionTurnsResponse(
        session_id=session.id,
        turns=[
            SessionTurn(
                team=None if opening else _team_side(guide),
                voice=_voice_side(guide, session.id, number, opening=opening),
            )
            for number, (guide, opening) in enumerate(_voice_turns(session))
        ],
    )


def boundary_turns_of(session: IRSession) -> SessionBoundaryTurnsResponse:
    kickoff = stored_opening_note(session)
    marked = [
        BoundaryTurn(
            number=number,
            outcome=turn.voice.outcome,
            team=(turn.team.guide_heard if turn.team else kickoff) or "",
            guide=turn.voice.text,
        )
        for number, turn in enumerate(turns_of(session).turns)
        if turn.voice.boundary
    ]
    return SessionBoundaryTurnsResponse(session_id=session.id, count=len(marked), turns=marked)


async def turn_clip_url(session: IRSession, number: int) -> str:
    """A short-lived signed address for the clip of one voice turn.

    The clip the turn stored is played whenever its object is still there, whichever voice
    made it. A turn stored without one, or whose object is gone, is voiced once in the
    room's current voice: the key is the words' content hash, so every later play finds it.
    """
    turns = _voice_turns(session)
    if not 0 <= number < len(turns):
        raise NotFoundError(f"Turn {number} of session {session.id} not found")
    settings = get_settings()
    if not settings.gcs_platform_bucket:
        raise ValidationError("GCS_PLATFORM_BUCKET is not configured")
    entry, _ = turns[number]
    key = entry.get("voice_key")
    if not key or not await is_stored(key):
        voiced, _ = await synthesize_facilitator_speech(
            entry.get("text", ""), language=session.language
        )
        key = voiced.key
    return await gcs_utils.generate_signed_download_url(
        settings.gcs_platform_bucket,
        key,
        expiry_minutes=LISTEN_MINUTES,
        response_content_type=MIME_TYPE,
    )


def _voice_turns(session: IRSession) -> list[tuple[dict[str, Any], bool]]:
    """The conversation's Guide entries, oldest first, each with whether it is the opening.

    A turn ends on the Guide's entry, which carries the facts of both sides. The opening is a
    Guide entry with nothing said before it and no take heard: a first take the room missed
    writes «(inaudible)» before its Guide entry and the take's facts on it, and is the team's
    turn.
    """
    turns: list[tuple[dict[str, Any], bool]] = []
    said_before = False
    for message in the_conversation(session):
        if message.get("opening_note"):
            continue
        if message.get("role") == "guide":
            turns.append((message, not said_before and "mother_tongue" not in message))
        said_before = True
    return turns


class TeamTurn(NamedTuple):
    words: str
    at: datetime


def team_turn_of(session: IRSession, number: int) -> TeamTurn:
    conversation = the_conversation(session)
    entry, _ = _voice_turns(session)[number]
    return TeamTurn(
        words=str(conversation[conversation.index(entry) - 1]["text"]),
        at=datetime.fromisoformat(entry["at"]),
    )


def last_turn_number(session: IRSession) -> int:
    return len(_voice_turns(session)) - 1


def _team_side(guide: dict[str, Any]) -> TurnTeamSide:
    cut = guide.get("interrupted")
    return TurnTeamSide(
        language=guide.get("language"),
        language_probability=guide.get("language_probability"),
        take_ms=guide.get("take_ms"),
        mother_tongue=guide.get("mother_tongue"),
        interrupted_at_s=cut["at_ms"] / 1000 if cut else None,
        guide_heard=guide.get("guide_heard"),
    )


def _voice_side(
    guide: dict[str, Any], session_id: str, number: int, *, opening: bool
) -> TurnVoiceSide:
    outcome: TurnOutcomeCode = (
        "fail_safe"
        if guide.get("category")
        else _OUTCOMES.get(guide.get("outcome", ""), "no_record")
    )
    text = guide.get("text", "")
    return TurnVoiceSide(
        outcome=outcome,
        boundary=is_boundary_turn(outcome, text, opening=opening),
        attempts=sum(
            1
            for attempt in guide.get("attempts") or []
            if attempt.get("draft") or not attempt.get("note")
        ),
        trace=[TurnTraceStep.model_validate(step) for step in guide.get("attempts") or []],
        accepted_ids=guide.get("accepted_ids") or [],
        recognition_ms=guide.get("recognition_ms"),
        reply_ms=guide.get("reply_ms"),
        synthesis_ms=guide.get("synthesis_ms"),
        model=guide.get("model"),
        text=text,
        audio_url=turn_audio_url(session_id, number),
        moment=TurnMomentStep.model_validate(guide["moment"]) if "moment" in guide else None,
    )
