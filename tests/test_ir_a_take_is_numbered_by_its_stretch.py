"""A back-translation take is numbered by the stretch it tells, or not at all.

Until now the chunks route guessed a take's position from a count of stretches already told,
before the transcript came back. A transcript that came back empty still kept the guess, so
the next good transcript inherited the same number and two takes claimed one place in the
telling-back. The number that survives is the ordinal of the stretch the take actually told —
written when `capture_segment` assigns it — and a take that told no stretch carries none.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTake, IRTakeKind
from app.services import internalization_room as room
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.release import build_internalization_release
from app.services.platform.storage import StoredObject
from tests.test_internalization_room_release import _supported_comprehension

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
PASSAGE = "P01"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def stat(self, key: str) -> StoredObject | None:
        stored = self.objects.get(key)
        if stored is None:
            return None
        checksum = Checksum()
        checksum.update(stored)
        return StoredObject(
            size=len(stored), crc32c=base64.b64encode(checksum.digest()).decode("ascii")
        )


@pytest.fixture()
async def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    from app.services.internalization_room import takes as takes_service

    store = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: store)
    return store


@pytest.fixture()
async def client(db_session: AsyncSession, bucket: MemoryStore, monkeypatch: pytest.MonkeyPatch):
    """The room's own routes, with the transcriber and the bucket held still.

    `client.said` queues what the transcriber will answer, one entry per capture.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router
    from app.api.internalization_room import segments as segments_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    said: list[str] = []

    async def _transcribe(*_: Any, **__: Any) -> str:
        return said.pop(0) if said else "algo que a equipe contou"

    monkeypatch.setattr(bt_api, "heard", _transcribe)
    monkeypatch.setattr(segments_api, "heard", _transcribe)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.said = said  # type: ignore[attr-defined]
        yield c


async def _open_session(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": PASSAGE}
    )
    assert created.status_code == 200, created.text
    return str(created.json()["session_id"])


async def _record(client: httpx.AsyncClient, session_id: str, audio: bytes) -> str:
    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"kind": IRTakeKind.ENSAIO.value, "scope": PASSAGE},
        files={"file": ("tomada.m4a", audio, "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def _tell_back(
    client: httpx.AsyncClient,
    session_id: str,
    *,
    take_id: str,
    starts_ms: int,
    ends_ms: int,
    audio: bytes,
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("trecho.m4a", audio, "audio/mp4")},
    )


async def _replace(
    client: httpx.AsyncClient,
    session_id: str,
    segment_id: str,
    *,
    take_id: str,
    starts_ms: int,
    ends_ms: int,
    audio: bytes,
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment_id}/replace",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("de-novo.m4a", audio, "audio/mp4")},
    )


async def _told_so_far(client: httpx.AsyncClient, session_id: str) -> list[dict[str, Any]]:
    state = await client.get(f"{PREFIX}/sessions/{session_id}", headers={"X-Room-Key": KEY})
    assert state.status_code == 200, state.text
    return list(state.json()["back_translation"]["segments"])


async def _retro_takes(db: AsyncSession, session_id: str) -> list[IRTake]:
    result = await db.execute(
        select(IRTake)
        .where(IRTake.session_id == session_id, IRTake.kind == IRTakeKind.RETRO)
        .order_by(IRTake.created_at)
    )
    return list(result.scalars().all())


async def _retro_take_by_audio(db: AsyncSession, session_id: str, audio: bytes) -> IRTake:
    """The retro row for this exact recording, told apart from its siblings by content.

    `created_at` has only second resolution on SQLite, so three captures made in one test can
    land in the same second with no defined order between them — a position in a list ordered
    by it is not a stable identity. The bytes are.
    """
    digest = hashlib.sha256(audio).hexdigest()
    result = await db.execute(
        select(IRTake).where(
            IRTake.session_id == session_id,
            IRTake.kind == IRTakeKind.RETRO,
            IRTake.sha256 == digest,
        )
    )
    return result.scalar_one()


async def _retro_take_by_id(db: AsyncSession, take_id: str) -> IRTake:
    result = await db.execute(select(IRTake).where(IRTake.id == take_id))
    return result.scalar_one()


async def _a_failed_capture_then_two_good_ones(client: httpx.AsyncClient) -> str:
    """One session: a stretch told back three times, the first attempt inaudible.

    The retry over the same slice is what takes the first place; the third call is a new
    stretch. Three different byte strings, so the dedupe by hash never enters into it.
    """
    session_id = await _open_session(client)
    take_id = await _record(client, session_id, b"a equipe ensaiou a passagem inteira")

    client.said.extend(["", "Noemi ouve que", "e decide voltar"])  # type: ignore[attr-defined]
    await _tell_back(
        client, session_id, take_id=take_id, starts_ms=0, ends_ms=9000, audio=b"tentativa muda"
    )
    await _tell_back(
        client, session_id, take_id=take_id, starts_ms=0, ends_ms=9000, audio=b"tentativa boa"
    )
    await _tell_back(
        client, session_id, take_id=take_id, starts_ms=9000, ends_ms=21000, audio=b"terceiro trecho"
    )
    return session_id


async def _ready_for_release(db: AsyncSession, session: IRSession) -> dict[str, Any]:
    """Everything `build_internalization_release` asks for besides the telling-back itself.

    The telling-back is left exactly as the caller built it: only comprehension, coverage,
    consent and the playback report are added here, none of which this ticket's rule touches.
    """
    session.coverage_state = merge(
        initial_state(PASSAGE), pericope_num=PASSAGE, engaged=element_keys(PASSAGE)
    )
    await room.save_comprehension(db, session, _supported_comprehension(PASSAGE))

    told = await room.final_segments(db, session.id)
    state = room.back_translation_of(session)
    state.analysed_segment_ids = [segment.id for segment in told]
    state.evidence_sufficient = True
    clip_end = max((segment.ends_ms for segment in told), default=0)
    await room.report_playback(
        db, session, state, played_ranges=[[0, clip_end]], clip_duration_ms=clip_end
    )

    return await build_internalization_release(db, session)


# ---------------------------------------------------------------------------
# 1. A failed capture claims no place, and the next one takes the first
# ---------------------------------------------------------------------------


async def test_a_failed_capture_claims_no_place_and_the_next_one_takes_the_first(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _a_failed_capture_then_two_good_ones(client)

    mute = await _retro_take_by_audio(db_session, session_id, b"tentativa muda")
    assert mute.chunk_index is None, (
        "a tentativa muda não fica com número nenhum, e a próxima toma o primeiro lugar"
    )

    stretches = await room.final_segments(db_session, session_id)
    assert [segment.ordinal for segment in stretches] == [1, 2]

    for segment in stretches:
        assert segment.bridge_take_id is not None
        bridge_take = await _retro_take_by_id(db_session, segment.bridge_take_id)
        assert bridge_take.chunk_index == segment.ordinal, (
            "o índice do take contado é o ordinal do trecho que ele conta"
        )


# ---------------------------------------------------------------------------
# 2. The packet never shows two takes at one place
# ---------------------------------------------------------------------------


async def test_the_packet_never_shows_two_takes_at_one_place(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _a_failed_capture_then_two_good_ones(client)
    session = await room.get_session(db_session, session_id)

    artifact = await _ready_for_release(db_session, session)

    indexes = [take["chunk_index"] for take in artifact["back_translation"]["retro_takes"]]
    assert indexes == [None, 1, 2]
    non_null = [index for index in indexes if index is not None]
    assert len(non_null) == len(set(non_null)), (
        "dois takes não podem apontar para o mesmo lugar na retrotradução"
    )


# ---------------------------------------------------------------------------
# 3. Re-recording a stretch keeps its number
# ---------------------------------------------------------------------------


async def test_re_recording_a_stretch_keeps_its_number(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _open_session(client)
    take_id = await _record(client, session_id, b"a equipe ensaiou a passagem inteira")

    client.said.append("Noemi mandou Rute voltar.")  # type: ignore[attr-defined]
    await _tell_back(
        client, session_id, take_id=take_id, starts_ms=0, ends_ms=9000, audio=b"primeiro trecho"
    )
    segment = (await _told_so_far(client, session_id))[0]

    client.said.append("Noemi mandou Rute voltar, de novo.")  # type: ignore[attr-defined]
    replaced = await _replace(
        client,
        session_id,
        segment["segment_id"],
        take_id=take_id,
        starts_ms=0,
        ends_ms=9000,
        audio=b"segunda gravacao do mesmo trecho",
    )
    assert replaced.status_code == 200, replaced.text

    retro_rows = await _retro_takes(db_session, session_id)
    assert [row.chunk_index for row in retro_rows] == [1, 1], (
        "a correção conta como o mesmo trecho, com o mesmo número"
    )
    assert retro_rows[0].id != retro_rows[1].id

    session = await room.get_session(db_session, session_id)
    artifact = await _ready_for_release(db_session, session)
    retro_takes = artifact["back_translation"]["retro_takes"]
    retro_view = [(take["take_id"], take["chunk_index"]) for take in retro_takes]
    assert {index for _, index in retro_view} == {1}
    assert len({take_id_ for take_id_, _ in retro_view}) == 2, (
        "os dois takes viajam no pacote, ambos sob o mesmo índice, cada um com o seu id"
    )
