"""ENG-1207 — a joined recording is checked on its own, and an untranslated stretch gets N-3.

Her join lays each scene rehearsal into the passage recording as a clip that remembers where it
came from, and only such a recording changes what follows the listen (`ensaioFinal.ts:431-483`
at her freeze): a stretch nobody translated sends the team back to it with her N-3, and a
recording translated through is checked once with no tap, after her N-2. A recording no join
touched checks exactly as before.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSceneRehearsal, IRSession
from app.services.internalization_room.takes import takes_of
from tests.release_harness import PREFIX
from tests.room_harness import (
    TABLET,
    Analyst,
    Room,
    rehearsed_in_parts,
    room_client,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
)


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    return the_analyst_reads(monkeypatch)


@pytest.fixture(autouse=True)
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _a_scene_rehearsal(db: AsyncSession, session: IRSession, n: int) -> IRSceneRehearsal:
    rehearsal = IRSceneRehearsal(
        session_id=session.id,
        project_id=session.project_id,
        pericope=session.pericope,
        n=n,
        device_id=TABLET,
        storage_key=f"scene-rehearsals/{session.id}/{n}",
        size_bytes=2048,
        sha256=chr(ord("p") + n) * 64,
        crc32c="AAAAAAA=",
        content_type="audio/wav",
        duration_ms=4000,
        scene=f"S{n}",
    )
    db.add(rehearsal)
    await db.commit()
    return rehearsal


async def _joined_upload(
    client: httpx.AsyncClient, session_id: str, *, part: int, origin: str
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Device": TABLET},
        data={
            "kind": "ensaio",
            "scope": f"parte-{part}",
            "chunk_index": str(part),
            "origin": origin,
        },
        files={"file": ("cena.wav", f"cena {part}".encode(), "audio/wav")},
    )


async def test_a_part_joined_from_a_scene_rehearsal_keeps_where_it_came_from(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    rehearsal = await _a_scene_rehearsal(db_session, session, 1)

    answered = await _joined_upload(client, session.id, part=1, origin=rehearsal.id)

    assert answered.status_code == 200, answered.text
    (take,) = await takes_of(db_session, session.id)
    assert take.origin == rehearsal.id, "a parte juntada esquecia de que ensaio veio"


async def test_an_origin_that_names_no_scene_rehearsal_of_the_passage_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)

    answered = await _joined_upload(client, session.id, part=1, origin="ensaio-que-nao-existe")

    assert answered.status_code == 422, answered.text
    assert await takes_of(db_session, session.id) == [], (
        "uma origem inventada fazia da gravação uma junção que nunca houve"
    )
