"""The scope a telling-back is stored under is defaulted where the rule lives, not at a door.

Two doors reach the same capture — the tablet's chunks route and the text seam — and both
wrote the same default onto the persisted state before calling it. A default on state that is
written to the database is a business rule, and a rule copied into every caller is a rule that
holds until somebody opens a third door (ADR 0009).

Read back from the row and never off the state the case handed in: the claim is about what is
stored, and an object the test is still holding would answer for the service even if nothing
ever reached the column.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.hard_stretches import capture_and_note_a_hard_stretch
from tests.room_harness import a_rehearsed_session


async def _scope_in_the_row(db: AsyncSession, session_id: str) -> str:
    stored = await db.execute(
        select(IRSession)
        .where(IRSession.id == session_id)
        .execution_options(populate_existing=True)
    )
    return str((stored.scalar_one().back_translation or {}).get("scope", ""))


@pytest.mark.asyncio
async def test_the_scope_default_is_set_by_the_service_on_the_first_capture(
    db_session: AsyncSession,
) -> None:
    """A state that names no scope is stored naming the session's passage, on either door.

    The two calls differ where the doors differ: the tablet has already stored the bridge
    recording and names it, and the seam has no audio to name at all.
    """
    session, take = await a_rehearsed_session(db_session)

    await capture_and_note_a_hard_stretch(
        db_session,
        session,
        take_id=take.id,
        starts_ms=0,
        ends_ms=9000,
        bridge_take_id="retro-1",
        transcript="Noemi mandou Rute voltar.",
        state=BackTranslationState(),
    )

    assert await _scope_in_the_row(db_session, session.id) == session.pericope

    await capture_and_note_a_hard_stretch(
        db_session,
        session,
        take_id=take.id,
        starts_ms=9000,
        ends_ms=21000,
        bridge_take_id=None,
        transcript="Rute disse que ia junto.",
        state=BackTranslationState(),
    )

    assert await _scope_in_the_row(db_session, session.id) == session.pericope
