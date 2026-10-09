from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.services.internalization_room import llm

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


_current = RoomAgent()


def room_agent() -> RoomAgent:
    return _current
