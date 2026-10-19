from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.segments import final_segments
from tests.release_harness import PREFIX
from tests.room_harness import (
    a_piece_still_to_be_told,
    rehearsed_in_parts,
    room_client,
)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _segments_of_the_read(client: httpx.AsyncClient, session_id: str) -> list[dict]:
    read = await client.get(f"{PREFIX}/sessions/{session_id}")
    assert read.status_code == 200, read.text
    return read.json()["back_translation"]["segments"]


async def test_the_session_read_numbers_four_told_stretches_one_to_four_in_the_voices_order(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 4)
    standing = await final_segments(db_session, session.id)

    segments = await _segments_of_the_read(client, session.id)

    assert [one["segment_id"] for one in segments] == [one.id for one in standing]
    assert [one.get("frase") for one in segments] == [1, 2, 3, 4], (
        "a sala dizia «na frase 3» e a leitura da sessão não numerava nenhum trecho"
    )


async def test_an_untold_piece_has_no_frase_and_takes_no_number_from_the_told_ones(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    standing = await final_segments(db_session, session.id)
    await a_piece_still_to_be_told(db_session, session, standing[1])

    segments = await _segments_of_the_read(client, session.id)

    assert [one["told"] for one in segments] == [True, True, False, True]
    assert [one.get("frase") for one in segments] == [1, 2, None, 3], (
        "a parte por contar ficava sem número, mas a frase seguinte contava com ela"
    )
