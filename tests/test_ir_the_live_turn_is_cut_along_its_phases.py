"""The comprehension turn is a sequencer over `turn/`, and every phase answers on its own."""

from __future__ import annotations

import dataclasses

import pytest

from app.services.internalization_room import live_turn
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.turn import scene_view
from app.services.internalization_room.turn.context import render_context
from tests.turn_harness import P


def test_the_scene_pointer_lives_in_its_own_module_and_live_turn_still_names_it() -> None:
    assert live_turn.current_scene_id is scene_view.current_scene_id
    assert "current_scene_id" in live_turn.__all__


def test_the_context_phase_hands_the_models_the_status_block_and_nothing_can_rewrite_it() -> None:
    checkpoints = list(checkpoints_for(P, load_map(P).book))
    context = render_context(
        checkpoints=checkpoints,
        scene_ids=scene_ids_for(P),
        state=ComprehensionState(),
        projected_practice=["S1"],
        scene_pointer="S2",
    )

    assert context.app_context.startswith("COMPREHENSION EVIDENCE (APP-OWNED;")
    assert "MOTHER-TONGUE PRACTICE REPORTED: S1" in context.app_context.splitlines()
    with pytest.raises(dataclasses.FrozenInstanceError):
        context.app_context = ""  # type: ignore[misc]
