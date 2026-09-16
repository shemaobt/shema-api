"""The rendered block the two models read, joined the way the sequencer used to join it."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.internalization_room.comprehension.checkpoints import Checkpoint
from app.services.internalization_room.comprehension.session_readiness import (
    render_comprehension_status,
)
from app.services.internalization_room.comprehension.state import ComprehensionState


@dataclass(frozen=True)
class RenderedContext:
    app_context: str


def render_context(
    *,
    checkpoints: list[Checkpoint],
    scene_ids: list[str],
    state: ComprehensionState,
    projected_practice: list[str],
    scene_pointer: str | None,
) -> RenderedContext:
    comprehension_status = render_comprehension_status(
        checkpoints=checkpoints,
        scene_ids=scene_ids,
        ledger=state.ledger,
        practiced_scene_ids=projected_practice,
        current_scene=scene_pointer,
    )

    app_context = comprehension_status
    return RenderedContext(app_context=app_context)
