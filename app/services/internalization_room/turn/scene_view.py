"""The scene fact the room derives from `coverage_state` before anything is planned."""

from __future__ import annotations

from typing import Any

from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.coverage import CoverageStatus


def current_scene_id(coverage_state: dict[str, Any], pericope: str) -> str | None:
    """The first scene whose own coverage is not fully engaged.

    It is what the rehearsal the Guide invites is read against: the Guide opens the scene
    the pointer names, and it never selects a scene itself.
    """
    by_scene: dict[int, bool] = {}
    for element in elements_for(pericope):
        if element.scene is None:
            continue
        engaged = coverage_state.get(element.key) == CoverageStatus.ENGAGED.value
        by_scene[element.scene] = by_scene.get(element.scene, True) and engaged
    for scene in sorted(by_scene):
        if not by_scene[scene]:
            return f"S{scene}"
    return None
