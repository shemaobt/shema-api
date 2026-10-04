from __future__ import annotations

from typing import Any

from app.db.models.internalization_room import IRSession
from app.models.internalization_room import ConversationResponse, ConversationTurn
from app.services.internalization_room.fail_safe import FailSafe

_CATEGORY_NAMES = {each.value: each.name.lower() for each in FailSafe}


def conversation_of(session: IRSession) -> ConversationResponse:
    """A line without the telling-back stamp counts as the conversation, so older sessions read."""
    return ConversationResponse(
        session_id=session.id,
        turns=[
            _turn_of(message) for message in session.messages or [] if not message.get("told_back")
        ],
    )


def _turn_of(message: dict[str, Any]) -> ConversationTurn:
    letter = message.get("category") or ""
    fail_safe = message["role"] == "guide" and (
        message.get("outcome") == "fail_safe" or bool(letter)
    )
    return ConversationTurn(
        role=message["role"],
        text=message.get("text", ""),
        at=message.get("at"),
        fail_safe=fail_safe,
        fail_safe_category=_CATEGORY_NAMES.get(letter) if fail_safe else None,
    )
