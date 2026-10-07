"""ENG-1164 — a telling with no words never becomes a stretch: the chunk door refuses it.

The door answered 200 `captured: false` when the transcript came back empty, and an empty
retelling was counted toward the warning. A telling with no words is refused with its own
code and the name of the inaudible line, and counts nothing. The audio stays kept: no
recording is ever lost.

ENG-1226 reads an outage the same way: `heard` returns nothing for it, so it is refused too
(ADR 0049). What the transcriber raises `ValidationError` for is the recording it could not
read, which is the telling with no words.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UpstreamServiceError, ValidationError
from app.db.models.internalization_room import IRSegment, IRSessionStatus
from app.services.internalization_room.sessions import RETELLS_BEFORE_A_WARNING
from tests.hard_stretch_harness import (
    AUDIO,
    DEVICE,
    IR,
    ROOM_KEY,
    SLICES,
    current,
    marks,
    retro_takes,
    row,
    told,
)
from tests.hard_stretch_harness import MemoryStore as _MemoryStore
from tests.hard_stretch_harness import a_session as _a_session
from tests.hard_stretch_harness import rehearse as _rehearse


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The chunk door with the real `heard`, over a transcriber that answers what is queued.

    `client.transcriber` queues one entry per call: text is what the transcriber returns, an
    exception is what it raises.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router as room_router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import hearing
    from app.services.internalization_room import takes as takes_service

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)

    queue: list[str | Exception] = []

    async def _transcribe(*_: Any, **__: Any) -> str:
        answer = queue.pop(0) if queue else "algo que a equipe contou"
        if isinstance(answer, Exception):
            raise answer
        return answer

    async def _unread(**_: Any) -> None:
        return None

    monkeypatch.setattr(hearing, "transcribe_audio", _transcribe)
    monkeypatch.setattr(bt_api, "read_ahead", _unread)
    bucket = _MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: bucket)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.transcriber = queue  # type: ignore[attr-defined]
        c.said = queue  # type: ignore[attr-defined]
        c.bucket = bucket  # type: ignore[attr-defined]
        yield c


async def _tell(
    client: httpx.AsyncClient,
    session_id: str,
    take_id: str,
    stretch: int,
    heard: str | Exception,
    *,
    again: bool = False,
) -> httpx.Response:
    starts, ends = SLICES[stretch - 1]
    client.transcriber.append(heard)  # type: ignore[attr-defined]
    data = {"take_id": take_id, "starts_ms": str(starts), "ends_ms": str(ends)}
    if again:
        data["retelling"] = "true"
    return await client.post(
        f"{IR}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data=data,
        files={"file": ("trecho.m4a", AUDIO, "audio/mp4")},
    )


async def _segment_rows(db: AsyncSession, session_id: str) -> list[str]:
    result = await db.execute(
        select(IRSegment.id).where(IRSegment.session_id == session_id).order_by(IRSegment.id)
    )
    return list(result.scalars().all())


@pytest.mark.parametrize(
    "heard",
    [
        pytest.param("", id="empty"),
        pytest.param("[silêncio]", id="only the transcribers annotation"),
        pytest.param(ValidationError("Transcription returned empty text"), id="unreadable"),
    ],
)
async def test_a_first_telling_with_no_words_is_refused_and_is_no_stretch(
    client: httpx.AsyncClient, db_session: AsyncSession, heard: str | Exception
) -> None:
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)
    before = await _segment_rows(db_session, session_id)

    refused = await _tell(client, session_id, take_id, 1, heard)

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "WORDLESS_TELLING"
    assert body["detail"]
    assert "fixed_line" not in body
    assert await _segment_rows(db_session, session_id) == before
    assert await current(db_session, session_id) == []


async def test_an_empty_retelling_is_refused_and_counts_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)
    await told(client, session_id, take_id, 1)
    (standing,) = await current(db_session, session_id)
    tellings = standing.tellings
    before = await _segment_rows(db_session, session_id)

    for _ in range(RETELLS_BEFORE_A_WARNING):
        refused = await _tell(client, session_id, take_id, 1, "", again=True)
        assert refused.status_code == 422, refused.text
        assert refused.json()["code"] == "WORDLESS_TELLING"

    (after,) = await current(db_session, session_id)
    assert after.id == standing.id
    assert after.tellings == tellings
    assert await _segment_rows(db_session, session_id) == before
    assert await marks(db_session, session_id) == []
    assert (await row(db_session, session_id)).status is not IRSessionStatus.NEEDS_PERSON
    read = await client.get(f"{IR}/sessions/{session_id}", headers={"X-Room-Key": ROOM_KEY})
    assert read.status_code == 200, read.text
    assert read.json()["halt"] is None


async def test_the_recording_of_a_refused_telling_stays_kept(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)

    refused = await _tell(client, session_id, take_id, 1, "")

    assert refused.status_code == 422
    assert len(await retro_takes(db_session, session_id)) == 1
    assert AUDIO in client.bucket.objects.values()  # type: ignore[attr-defined]


async def test_a_transcriber_outage_is_a_wordless_refusal_that_counts_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)
    await told(client, session_id, take_id, 1)
    (standing,) = await current(db_session, session_id)
    tellings = standing.tellings

    outage = await _tell(
        client, session_id, take_id, 1, UpstreamServiceError("transcriber down"), again=True
    )

    assert outage.status_code == 422, outage.text
    assert outage.json()["code"] == "WORDLESS_TELLING"
    (after,) = await current(db_session, session_id)
    assert after.id == standing.id
    assert after.tellings == tellings


async def test_a_telling_with_words_is_still_a_stretch(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _a_session(db_session)
    take_id = await _rehearse(client, session_id)

    answered = await _tell(client, session_id, take_id, 1, "Noemi ouve que o Senhor visitou")

    assert answered.status_code == 200, answered.text
    assert answered.json()["captured"] is True
    assert len(await current(db_session, session_id)) == 1
