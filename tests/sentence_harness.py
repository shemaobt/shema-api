"""A rehearsal recorded in WAV, with frases told over it, and the door that re-records one.

Plain builders and constants: each case module keeps its own fixtures.
"""

from __future__ import annotations

import hashlib
import io
import wave
from array import array
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.segments import capture_segment
from tests.device_harness import TABLET_TEAM
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX, P, create_session, ensaio_take
from tests.room_harness import REHEARSED_AT

RATE = 16000
WAV = "audio/wav"


def wav(samples: list[int], rate: int = RATE, channels: int = 1) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as file:
        file.setnchannels(channels)
        file.setsampwidth(2)
        file.setframerate(rate)
        file.writeframes(array("h", samples).tobytes())
    return out.getvalue()


def samples_of(audio: bytes) -> list[int]:
    with wave.open(io.BytesIO(audio), "rb") as file:
        return list(array("h", file.readframes(file.getnframes())))


def seconds(count: float, value: int) -> list[int]:
    return [value] * int(count * RATE)


def spoken(length: float, *, silence: float = 0.3) -> bytes:
    """A sentence of `length` seconds of voice, with `silence` seconds of quiet on each side."""
    return wav(seconds(silence, 0) + seconds(length, 9000) + seconds(silence, 0))


def part_audio(number: int, length_ms: int) -> bytes:
    return wav([(n * 7 + number * 13) % 3000 - 1500 for n in range(length_ms * RATE // 1000)])


async def rehearsed_in_wav(
    db: AsyncSession,
    store: MemoryStore,
    parts: list[list[tuple[int, int]]],
    *,
    content_type: str = WAV,
) -> tuple[IRSession, list[IRTake], list[list[IRSegment]]]:
    """One WAV part per entry of `parts`, its bytes in `store`, a frase told over each span."""
    session = await create_session(db, pericope=P, project_id=TABLET_TEAM, language="pt")
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    takes, frases = [], []
    for number, spans in enumerate(parts, start=1):
        audio = part_audio(number, spans[-1][1])
        take = ensaio_take(
            session.id,
            scope=f"parte-{number}",
            ordinal=number,
            sha256=hashlib.sha256(audio).hexdigest(),
            created_at=REHEARSED_AT + timedelta(minutes=number),
            project_id=session.project_id,
        )
        take.content_type = content_type
        db.add(take)
        await db.commit()
        store.objects[take.storage_key] = audio
        told = []
        for index, (starts_ms, ends_ms) in enumerate(spans, start=1):
            told.append(
                await capture_segment(
                    db,
                    session,
                    take_id=take.id,
                    starts_ms=starts_ms,
                    ends_ms=ends_ms,
                    bridge_take_id=f"retro-{number}-{index}",
                    transcript=f"parte {number} frase {index}",
                )
            )
        takes.append(take)
        frases.append(told)
    return session, takes, frases


async def re_record(
    client: httpx.AsyncClient,
    session_id: str,
    segment_id: str,
    audio: bytes,
    *,
    sentence_id: str = "sentence-0001",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment_id}/sentence",
        data={"sentence_id": sentence_id},
        files={"file": ("frase.wav", audio, WAV)},
        headers=headers,
    )


async def take_named(db: AsyncSession, take_id: str) -> IRTake:
    found = await db.execute(
        select(IRTake).where(IRTake.id == take_id).execution_options(populate_existing=True)
    )
    return found.scalar_one()
