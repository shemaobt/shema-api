"""ENG-1739 — a re-recorded part's stretches stay served, marked stale, for the tablet that asks.

Recording a **Part** again retires its stretches (ADR 0023), so the tablet lost them from its
list and had nothing to show the team in their place. Her app keeps them listed, marked, and
out of the check. The room still retires them — the check, the gate and the findings read the
standing stretches and nothing else — and serves them on top, only when the tablet asks.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.segments import current_segments
from tests.release_harness import PREFIX
from tests.room_harness import (
    rehearsed_in_parts,
    room_client,
    the_bucket_is_in_memory,
    upload_a_part,
)

NEW_AUDIO = b"a equipe gravou esta parte outra vez"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _read_asking_for_stale(client: httpx.AsyncClient, session_id: str) -> list[dict]:
    read = await client.get(f"{PREFIX}/sessions/{session_id}", params={"include_stale": "true"})
    assert read.status_code == 200, read.text
    return read.json()["back_translation"]["segments"]


async def test_a_part_recorded_again_keeps_its_earlier_stretch_listed_stale_for_a_tablet_that_asks(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}

    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    segments = await _read_asking_for_stale(client, session.id)

    assert [(row["segment_id"], row["stale"]) for row in segments] == [
        (by_part[one.id], False),
        (by_part[three.id], False),
        (by_part[two.id], True),
    ], "a parte regravada sumia da lista da tablet em vez de ficar marcada como regravada"
