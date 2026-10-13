from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PauseCannotMove
from app.db.models.internalization_room import (
    IRRelease,
    IRSegment,
    IRSession,
    IRTake,
    IRTakeKind,
)
from app.models.internalization_room import PlayedTake
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import back_translation_of, save_back_translation
from tests.release_harness import PREFIX
from tests.room_harness import (
    nothing_is_read_ahead,
    rehearsed_in_parts_of,
    room_client,
    the_bucket_is_in_memory,
)

PART_LENGTH_MS = 5000


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    nothing_is_read_ahead(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.fixture()
def transcribed(monkeypatch: pytest.MonkeyPatch) -> list[bytes]:
    from app.api.internalization_room import segments as segments_api

    asked: list[bytes] = []

    async def transcribe(audio: bytes, **_: Any) -> str:
        asked.append(audio)
        return "a frase contada de novo, até a pausa nova"

    monkeypatch.setattr(segments_api, "heard", transcribe)
    return asked


async def _rehearsed(
    db: AsyncSession, *, content_type: str = "audio/wav"
) -> tuple[IRSession, list[IRTake]]:
    session, parts = await rehearsed_in_parts_of(db, [3, 3])
    for part in parts:
        part.content_type = content_type
    await db.commit()
    state = back_translation_of(session)
    state.played_by_take = [
        PlayedTake(
            take_id=part.id, played_ranges=[(0, PART_LENGTH_MS)], clip_duration_ms=PART_LENGTH_MS
        )
        for part in parts
    ]
    await save_back_translation(db, session, state)
    return session, parts


async def _retro_takes(db: AsyncSession, session_id: str) -> list[IRTake]:
    kept = await db.execute(
        select(IRTake).where(IRTake.session_id == session_id, IRTake.kind == IRTakeKind.RETRO)
    )
    return list(kept.scalars().all())


async def _move(
    client: httpx.AsyncClient, session_id: str, stretch: IRSegment, *, ends_ms: int
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{stretch.id}/replace",
        data={
            "take_id": stretch.take_id,
            "starts_ms": str(stretch.starts_ms),
            "ends_ms": str(ends_ms),
        },
        files={"file": ("frase.wav", b"a frase dita de novo", "audio/wav")},
    )


async def test_the_last_pause_of_a_part_moves_later_with_the_frase_told_again(
    client: httpx.AsyncClient, db_session: AsyncSession, transcribed: list[bytes]
) -> None:
    session, parts = await _rehearsed(db_session)
    last = (await final_segments(db_session, session.id))[-1]

    moved = await _move(client, session.id, last, ends_ms=4200)

    assert moved.status_code == 200, moved.text
    spans = [(one["take_id"], one["starts_ms"], one["ends_ms"]) for one in moved.json()["segments"]]
    assert spans[-1] == (parts[1].id, 2000, 4200), (
        "a pausa da última frase da parte 2 ia de 3000 ms para 4200 ms"
    )
    assert last.id not in [one["segment_id"] for one in moved.json()["segments"]], (
        "a frase de antes continuava contando ao lado da nova"
    )


async def test_an_earlier_pause_of_the_part_does_not_move_and_nothing_is_kept(
    client: httpx.AsyncClient, db_session: AsyncSession, transcribed: list[bytes]
) -> None:
    session, _ = await _rehearsed(db_session)
    earlier = (await final_segments(db_session, session.id))[-2]

    refused = await _move(client, session.id, earlier, ends_ms=1800)

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_ONLY_ON_THE_LAST_FRASE"
    assert transcribed == [], "a recusa pagava o transcritor antes de recusar"
    assert await _retro_takes(db_session, session.id) == [], "a gravação da recusa ficava guardada"
    assert [(one.starts_ms, one.ends_ms) for one in await final_segments(db_session, session.id)][
        3:
    ] == [(0, 1000), (1000, 2000), (2000, 3000)], "a recusa mexeu nas frases da parte 2"


async def test_a_compressed_take_keeps_its_last_pause_where_it_was(
    client: httpx.AsyncClient, db_session: AsyncSession, transcribed: list[bytes]
) -> None:
    session, _ = await _rehearsed(db_session, content_type="audio/mp4")
    last = (await final_segments(db_session, session.id))[-1]

    refused = await _move(client, session.id, last, ends_ms=4200)

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_CANNOT_STAND_THERE"
    assert transcribed == [], "uma gravação comprimida movia a pausa mesmo sem poder buscar nela"


async def test_a_conferida_passage_keeps_its_last_pause_where_it_was(
    client: httpx.AsyncClient, db_session: AsyncSession, transcribed: list[bytes]
) -> None:
    session, _ = await _rehearsed(db_session)
    state = back_translation_of(session)
    state.checked = True
    await save_back_translation(db_session, session, state)
    last = (await final_segments(db_session, session.id))[-1]

    refused = await _move(client, session.id, last, ends_ms=4200)

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_CANNOT_STAND_THERE"
    assert transcribed == [], "a passagem conferida ainda deixava mover a pausa"


async def test_an_approved_passage_keeps_its_last_pause_even_once_it_is_no_longer_conferida(
    client: httpx.AsyncClient, db_session: AsyncSession, transcribed: list[bytes]
) -> None:
    session, _ = await _rehearsed(db_session)
    db_session.add(
        IRRelease(
            session_id=session.id,
            project_id=session.project_id,
            pericope=session.pericope,
            version=1,
            package_sha256="a" * 64,
            packet={},
        )
    )
    await db_session.commit()
    last = (await final_segments(db_session, session.id))[-1]

    refused = await _move(client, session.id, last, ends_ms=4200)

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_CANNOT_STAND_THERE"
    assert transcribed == [], "o rascunho aprovado ainda deixava mover a pausa"


async def test_a_pause_moved_to_within_a_fifth_of_a_second_of_the_start_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession, transcribed: list[bytes]
) -> None:
    session, _ = await _rehearsed(db_session)
    last = (await final_segments(db_session, session.id))[-1]

    refused = await _move(client, session.id, last, ends_ms=2150)

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_CANNOT_STAND_THERE"
    assert transcribed == [], "uma frase de 150 ms passava como frase"


async def test_a_pause_moved_past_the_end_of_the_recording_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession, transcribed: list[bytes]
) -> None:
    session, _ = await _rehearsed(db_session)
    last = (await final_segments(db_session, session.id))[-1]

    refused = await _move(client, session.id, last, ends_ms=5400)

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_PAST_THE_END"
    assert transcribed == [], "uma pausa depois do fim da gravação de 5000 ms passava"


async def test_a_pause_a_hair_past_the_measured_end_still_moves(
    client: httpx.AsyncClient, db_session: AsyncSession, transcribed: list[bytes]
) -> None:
    session, _ = await _rehearsed(db_session)
    last = (await final_segments(db_session, session.id))[-1]

    moved = await _move(client, session.id, last, ends_ms=5200)

    assert moved.status_code == 200, moved.text
    assert moved.json()["segments"][-1]["ends_ms"] == 5200, (
        "o fim medido pelo tablet e o da gravação diferem por um fio, e a pausa no fim era recusada"
    )


async def test_a_frase_that_is_no_longer_the_last_is_refused_at_the_capture_as_well(
    db_session: AsyncSession,
) -> None:
    session, _ = await _rehearsed(db_session)
    earlier = (await final_segments(db_session, session.id))[-2]

    with pytest.raises(PauseCannotMove) as refused:
        await capture_segment(
            db_session,
            session,
            take_id=earlier.take_id,
            starts_ms=earlier.starts_ms,
            ends_ms=1800,
            transcript="a frase contada de novo",
            replaces=earlier,
        )

    assert refused.value.code == "PAUSE_ONLY_ON_THE_LAST_FRASE"
