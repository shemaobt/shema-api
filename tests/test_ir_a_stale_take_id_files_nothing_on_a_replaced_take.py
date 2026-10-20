"""A tablet naming a take that is no longer the part files nothing on it.

The outbox drains whenever the link comes back, so a tablet can send a stretch, or a correction
of one, over a recording the team has since replaced. Every case drives the doors over HTTP the
way the tablet does, and reads the rows the room kept.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRTake, IRTakeKind
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    nothing_is_read_ahead,
    record_the_part_again,
    rehearsed_in_parts_of,
    room_client,
    the_bucket_is_in_memory,
    the_transcriber_says,
)
from tests.sentence_harness import re_record, rehearsed_in_wav, spoken


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    the_transcriber_says(monkeypatch, [])
    nothing_is_read_ahead(monkeypatch)
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _tell(
    client: httpx.AsyncClient, session_id: str, take_id: str, *, starts_ms: int, ends_ms: int
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Device": TABLET},
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("trecho.m4a", b"um trecho contado", "audio/mp4")},
    )


async def _stretch_ids(db: AsyncSession, session_id: str) -> set[str]:
    rows = await db.execute(select(IRSegment.id).where(IRSegment.session_id == session_id))
    return set(rows.scalars().all())


async def _telling_ids(db: AsyncSession, session_id: str) -> set[str]:
    rows = await db.execute(
        select(IRTake.id).where(IRTake.session_id == session_id, IRTake.kind == IRTakeKind.RETRO)
    )
    return set(rows.scalars().all())


async def test_a_chunk_over_the_take_a_part_was_recorded_again_over_files_nothing(
    db_session: AsyncSession, client: httpx.AsyncClient
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])
    replaced_by = await record_the_part_again(db_session, session, part, sha256="b" * 64)
    stretches = await _stretch_ids(db_session, session.id)
    tellings = await _telling_ids(db_session, session.id)

    stale = await _tell(client, session.id, part.id, starts_ms=1000, ends_ms=2000)

    assert stale.status_code == 400, stale.text
    assert stale.json()["code"] == "STRETCH_NO_LONGER_COUNTS"
    assert await _stretch_ids(db_session, session.id) == stretches, (
        "a tomada trocada ganhava um trecho novo, e o ensaio listava a parte velha como se valesse"
    )
    assert await _telling_ids(db_session, session.id) == tellings, (
        "a fala era guardada antes de alguém olhar se a gravação ainda era a parte"
    )

    current = await _tell(client, session.id, replaced_by.id, starts_ms=1000, ends_ms=2000)

    assert current.status_code == 200, current.text
    assert len(await _stretch_ids(db_session, session.id)) == len(stretches) + 1


async def test_a_chunk_over_the_take_a_sentence_was_laid_in_over_files_nothing(
    db_session: AsyncSession, client: httpx.AsyncClient, store: MemoryStore
) -> None:
    session, (part,), ((_, middle, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)]]
    )
    laid = await re_record(client, session.id, middle.id, spoken(1.0))
    assert laid.status_code == 200, laid.text
    laid_in = laid.json()["segments"][0]["take_id"]
    assert laid_in != part.id
    stretches = await _stretch_ids(db_session, session.id)
    tellings = await _telling_ids(db_session, session.id)

    stale = await _tell(client, session.id, part.id, starts_ms=10000, ends_ms=11000)

    assert stale.status_code == 400, stale.text
    assert stale.json()["code"] == "STRETCH_NO_LONGER_COUNTS"
    assert await _stretch_ids(db_session, session.id) == stretches, (
        "a tomada anterior à frase regravada ganhava um trecho, com o mesmo número da parte"
    )
    assert await _telling_ids(db_session, session.id) == tellings

    current = await _tell(client, session.id, laid_in, starts_ms=10000, ends_ms=11000)

    assert current.status_code == 200, current.text
    assert len(await _stretch_ids(db_session, session.id)) == len(stretches) + 1
