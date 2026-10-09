"""ENG-1457 — a **Panorama** session records nothing, and every door that would says so.

The panorama is spoken before the first passage; nothing in it is rehearsed, told back or
checked. Her app already answers each of these doors for a panorama with a 400, so the server
refuses the same way, with one code the tablet tells apart from any other 400 without reading
words. The release doors are not among the doors refused: ENG-954 settled their answers.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sessions import create_session
from app.services.internalization_room.takes import declare_rehearsal_parts
from tests.device_harness import TABLET_TEAM
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    another_rehearsal_take,
    nothing_is_read_ahead,
    press_terminei,
    room_client,
    stored_telling_back,
    tell_back_about,
    the_bucket_is_in_memory,
    the_transcriber_says,
    upload_a_part,
)
from tests.text_seam_harness import RUNNER_KEY

CODE = "PANORAMA_RECORDS_NOTHING"
HEADERS = {"X-Room-Device": TABLET}
SEAM = f"{PREFIX}/text-seam/back-translation"
CLIPS = [{"key": "S1", "durationMs": 20000}]


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch, runner_key=RUNNER_KEY) as door:
        yield door


@pytest.fixture()
def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    from app.api.internalization_room import segments as segments_api

    async def heard(*_: Any, **__: Any) -> str:
        return "algo que a equipe contou"

    nothing_is_read_ahead(monkeypatch)
    the_transcriber_says(monkeypatch, [])
    monkeypatch.setattr(segments_api, "heard", heard)
    return the_bucket_is_in_memory(monkeypatch)


async def _a_panorama(db: AsyncSession) -> IRSession:
    return await create_session(db, project_id=TABLET_TEAM, pericope="OV-Ruth", language="pt")


async def _a_panorama_with_a_told_stretch(db: AsyncSession) -> tuple[IRSession, IRTake, IRSegment]:
    session = await _a_panorama(db)
    take = await another_rehearsal_take(db, session, sha256="a" * 64)
    stretch = await tell_back_about(db, session, take)
    return session, take, stretch


async def _count(db: AsyncSession, model: type, **where: str) -> int:
    query = select(func.count()).select_from(model)
    for column, value in where.items():
        query = query.where(getattr(model, column) == value)
    return int((await db.execute(query)).scalar_one())


def _refused(response: httpx.Response) -> None:
    assert response.status_code == 400, response.text
    assert response.json()["code"] == CODE, response.text


async def test_a_take_sent_under_a_panorama_is_refused_and_nothing_is_stored(
    client: httpx.AsyncClient, db_session: AsyncSession, bucket: MemoryStore
) -> None:
    session = await _a_panorama(db_session)

    refused = await upload_a_part(client, session.id, part=None, audio=b"a equipe ensaiou")

    _refused(refused)
    assert await _count(db_session, IRTake, session_id=session.id) == 0
    assert bucket.objects == {}


async def test_a_chunk_sent_under_a_panorama_is_refused_and_nothing_is_stored(
    client: httpx.AsyncClient, db_session: AsyncSession, bucket: MemoryStore
) -> None:
    session, take, _ = await _a_panorama_with_a_told_stretch(db_session)

    refused = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/chunks",
        headers=HEADERS,
        data={"take_id": take.id, "starts_ms": "0", "ends_ms": "9000"},
        files={"file": ("trecho.m4a", b"a equipe explicou", "audio/mp4")},
    )

    _refused(refused)
    assert await _count(db_session, IRTake, session_id=session.id) == 1
    assert await _count(db_session, IRSegment, session_id=session.id) == 1
    assert bucket.objects == {}


async def test_pressing_terminei_under_a_panorama_is_refused_and_saves_no_playback_report(
    client: httpx.AsyncClient, db_session: AsyncSession, bucket: MemoryStore
) -> None:
    session = await _a_panorama(db_session)
    before = await stored_telling_back(db_session, session)

    refused = await press_terminei(
        client,
        session.id,
        report={"played_ranges": [[0, 9000]], "clip_duration_ms": 9000},
    )

    _refused(refused)
    assert await stored_telling_back(db_session, session) == before


async def test_dividing_a_stretch_under_a_panorama_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession, bucket: MemoryStore
) -> None:
    session, _, stretch = await _a_panorama_with_a_told_stretch(db_session)
    before = [one.id for one in await final_segments(db_session, session.id)]

    refused = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{stretch.id}/divide",
        headers=HEADERS,
        json={"at_ms": 30000},
    )

    _refused(refused)
    assert [one.id for one in await final_segments(db_session, session.id)] == before


async def test_a_correction_sent_under_a_panorama_is_refused_and_nothing_is_stored(
    client: httpx.AsyncClient, db_session: AsyncSession, bucket: MemoryStore
) -> None:
    session, take, stretch = await _a_panorama_with_a_told_stretch(db_session)
    before = [one.id for one in await final_segments(db_session, session.id)]

    refused = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{stretch.id}/replace",
        headers=HEADERS,
        data={"take_id": take.id, "starts_ms": "0", "ends_ms": "61000"},
        files={"file": ("trecho.m4a", b"a equipe disse de novo", "audio/mp4")},
    )

    _refused(refused)
    assert [one.id for one in await final_segments(db_session, session.id)] == before
    assert await _count(db_session, IRTake, session_id=session.id) == 1
    assert bucket.objects == {}


async def test_the_text_seam_will_not_open_a_back_translation_session_over_a_panorama(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    refused = await client.post(
        f"{SEAM}/session",
        json={"pericopeId": "OV", "language": "Brazilian Portuguese", "clips": CLIPS},
    )

    _refused(refused)
    assert await _count(db_session, IRSession) == 0


async def test_a_text_seam_round_on_a_panorama_session_is_refused_and_captures_no_stretch(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session = await _a_panorama(db_session)
    await declare_rehearsal_parts(db_session, session, ["S1"])

    refused = await client.post(
        f"{SEAM}/round",
        json={
            "sessionId": session.id,
            "frases": [{"clipKey": "S1", "coversFrom": 0, "coversTo": 10, "text": "Noemi voltou"}],
        },
    )

    _refused(refused)
    assert await _count(db_session, IRSegment, session_id=session.id) == 0


async def test_a_passage_sessions_take_is_still_kept(
    client: httpx.AsyncClient, db_session: AsyncSession, bucket: MemoryStore
) -> None:
    session = await create_session(
        db_session, project_id=TABLET_TEAM, pericope="P03", language="pt"
    )

    kept = await upload_a_part(client, session.id, part=None, audio=b"a equipe ensaiou")

    assert kept.status_code == 200, kept.text
    assert await _count(db_session, IRTake, session_id=session.id) == 1
