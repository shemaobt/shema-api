"""ENG-1379 — her runner's turns read the KEPT REHEARSALS note as the tablet's do.

Her golden scripts that reach the send-off are played through the Golden doors, so the note
reaches the voice there once every scene of the passage has a kept take.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import internalization_room as room_service
from tests.golden_rehearsal_harness import a_golden_client, after_the_break, an_open_session
from tests.text_seam_harness import GOLDEN, the_models_answer

KEPT = (
    "KEPT REHEARSALS: the team's own passing retellings of every part of this passage are "
    "saved. Small numbered buttons on their screen replay each part in the team's own voice. "
    "Before the send-off you may offer this once, warmly: if a part has gone cold, they can "
    "tap its number and hear their own telling of it again. Never require it. These kept "
    "takes are practice audio for listening only."
)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with a_golden_client(db_session, monkeypatch) as c:
        yield c


async def test_a_golden_turn_with_every_scene_kept_reads_the_note(
    client: httpx.AsyncClient, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client, "P02")
    stored = await room_service.get_session(db_session, session_id)
    stored.retellings = {
        str(n): {
            "scope": scope,
            "approved": True,
            "kept": {"storage_key": f"takes/{scope}.m4a", "content_type": "audio/m4a"},
        }
        for n, scope in enumerate(("S1", "S2", "S3"), start=1)
    }
    await db_session.commit()
    agent = the_models_answer(monkeypatch)

    typed = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": "Vamos continuar."}
    )

    assert typed.status_code == 200, typed.text
    assert KEPT in after_the_break(agent.guide_systems[-1]), (
        "o turno dourado com as três cenas guardadas não lia a nota dos ensaios guardados"
    )
