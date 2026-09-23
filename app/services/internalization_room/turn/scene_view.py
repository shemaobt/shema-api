"""The scene fact the room derives from `coverage_state` before anything is planned."""

from __future__ import annotations

from typing import Any

from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.comprehension.checkpoints import scene_ids_for
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


def scene_the_invitation_is_about(
    scene_pointer: str | None, pericope: str, practiced_scene_ids: list[str]
) -> str | None:
    """The scene the pointer names, or the first scene still owed a rehearsal once it is blank.

    While a scene is still being opened it is that one: the invitation ends the opening
    of the scene the pointer names. Once every bead is engaged there is nothing left to
    open, and an invitation can only be about a rehearsal still owed — the first scene the
    room told the Guide was still needed. Engagement and practice are two facts (ENG-780),
    so a necklace can fill before the rehearsals catch up, and a pointer that only knew
    coverage went blank exactly then, with every telling after it marking nothing.

    One scene per telling. The Guide invites in its own words and may ask for two scenes
    at once; the app cannot read that off its prose, so the second stays on the STILL
    NEEDED line for the Guide to invite again. Marking every scene still needed on one
    telling would be a full necklace closing the passage through a second door.
    """
    if scene_pointer is not None:
        return scene_pointer
    return next((s for s in scene_ids_for(pericope) if s not in practiced_scene_ids), None)
