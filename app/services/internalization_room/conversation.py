from __future__ import annotations

from typing import Any, Literal

from app.db.models.internalization_room import IRSession
from app.models.internalization_room import ConversationResponse, ConversationTurn
from app.services.internalization_room.fail_safe import FailSafe

_CATEGORY_NAMES = {each.value: each.name.lower() for each in FailSafe}


def conversation_of(session: IRSession) -> ConversationResponse:
    return ConversationResponse(
        session_id=session.id,
        turns=[_turn_of(message) for message in the_conversation(session)],
    )


def the_conversation(session: IRSession) -> list[dict[str, Any]]:
    """A line without the telling-back stamp counts as the conversation, so older sessions read."""
    return [message for message in session.messages or [] if not message.get("told_back")]


def guide_turns_of(session: IRSession) -> int:
    return sum(1 for line in the_conversation(session) if line.get("role") == "guide")


def _turn_of(message: dict[str, Any]) -> ConversationTurn:
    letter = message.get("category") or ""
    fail_safe = message["role"] == "guide" and (
        message.get("outcome") == "fail_safe" or bool(letter)
    )
    return ConversationTurn(
        role="team" if message["role"] == "room" else message["role"],
        text=message.get("text", ""),
        at=message.get("at"),
        fail_safe=fail_safe,
        fail_safe_category=_CATEGORY_NAMES.get(letter) if fail_safe else None,
        note_kind=_note_kind_of(message),
    )


def _note_kind_of(message: dict[str, Any]) -> Literal["opening", "room"] | None:
    # «(inaudible)» is the team's turn that was not heard, unmarked on purpose (sessions.py:582).
    if message.get("opening_note"):
        return "opening"
    if message.get("room_note") or message["role"] == "room":
        return "room"
    return None
