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

from app.services.internalization_room.segments import current_segments, divide_segment
from tests.release_harness import PREFIX
from tests.room_harness import (
    PART_MS,
    rehearsed_in_parts,
    rehearsed_in_parts_of,
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


async def test_a_stretch_the_team_divided_is_served_as_its_pieces_and_not_as_itself(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (_one, two, _three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row for row in await current_segments(db_session, session.id)}
    head, tail = await divide_segment(db_session, session, by_part[two.id], at_ms=PART_MS // 2)

    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    stale = [row for row in await _read_asking_for_stale(client, session.id) if row["stale"]]

    assert [row["segment_id"] for row in stale] == [head.id, tail.id], (
        "o trecho cortado voltava inteiro, além das duas partes em que a equipe o tinha cortado"
    )


async def test_the_stale_stretches_follow_the_order_of_the_passage_not_the_order_they_went(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (_one, two, three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}

    for part in (3, 2):
        again = await upload_a_part(client, session.id, part=part, audio=NEW_AUDIO + bytes([part]))
        assert again.status_code == 200, again.text

    stale = [row for row in await _read_asking_for_stale(client, session.id) if row["stale"]]

    assert [row["segment_id"] for row in stale] == [by_part[two.id], by_part[three.id]], (
        "as regravadas voltavam na ordem em que foram regravadas, não na ordem da passagem"
    )


async def test_the_stale_stretches_of_a_whole_recording_leave_when_the_team_records_by_scene(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (_whole,) = await rehearsed_in_parts_of(db_session, [3], told_whole=True)
    told = [row.id for row in await current_segments(db_session, session.id)]
    again = await upload_a_part(client, session.id, part=None, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text
    asked = await _read_asking_for_stale(client, session.id)
    assert [row["segment_id"] for row in asked if row["stale"]] == told, (
        "o ensaio inteiro regravado devia continuar listado enquanto ainda é uma parte"
    )

    scene = await upload_a_part(client, session.id, part=1, audio=NEW_AUDIO + b"1")
    assert scene.status_code == 200, scene.text

    assert [
        row for row in await _read_asking_for_stale(client, session.id) if row["stale"]
    ] == [], "o ensaio inteiro já era história quando a equipe passou a gravar por cena"
