"""ENG-1273 — a scene rehearsal keeps the tablet's recording time, checked against its bytes.

A **Scene rehearsal** is always recorded on the tablet, so the **Recording time** it was sent
with is the one it keeps; its fingerprint and length are checked as a take's are, and refused
when they differ.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSceneRehearsal
from app.utils.stored_time import as_utc
from tests.hard_stretch_harness import a_session
from tests.scene_rehearsal_harness import IR, Room, a_room, count, read_by_b, recording

TEN_OH_TWO = "2026-10-20T10:02:00+00:00"


@pytest.fixture()
async def room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    async with a_room(db_session, rival_factory, monkeypatch) as built:
        yield built


async def send(room: Room, session_id: str, audio: bytes, **fields: object) -> httpx.Response:
    return await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals",
        data={name: str(value) for name, value in fields.items()},
        files={"file": ("cena.wav", audio, "audio/wav")},
    )


async def test_a_scene_rehearsal_recorded_at_10_02_keeps_10_02_as_its_recording_time(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    audio = recording(4, 1)

    kept = await send(
        room,
        session_id,
        audio,
        recorded_at="2026-10-20T10:02:00Z",
        duration_ms=4000,
        sha256=hashlib.sha256(audio).hexdigest(),
    )

    assert kept.status_code == 200, kept.text
    assert kept.json()["recorded_at"] == TEN_OH_TWO
    assert [r["recorded_at"] for r in await read_by_b(room, session_id)] == [TEN_OH_TWO]


async def test_a_scene_rehearsals_fingerprint_not_its_recordings_is_refused_and_nothing_kept(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    refused = await send(
        room, session_id, recording(4, 2), sha256=hashlib.sha256(b"outros bytes").hexdigest()
    )

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "TAKE_FINGERPRINT_DIFFERS"
    assert await count(db_session, "ir_scene_rehearsals", "session_id", session_id) == 0
    assert room.bucket.objects == {}


async def test_a_scene_rehearsal_whose_length_is_not_its_recordings_is_refused_and_nothing_is_kept(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    refused = await send(room, session_id, recording(4, 3), duration_ms=9000)

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "TAKE_DURATION_DIFFERS"
    assert await count(db_session, "ir_scene_rehearsals", "session_id", session_id) == 0
    assert room.bucket.objects == {}


async def test_a_scene_rehearsal_sent_with_no_time_keeps_its_arrival_as_its_recording_time(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    kept = await send(room, session_id, recording(4, 4))

    assert kept.status_code == 200, kept.text
    row = (
        await db_session.execute(
            select(IRSceneRehearsal)
            .where(IRSceneRehearsal.id == kept.json()["rehearsal_id"])
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert datetime.fromisoformat(kept.json()["recorded_at"]) == as_utc(row.created_at)


async def test_a_scene_rehearsals_length_no_recording_can_have_is_refused_and_nothing_kept(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    refused = await send(room, session_id, b"bytes que o ffprobe nao le", duration_ms=2**31)

    assert refused.status_code == 422, refused.text
    assert await count(db_session, "ir_scene_rehearsals", "session_id", session_id) == 0
    assert room.bucket.objects == {}


@pytest.mark.parametrize("edge", ["0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"])
async def test_a_scene_rehearsals_recording_time_with_no_utc_instant_is_refused(
    room: Room, db_session: AsyncSession, edge: str
) -> None:
    session_id = await a_session(db_session)

    refused = await send(room, session_id, recording(4, 5), recorded_at=edge)

    assert refused.status_code == 422, refused.text
    assert "code" not in refused.json()
    assert await count(db_session, "ir_scene_rehearsals", "session_id", session_id) == 0
