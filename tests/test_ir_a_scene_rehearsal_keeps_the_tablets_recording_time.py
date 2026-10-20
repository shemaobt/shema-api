"""ENG-1273 — a scene rehearsal keeps the tablet's recording time, checked against its bytes.

A **Scene rehearsal** is always recorded on the tablet, so the **Recording time** it was sent
with is the one it keeps; its fingerprint and length are checked as a take's are, and refused
when they differ.
"""

from __future__ import annotations

import hashlib

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
