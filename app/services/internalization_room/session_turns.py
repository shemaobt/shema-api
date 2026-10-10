from __future__ import annotations

import re
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.internalization_room import IRSession
from app.models.internalization_room import (
    SessionTurn,
    SessionTurnsResponse,
    TurnOutcomeCode,
    TurnTeamSide,
    TurnVoiceSide,
)
from app.services.internalization_room.conversation import the_conversation
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

_SELF_NAME = re.compile(r"\b(facilitador(a)?\s+digital|digital\s+facilitator)\b", re.IGNORECASE)
_HANDS_OFF = [
    re.compile(pattern, re.IGNORECASE)
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
    spoken = _SELF_NAME.sub(" ", text)
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
    writes nothing before its Guide entry either, and is still the team's turn.
    """
    turns: list[tuple[dict[str, Any], bool]] = []
    said_before = False
    for message in the_conversation(session):
        if message.get("role") == "guide":
            turns.append((message, not said_before and "mother_tongue" not in message))
        said_before = True
    return turns


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
        attempts=len(guide.get("attempts") or []),
        recognition_ms=guide.get("recognition_ms"),
        reply_ms=guide.get("reply_ms"),
        synthesis_ms=guide.get("synthesis_ms"),
        model=guide.get("model"),
        text=text,
        audio_url=turn_audio_url(session_id, number),
    )
