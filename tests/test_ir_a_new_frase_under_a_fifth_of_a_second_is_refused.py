from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PauseCannotMove
from app.services.internalization_room.segments import capture_segment, final_segments
from tests.room_harness import rehearsed_in_parts_of


async def test_a_new_frase_under_a_fifth_of_a_second_is_refused_at_the_capture_whatever_the_door(
    db_session: AsyncSession,
) -> None:
    session, parts = await rehearsed_in_parts_of(db_session, [3, 3])

    with pytest.raises(PauseCannotMove) as refused:
        await capture_segment(
            db_session,
            session,
            take_id=parts[0].id,
            starts_ms=3000,
            ends_ms=3100,
            transcript="uma frase curta demais",
        )

    assert refused.value.code == "PAUSE_CANNOT_STAND_THERE"
    assert len(await final_segments(db_session, session.id)) == 6, (
        "uma frase de 100 ms era guardada como frase de pé"
    )
