from __future__ import annotations

import logging

from app.services.internalization_room.bridge_language import strays_from
from app.services.internalization_room.llm import call_agent
from app.services.internalization_room.panorama_turn import run_panorama_turn
from app.services.internalization_room.passage_turn import run_turn
from app.services.internalization_room.peer_cue import detects_peer_cue
from app.services.internalization_room.prompt_blocks import coverage_status_block
from app.services.internalization_room.redraft_note import (
    _DESCRIBED_ISSUES_NOTE,
    _NO_ISSUES_NOTE,
    _OFF_BRIDGE_LANGUAGE_NOTE,
    _redraft_note,
)
from app.services.internalization_room.turn_instructions import (
    OPENING_MOVEMENT_MARK,
    split_opening_movements,
)
from app.services.internalization_room.validated_turn import TurnOutcome
from app.services.internalization_room.verdict_turn import run_verdict_turn

__all__ = [
    "OPENING_MOVEMENT_MARK",
    "_DESCRIBED_ISSUES_NOTE",
    "_NO_ISSUES_NOTE",
    "_OFF_BRIDGE_LANGUAGE_NOTE",
    "TurnOutcome",
    "_redraft_note",
    "call_agent",
    "coverage_status_block",
    "detects_peer_cue",
    "run_panorama_turn",
    "run_turn",
    "run_verdict_turn",
    "split_opening_movements",
    "strays_from",
]

logger = logging.getLogger(__name__)

MAX_REDRAFTS = 2
