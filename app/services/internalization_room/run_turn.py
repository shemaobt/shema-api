"""What the rest of the room still calls the turn, and what the fakes are installed on.

The turn itself moved out — `passage_turn`, `panorama_turn`, `verdict_turn` and the engine
under them — and this file imports all of it back, so not one import line anywhere else had
to change. The names are not free to follow it: twenty-seven sites across thirteen test files
install their fake model by writing over `call_agent` on this module, one writes over
`strays_from`, and `tests/test_internalization_room_model_failure.py` asserts on records whose
`record.name` is exactly this module's. `validated_turn` reads those four off here at call
time for the same reason, and `__all__` is what stops ruff removing the imports that are the
whole point of the file.
"""

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
