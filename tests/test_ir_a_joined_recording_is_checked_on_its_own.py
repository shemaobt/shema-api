"""ENG-1207 — a joined recording is checked on its own, and an untranslated stretch gets N-3.

Her join lays each scene rehearsal into the passage recording as a clip that remembers where it
came from, and only such a recording changes what follows the listen (`ensaioFinal.ts:431-483`
at her freeze): a stretch nobody translated sends the team back to it with her N-3, and a
recording translated through is checked once with no tap, after her N-2. A recording no join
touched checks exactly as before.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSceneRehearsal, IRSession, IRTake, IRTakeKind
from app.services.internalization_room.segments import capture_segment
from app.services.internalization_room.takes import takes_of
from tests.release_harness import PREFIX
from tests.room_harness import (
    REHEARSED_AT,
    TABLET,
    Analyst,
    Room,
    played_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    stored_telling_back,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
)

PART_MS = 4000
UNTRANSLATED_BY_POSITION = "N2"


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


async def _recorded(
    db: AsyncSession,
    frases_by_part: list[list[tuple[int, int]]],
    *,
    joined: bool = True,
    content_type: str = "audio/wav",
) -> tuple[IRSession, list[IRTake]]:
    """A passage recorded in one part per scene, each told back over the spans it names.

    `frases_by_part[i]` are the spans, in the part's own milliseconds, of the translated frases
    on scene i+1; an empty list is a scene nobody translated anything over. `joined` lays each
    part in from that scene's rehearsal, as the join does; without it the team recorded them.
    """
    session, _ = await rehearsed_in_parts(db, 0)
    parts = []
    for index, spans in enumerate(frases_by_part):
        number = index + 1
        rehearsal = await _a_scene_rehearsal(db, session, number) if joined else None
        take = IRTake(
            session_id=session.id,
            project_id=session.project_id,
            device_id=TABLET,
            pericope=session.pericope,
            kind=IRTakeKind.ENSAIO,
            scope=f"parte-{number}",
            ordinal=number,
            storage_key=f"takes/{session.id}/ensaio/{number}",
            size_bytes=2048,
            sha256=chr(ord("a") + index) * 64,
            crc32c="AAAAAAA=",
            content_type=content_type,
            created_at=REHEARSED_AT + timedelta(minutes=index),
            origin=rehearsal.id if rehearsal else None,
        )
        db.add(take)
        await db.commit()
        for starts_ms, ends_ms in spans:
            await capture_segment(
                db,
                session,
                take_id=take.id,
                starts_ms=starts_ms,
                ends_ms=ends_ms,
                bridge_take_id=f"retro-{number}-{starts_ms}",
                transcript=f"a cena {number} contada de volta",
            )
        parts.append(take)
    return session, parts


def _heard(parts: list[IRTake]) -> dict[str, Any]:
    return played_every_part([part.id for part in parts], duration_ms=PART_MS)


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


async def test_terminei_over_a_joined_scene_with_no_frase_is_refused_with_n3_naming_that_scene(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, (first, second, third) = await _recorded(
        db_session, [[(0, PART_MS)], [], [(0, PART_MS)]]
    )

    answered = await press_terminei(client, session.id, report=_heard([first, second, third]))

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] == "STRETCH_UNTRANSLATED", (
        "uma cena juntada sem frase nenhuma ia para a conferência como se estivesse traduzida"
    )
    assert body["fixed_line"] == UNTRANSLATED_BY_POSITION
    assert body["untranslated"] == [{"take_id": second.id, "scene": 2, "from_ms": 0}]
    assert body["checked"] is False
    assert analyst.readings == 0
    assert (await stored_telling_back(db_session, session)).checks == []


async def test_an_unheard_joined_scene_is_refused_as_unheard_before_untranslated(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (first, second) = await _recorded(db_session, [[(0, PART_MS)], []])

    answered = await press_terminei(client, session.id, report=_heard([first]))

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] == "PART_UNHEARD", (
        "ela recusa o que não foi ouvido antes do que falta traduzir"
    )
    assert body["unheard_take_ids"] == [second.id]
    assert body["untranslated"] == []


async def test_a_joined_recording_with_nothing_translated_names_every_scene_still_to_translate(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, (first, second) = await _recorded(db_session, [[], []])

    answered = await press_terminei(client, session.id, report=_heard([first, second]))

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] == "STRETCH_UNTRANSLATED", (
        "numa junção sem tradução nenhuma ela manda às cenas, não diz que não há frase"
    )
    assert body["untranslated"] == [
        {"take_id": first.id, "scene": 1, "from_ms": 0},
        {"take_id": second.id, "scene": 2, "from_ms": 0},
    ]
    assert analyst.readings == 0
