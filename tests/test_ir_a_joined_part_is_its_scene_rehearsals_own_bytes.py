"""ENG-1385 — a joined part is its scene rehearsal's own bytes, and the same join twice is one take.

The tablet joins a **Scene rehearsal** by sending its bytes as that scene's **Part**, with the
rehearsal's id as `origin` and the rehearsal's fingerprint as `sha256`. The listing names that
fingerprint; the room keeps exactly those bytes and refuses any others (ADR 0072).
"""

from __future__ import annotations

import hashlib

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.takes import takes_of
from tests.hard_stretch_harness import a_session
from tests.scene_rehearsal_harness import IR, Room, a_room, read_by_b, recording


@pytest.fixture()
async def room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    async with a_room(db_session, rival_factory, monkeypatch) as built:
        monkeypatch.setattr(takes_service, "_store", lambda *_, **__: built.bucket)
        yield built


async def _joined(
    client: httpx.AsyncClient,
    session_id: str,
    *,
    part: int,
    origin: str,
    sha256: str,
    audio: bytes,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return await client.post(
        f"{IR}/sessions/{session_id}/takes",
        headers=headers,
        data={
            "kind": "ensaio",
            "scope": f"parte-{part}",
            "chunk_index": str(part),
            "origin": origin,
            "sha256": sha256,
        },
        files={"file": ("cena.wav", audio, "audio/wav")},
    )


async def _rehearsed(room: Room, session_id: str, audio: bytes) -> tuple[str, str]:
    kept = await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals",
        data={"scene": "S2"},
        files={"file": ("cena.wav", audio, "audio/wav")},
    )
    assert kept.status_code == 200, kept.text
    (listed,) = await read_by_b(room, session_id)
    assert kept.json()["sha256"] == listed["sha256"]
    return str(listed["rehearsal_id"]), str(listed["sha256"])


async def test_the_listing_names_each_scene_rehearsals_fingerprint(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    audio = recording(4, 7)

    kept = await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals",
        data={"scene": "S2"},
        files={"file": ("cena.wav", audio, "audio/wav")},
    )

    expected = hashlib.sha256(audio).hexdigest()
    assert kept.json()["sha256"] == expected, "a resposta do envio não nomeava a impressão digital"
    assert [r["sha256"] for r in await read_by_b(room, session_id)] == [expected], (
        "a listagem não deixava o tablet que não gravou saber a impressão digital do ensaio"
    )


async def test_a_part_joined_under_the_rehearsals_fingerprint_is_kept_as_those_bytes(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    audio = recording(4, 8)
    rehearsal_id, fingerprint = await _rehearsed(room, session_id, audio)

    joined = await _joined(
        room.client,
        session_id,
        part=2,
        origin=rehearsal_id,
        sha256=fingerprint,
        audio=audio,
        headers=room.tablet_b,
    )

    assert joined.status_code == 200, joined.text
    (part,) = await takes_of(db_session, session_id)
    assert (part.ordinal, part.origin, part.sha256) == (2, rehearsal_id, fingerprint)
    assert list(room.bucket.objects.values()).count(audio) >= 1, (
        "a parte não eram os bytes do ensaio"
    )


async def test_bytes_that_are_not_the_rehearsals_fingerprint_are_refused_and_nothing_is_kept(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id, fingerprint = await _rehearsed(room, session_id, recording(4, 9))
    stored_before = dict(room.bucket.objects)

    refused = await _joined(
        room.client,
        session_id,
        part=2,
        origin=rehearsal_id,
        sha256=fingerprint,
        audio=recording(4, 10),
    )

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "TAKE_FINGERPRINT_DIFFERS"
    assert await takes_of(db_session, session_id) == []
    assert room.bucket.objects == stored_before, "bytes de outro som entraram como a parte"


async def test_the_same_rehearsal_joined_from_two_tablets_is_one_take(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    audio = recording(4, 11)
    rehearsal_id, fingerprint = await _rehearsed(room, session_id, audio)

    first = await _joined(
        room.client, session_id, part=2, origin=rehearsal_id, sha256=fingerprint, audio=audio
    )
    second = await _joined(
        room.client,
        session_id,
        part=2,
        origin=rehearsal_id,
        sha256=fingerprint,
        audio=audio,
        headers=room.tablet_b,
    )

    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert first.json()["take_id"] == second.json()["take_id"]
    assert len(await takes_of(db_session, session_id)) == 1, "a mesma junção virou duas gravações"
