"""ENG-1383 — a scene rehearsal that is a current part's origin keeps its scene label.

Her route refuses to relabel a scene's clip that sits in the passage recording right now
(`app/api/rehearsal/scene/route.ts:16-21`), and stays a no-op for the same scene. Here the clip is
the **Part** whose `origin` names the **Scene rehearsal**; recording that part again frees the
label. Said at the recording holds only while the label is the one given then.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.hard_stretch_harness import a_session
from tests.scene_rehearsal_harness import (
    IR,
    Room,
    a_room,
    read_by_b,
    recorded,
    sent,
    translated,
)

TABLET_DEVICE = {"X-Room-Device": "tablet-da-sala"}


@pytest.fixture()
async def room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    from app.services.internalization_room import takes as takes_service

    async with a_room(db_session, rival_factory, monkeypatch) as built:
        monkeypatch.setattr(takes_service, "_store", lambda settings=None: built.bucket)
        yield built


async def label(room: Room, session_id: str, rehearsal_id: str, scene: str) -> httpx.Response:
    return await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/scene",
        data={"scene": scene},
    )


async def the_record(room: Room, session_id: str, rehearsal_id: str) -> dict[str, Any]:
    (found,) = [r for r in await read_by_b(room, session_id) if r["rehearsal_id"] == rehearsal_id]
    return found


async def part_2(
    room: Room,
    session_id: str,
    *,
    origin: str | None,
    audio: bytes,
    pass_number: int | None = None,
    recorded_at: datetime | None = None,
) -> httpx.Response:
    data = {"kind": "ensaio", "scope": "parte-2", "chunk_index": "2"}
    if origin is not None:
        data["origin"] = origin
    if pass_number is not None:
        data["pass_number"] = str(pass_number)
    if recorded_at is not None:
        data["recorded_at"] = recorded_at.isoformat()
    return await room.client.post(
        f"{IR}/sessions/{session_id}/takes",
        headers=TABLET_DEVICE,
        data=data,
        files={"file": ("cena.wav", audio, "audio/wav")},
    )


async def a_joined_rehearsal(room: Room, db: AsyncSession) -> tuple[str, str]:
    session_id = await a_session(db)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000)])
    await sent(db, rehearsal_id)
    joined = await part_2(room, session_id, origin=rehearsal_id, audio=b"cena 2")
    assert joined.status_code == 200, joined.text
    return session_id, rehearsal_id


async def test_a_joined_rehearsal_given_another_scene_is_refused_and_keeps_its_label(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, rehearsal_id = await a_joined_rehearsal(room, db_session)
    before = await the_record(room, session_id, rehearsal_id)

    refused = await label(room, session_id, rehearsal_id, "S3")

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "REHEARSAL_JOINED"
    assert (before["scene"], before["scene_said"]) == ("S2", "recording")
    assert await the_record(room, session_id, rehearsal_id) == before


async def test_the_same_label_on_a_joined_rehearsal_changes_nothing(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, rehearsal_id = await a_joined_rehearsal(room, db_session)
    before = await the_record(room, session_id, rehearsal_id)

    same = await label(room, session_id, rehearsal_id, "S2")

    assert same.status_code == 200, same.text
    assert await the_record(room, session_id, rehearsal_id) == before


async def test_a_rehearsal_whose_part_was_recorded_again_takes_another_scene_said_later(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, rehearsal_id = await a_joined_rehearsal(room, db_session)
    again = await part_2(
        room,
        session_id,
        origin=None,
        audio=b"cena 2 outra vez",
        pass_number=2,
        recorded_at=datetime.now(UTC),
    )
    assert again.status_code == 200, again.text

    moved = await label(room, session_id, rehearsal_id, "S3")

    assert moved.status_code == 200, moved.text
    after = await the_record(room, session_id, rehearsal_id)
    assert (after["scene"], after["scene_said"]) == ("S3", "later")


async def test_a_label_given_at_the_recording_changed_and_given_back_reads_said_later(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await sent(db_session, rehearsal_id)

    assert (await label(room, session_id, rehearsal_id, "S3")).status_code == 200
    assert (await label(room, session_id, rehearsal_id, "S2")).status_code == 200

    back = await the_record(room, session_id, rehearsal_id)
    assert (back["scene"], back["scene_said"]) == ("S2", "later")


async def test_an_unknown_scene_on_a_joined_rehearsal_is_refused_as_unknown(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, rehearsal_id = await a_joined_rehearsal(room, db_session)

    refused = await label(room, session_id, rehearsal_id, "S99")

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "UNKNOWN_SCENE"
