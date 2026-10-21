"""ENG-1739 — a re-recorded part's stretches stay served, marked stale, for the tablet that asks.

Recording a **Part** again retires its stretches (ADR 0023), so the tablet lost them from its
list and had nothing to show the team in their place. Her app keeps them listed, marked, and
out of the check. The room still retires them — the check, the gate and the findings read the
standing stretches and nothing else — and serves them on top, only when the tablet asks.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment
from app.services.internalization_room.segments import current_segments, divide_segment
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    PART_MS,
    rehearsed_in_parts,
    rehearsed_in_parts_of,
    room_client,
    the_bucket_is_in_memory,
    the_room_speaks,
    upload_a_part,
)

NEW_AUDIO = b"a equipe gravou esta parte outra vez"
RETELLING = b"a equipe contou a parte regravada"


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from app.api.internalization_room import segments as segments_api

    the_bucket_is_in_memory(monkeypatch)

    async def _heard(*_: Any, **__: Any) -> str:
        return "a parte contada de novo"

    monkeypatch.setattr(segments_api, "heard", _heard)
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _tell_again(
    client: httpx.AsyncClient,
    session_id: str,
    segment_id: str,
    *,
    take_id: str,
    starts_ms: int = 0,
    ends_ms: int = PART_MS,
    params: dict[str, str] | None = None,
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment_id}/replace",
        headers={"X-Room-Device": TABLET},
        params=params,
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("de-novo.m4a", RETELLING, "audio/mp4")},
    )


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


async def test_a_translation_started_over_leaves_no_stale_stretch_to_serve(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text
    assert [row for row in await _read_asking_for_stale(client, session.id) if row["stale"]]

    restarted = await client.post(f"{PREFIX}/sessions/{session.id}/back-translation/restart")
    assert restarted.status_code == 200, restarted.text

    assert await _read_asking_for_stale(client, session.id) == [], (
        "a tradução recomeçada continuava listando a parte regravada antes do recomeço"
    )


async def test_telling_a_stale_stretch_again_replaces_it_and_the_marker_goes(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    told = await _tell_again(client, session.id, by_part[two.id], take_id=again.json()["take_id"])

    assert told.status_code == 200, told.text
    standing = await _read_asking_for_stale(client, session.id)
    assert [(row["take_id"], row["stale"], row["frase"]) for row in standing] == [
        (one.id, False, 1),
        (again.json()["take_id"], False, 2),
        (three.id, False, 3),
    ], "a parte contada de novo continuava marcada como regravada, ou não ocupava o seu lugar"
    old = (
        await db_session.execute(
            select(IRSegment)
            .where(IRSegment.id == by_part[two.id])
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert old.superseded_by_id == standing[1]["segment_id"], (
        "a linha antiga não dizia o que tomou o seu lugar"
    )
