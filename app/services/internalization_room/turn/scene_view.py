"""The scene fact the room derives from `coverage_state` before anything is planned."""

from __future__ import annotations

from typing import Any

from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.hearing import spoken_words_only


def has_substantive_team_history(messages: list[dict[str, Any]]) -> bool:
    return any(
        message.get("role") == "team" and spoken_words_only(message.get("text", ""))
        for message in messages
    )


def current_scene_id(
    coverage_state: dict[str, Any], pericope: str, messages: list[dict[str, Any]]
) -> str | None:
    """The first scene whose own coverage is not fully engaged — once the team has spoken.

    It is what the Guide is opening: the Guide opens the scene the pointer names, and it
    never selects a scene itself. On a session where nobody has said a word there is no
    scene to name: the app declines to assert one rather than tell the Guide the team is in
    Scene 1 before they have opened their mouths.
    """
    if not has_substantive_team_history(messages):
        return None
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
