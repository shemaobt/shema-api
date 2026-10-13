"""ENG-1303 — a passage is done at the coverage floor, whatever the room read about rehearsing.

Her room calls a passage done when every element has the status its kind needs, and reads
neither practice, a report nor the team's words. Ours also waited until every scene had been
credited as practised, a credit a regex gave when the voice's line looked like an invitation
and the team's next words looked like a report, so a team that worked the whole map but never
said «pronto» after an invitation was never done.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSessionStatus
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.sessions import (
    apply_coverage,
    create_session,
    session_is_done,
)

P = "P03"


async def test_a_passage_the_team_worked_whole_is_done_with_no_scene_ever_reported_practised(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    settled = await apply_coverage(
        db_session, session.id, dict.fromkeys(element_keys(P), "engaged")
    )

    assert session_is_done(settled), (
        "a passagem com o mapa inteiro trabalhado esperava cada cena ser dada como ensaiada"
    )
    assert settled.status is IRSessionStatus.DONE
    assert settled.ended_at is not None
