from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.services.internalization_room import llm
from app.services.internalization_room.bridge_language import strays_from

CallAgent = Callable[..., Awaitable[str]]


@dataclass(frozen=True)
class Agent:
    call_agent: CallAgent = llm.call_agent


@dataclass(frozen=True)
class RoomAgent:
    turn: Agent = field(default_factory=Agent)
    analyst: Agent = field(default_factory=Agent)
    classifier: Agent = field(default_factory=Agent)
    judge: Agent = field(default_factory=Agent)
    strays_from: Callable[[str, str], bool] = strays_from


_current = RoomAgent()


def room_agent() -> RoomAgent:
    return _current
