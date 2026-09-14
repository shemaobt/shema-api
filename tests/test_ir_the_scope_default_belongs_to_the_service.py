"""The scope a telling-back is stored under is defaulted where the rule lives, not at a door.

Two doors reach the same capture — the tablet's chunks route and the text seam — and both
wrote the same default onto the persisted state before calling it. A default on state that is
written to the database is a business rule, and a rule copied into every caller is a rule that
holds until somebody opens a third door (ADR 0009).
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.hard_stretches import capture_and_note_a_hard_stretch
from tests.room_harness import a_rehearsed_session


@pytest.mark.asyncio
async def test_the_scope_default_is_set_by_the_service_on_the_first_capture(
    db_session: AsyncSession,
) -> None:
    """A state that names no scope comes back naming the session's passage, on either door.

    The two calls differ where the doors differ: the tablet has already stored the bridge
    recording and names it, and the seam has no audio to name at all.
    """
    session, take = await a_rehearsed_session(db_session)

    from_the_chunks_door = BackTranslationState()
    await capture_and_note_a_hard_stretch(
        db_session,
        session,
        take_id=take.id,
        starts_ms=0,
        ends_ms=9000,
        bridge_take_id="retro-1",
        transcript="Noemi mandou Rute voltar.",
        state=from_the_chunks_door,
    )

    assert from_the_chunks_door.scope == session.pericope

    from_the_seam_door = BackTranslationState()
    await capture_and_note_a_hard_stretch(
        db_session,
        session,
        take_id=take.id,
        starts_ms=9000,
        ends_ms=21000,
        bridge_take_id=None,
        transcript="Rute disse que ia junto.",
        state=from_the_seam_door,
    )

    assert from_the_seam_door.scope == session.pericope
