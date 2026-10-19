from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from app.services.internalization_room.segments import final_segments
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    PART_MS,
    a_piece_still_to_be_told,
    nothing_is_read_ahead,
    rehearsed_in_parts,
    room_client,
    the_bucket_is_in_memory,
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


async def test_dividing_a_stretch_answers_with_the_numbers_the_next_read_serves(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    standing = await final_segments(db_session, session.id)

    divided = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{standing[1].id}/divide",
        headers={"X-Room-Device": TABLET},
        json={"at_ms": PART_MS // 2},
    )

    assert divided.status_code == 200, divided.text
    answered = divided.json()["segments"]
    assert [one.get("frase") for one in answered] == [1, None, None, 2], (
        "o corte devolvia a lista sem números e a tela se renumerava sozinha"
    )
    assert answered == await _segments_of_the_read(client, session.id)


async def test_a_stretch_told_again_answers_with_the_number_it_already_had(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_bucket_is_in_memory(monkeypatch)
    nothing_is_read_ahead(monkeypatch)

    async def heard(*_: object, **__: object) -> str:
        return "Rute disse que iria aonde Noemi fosse."

    monkeypatch.setattr(segments_api, "heard", heard)
    session, _parts = await rehearsed_in_parts(db_session, 4)
    standing = await final_segments(db_session, session.id)

    replaced = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{standing[1].id}/replace",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": standing[1].take_id,
            "starts_ms": str(standing[1].starts_ms),
            "ends_ms": str(standing[1].ends_ms),
        },
        files={"file": ("de-novo.m4a", b"a frase dois traduzida de novo", "audio/mp4")},
    )

    assert replaced.status_code == 200, replaced.text
    answered = replaced.json()["segments"]
    assert [one.get("frase") for one in answered] == [1, 2, 3, 4], (
        "a frase traduzida de novo perdia o número e arrastava as seguintes"
    )
    assert answered == await _segments_of_the_read(client, session.id)
