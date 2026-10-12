"""ENG-1303 — the packet stops carrying the room's reading of practice and probes.

The packet read the session's comprehension column into a `comprehension` block — the
readiness the room computed from practice credits, the practised scenes, the evidence
ledger and its open points — and counted every open point among the open questions. Nothing
writes that column any more, so a new packet would have said `needs_more_work` beside
`ready_for_refine` for every passage. A row that still holds that history releases as any
other, and its history stays on the row.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.release import build_internalization_release
from tests.release_harness import ready_session

LEGACY = {
    "ledger": [
        {
            "kind": "evidence",
            "id": "ev-0",
            "unit_id": "proposition:P03:P1",
            "probe_id": "probe-0",
            "method": "micro_tellback",
            "result": "carry_to_refine",
            "respondent_slot": None,
            "note": None,
        }
    ],
    "active_probe": {
        "id": "probe-1",
        "checkpoint_ids": ["proposition:P03:P1"],
        "method": "micro_tellback",
        "purpose": "initial_check",
        "practice_scene_ids": [],
    },
    "practiced_scene_ids": ["S1"],
    "invited_scene_id": "S2",
}


async def test_a_row_holding_the_old_practice_and_probe_releases_with_no_comprehension_block(
    db_session: AsyncSession,
) -> None:
    session = await ready_session(db_session)
    session.comprehension = LEGACY
    await db_session.commit()

    artifact = await build_internalization_release(db_session, session)

    assert "comprehension" not in artifact, (
        "o pacote ainda levava a leitura de ensaio e sondas que a sala não faz mais"
    )
    assert artifact["schema_version"] == "tripod.internalization-release.v0.7"
    assert artifact["open_questions"] == 0, (
        "um ponto antigo do registro de compreensão ainda contava como pergunta em aberto"
    )
    assert session.comprehension == LEGACY
