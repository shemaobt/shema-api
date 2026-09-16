"""The comprehension turn is a sequencer over `turn/`, and every phase answers on its own."""

from __future__ import annotations

from app.services.internalization_room import live_turn
from app.services.internalization_room.turn import scene_view


def test_the_scene_pointer_lives_in_its_own_module_and_live_turn_still_names_it() -> None:
    assert live_turn.current_scene_id is scene_view.current_scene_id
    assert "current_scene_id" in live_turn.__all__
