"""A rehearsal recorded in WAV, with frases told over it, and the door that re-records one.

Plain builders and constants: each case module keeps its own fixtures.
"""

from __future__ import annotations

import hashlib
import io
import json
import wave
from array import array
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.llm import CACHE_BREAK
from app.services.internalization_room.segments import capture_segment
from tests.device_harness import TABLET_TEAM
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX, P, create_session, ensaio_take
from tests.room_harness import REHEARSED_AT, played_every_part, press_terminei

RATE = 16000
PART = [(0, 1000), (1000, 2000), (2000, 3000)]
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


def nuance_of_frase(frase: int, quote: str = "") -> dict[str, Any]:
    return {
        "kind": "nuance",
        "note": "O jeito de contar mudou.",
        "frase": frase,
        "quote": quote or f"frase {frase}",
        "story": "a história conta de outro jeito",
    }


def names_the_nuance_on(frase: int) -> str:
    return f"Só um detalhe, na frase {frase}: vocês traduziram «frase {frase}»."


class Speaker:
    def __init__(self) -> None:
        self.line = "Vocês contaram bem."
        self.briefs: list[str] = []

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.briefs.append(system_prompt.replace(CACHE_BREAK, ""))
        return self.line

    def handed(self) -> list[dict[str, Any]]:
        return list(
            json.loads(self.briefs[-1].split("## The findings for the whole passage\n\n")[1])
        )


async def named_and_heard(
    client: httpx.AsyncClient,
    analyst: Any,
    speaker: Speaker,
    session_id: str,
    part_id: str,
    nuance: dict[str, Any],
) -> None:
    analyst.readings = [{"findings": [nuance]}]
    speaker.line = names_the_nuance_on(nuance["frase"])
    pressed = await press_terminei(
        client,
        session_id,
        report=played_every_part([part_id], duration_ms=3000),
    )
    assert pressed.status_code == 200, pressed.text
    heard = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/heard",
        json={"at": pressed.json()["check_at"]},
    )
    assert heard.status_code == 200, heard.text


async def laid_in_and_told_again(
    client: httpx.AsyncClient,
    session_id: str,
    segment_id: str,
    position: int,
    *,
    sentence_id: str = "sentence-0001",
) -> str:
    laid = (
        await re_record(client, session_id, segment_id, spoken(1.0), sentence_id=sentence_id)
    ).json()["segments"]
    new = laid[position]
    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment_id}/replace",
        data={
            "take_id": new["take_id"],
            "starts_ms": str(new["starts_ms"]),
            "ends_ms": str(new["ends_ms"]),
        },
        files={"file": ("trecho.m4a", b"a equipe traduziu a frase nova", "audio/mp4")},
    )
    assert told.status_code == 200, told.text
    return str(new["take_id"])
