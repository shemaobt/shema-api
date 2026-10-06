"""ENG-1226 — a telling is recognized in the session's bridge language, within 15 s.

Both telling doors (the chunk door and the replace door) used to let the transcriber guess the
language, so a Portuguese telling came back as phonetic Spanish, and let it take two minutes. A
telling now carries the session's language and is bound to fifteen seconds; one that comes back
with no words, fails, or runs past the bound is refused with `WORDLESS_TELLING` and no spoken
line. Scribe is played at the provider boundary, so the real `transcribe_audio` and `heard` run.
"""

from __future__ import annotations

import asyncio
import re
import sys
import time
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSessionStatus, IRTake, IRTakeKind
from app.services.internalization_room import sessions as room
from app.services.internalization_room.sessions import RETELLS_BEFORE_A_WARNING
from tests.hard_stretch_harness import (
    AUDIO,
    DEVICE,
    IR,
    ROOM_KEY,
    SLICES,
    P,
    current,
    marks,
    row,
)
from tests.hard_stretch_harness import MemoryStore as _MemoryStore
from tests.hard_stretch_harness import rehearse as _rehearse

PORTUGUESE = "Noemi ouve que o Senhor visitou o seu povo"
ENGLISH = "Naomi hears that the Lord visited his people"
SPANISH = "Noemí oye que el Señor visitó"


class Scribe:
    """The provider as the telling doors meet it: honours `language_code`, else guesses Spanish."""

    def __init__(self) -> None:
        self.mode = "words"

    def handle(self, request: httpx.Request) -> httpx.Response | Any:
        return self.answer(request)

    async def answer(self, request: httpx.Request) -> httpx.Response:
        if self.mode == "down":
            return httpx.Response(503, text="unavailable")
        if self.mode == "hang":
            await asyncio.Event().wait()
        if self.mode == "empty":
            return httpx.Response(200, json={"text": ""})
        if self.mode == "annotation":
            return httpx.Response(200, json={"text": "[silêncio]"})
        hint = re.search(rb'name="language_code"\r\n\r\n(\w+)', request.content)
        said = {b"pt": PORTUGUESE, b"en": ENGLISH}.get(hint.group(1) if hint else b"", SPANISH)
        return httpx.Response(200, json={"text": said})


@pytest.fixture()
async def scribe() -> Scribe:
    return Scribe()


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, scribe: Scribe):
    from fastapi import FastAPI

    import app.services.translation_helper.transcribe_audio  # noqa: F401
    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router as room_router
    from app.api.internalization_room import segments as segments_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    transcriber = sys.modules["app.services.translation_helper.transcribe_audio"]

    settings = get_settings()
    monkeypatch.setattr(settings, "internalization_room_api_key", ROOM_KEY, raising=False)
    monkeypatch.setattr(settings, "elevenlabs_api_key", "chave-de-teste", raising=False)

    provider = httpx.AsyncClient(transport=httpx.MockTransport(scribe.handle))
    monkeypatch.setattr(transcriber, "_make_client", lambda: provider)

    async def _unread(**_: Any) -> None:
        return None

    monkeypatch.setattr(bt_api, "read_ahead", _unread)
    monkeypatch.setattr(segments_api, "read_ahead", _unread)
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
        yield c
    await provider.aclose()


async def _a_session_in(db: AsyncSession, language: str) -> str:
    session = await room.create_session(db, pericope=P, language=language)
    return str(session.id)


async def _tell(client: httpx.AsyncClient, session_id: str, take_id: str) -> httpx.Response:
    starts, ends = SLICES[0]
    return await client.post(
        f"{IR}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data={"take_id": take_id, "starts_ms": str(starts), "ends_ms": str(ends)},
        files={"file": ("trecho.m4a", AUDIO, "audio/mp4")},
    )


async def _correct(
    client: httpx.AsyncClient,
    session_id: str,
    segment_id: str,
    take_id: str,
    audio: bytes = AUDIO,
) -> httpx.Response:
    starts, ends = SLICES[0]
    return await client.post(
        f"{IR}/sessions/{session_id}/segments/{segment_id}/replace",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data={"take_id": take_id, "starts_ms": str(starts), "ends_ms": str(ends)},
        files={"file": ("trecho.m4a", audio, "audio/mp4")},
    )


async def _one_told_stretch(
    client: httpx.AsyncClient, db: AsyncSession, language: str = "pt"
) -> tuple[str, str]:
    session_id = await _a_session_in(db, language)
    take_id = await _rehearse(client, session_id)
    told = await _tell(client, session_id, take_id)
    assert told.status_code == 200, told.text
    return session_id, take_id


async def _retro_takes(db: AsyncSession, session_id: str) -> list[IRTake]:
    from sqlalchemy import select

    result = await db.execute(
        select(IRTake).where(IRTake.session_id == session_id, IRTake.kind == IRTakeKind.RETRO)
    )
    return list(result.scalars().all())


async def test_a_telling_in_a_portuguese_session_is_stored_in_portuguese_words(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _a_session_in(db_session, "pt")
    take_id = await _rehearse(client, session_id)

    answered = await _tell(client, session_id, take_id)

    assert answered.status_code == 200, answered.text
    (stretch,) = await current(db_session, session_id)
    assert stretch.transcript == PORTUGUESE


async def test_a_telling_in_an_english_session_is_recognized_in_english(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _a_session_in(db_session, "en")
    take_id = await _rehearse(client, session_id)

    answered = await _tell(client, session_id, take_id)

    assert answered.status_code == 200, answered.text
    (stretch,) = await current(db_session, session_id)
    assert stretch.transcript == ENGLISH


async def test_a_correction_in_a_portuguese_session_is_stored_in_portuguese_words(
    client: httpx.AsyncClient, db_session: AsyncSession, scribe: Scribe
) -> None:
    session_id, take_id = await _one_told_stretch(client, db_session)
    (standing,) = await current(db_session, session_id)

    answered = await _correct(client, session_id, standing.id, take_id)

    assert answered.status_code == 200, answered.text
    (replacement,) = await current(db_session, session_id)
    assert replacement.id != standing.id
    assert replacement.transcript == PORTUGUESE


@pytest.mark.parametrize("mode", ["empty", "annotation"])
async def test_a_telling_the_recognizer_finds_no_words_in_is_refused_with_no_spoken_line(
    client: httpx.AsyncClient, db_session: AsyncSession, scribe: Scribe, mode: str
) -> None:
    session_id = await _a_session_in(db_session, "pt")
    take_id = await _rehearse(client, session_id)
    scribe.mode = mode

    refused = await _tell(client, session_id, take_id)

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "WORDLESS_TELLING"
    assert "fixed_line" not in body
    assert await current(db_session, session_id) == []
    assert len(await _retro_takes(db_session, session_id)) == 1


async def test_a_telling_the_recognizer_fails_on_is_refused_with_no_spoken_line(
    client: httpx.AsyncClient, db_session: AsyncSession, scribe: Scribe
) -> None:
    session_id = await _a_session_in(db_session, "pt")
    take_id = await _rehearse(client, session_id)
    scribe.mode = "down"

    refused = await _tell(client, session_id, take_id)

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "WORDLESS_TELLING"
    assert "fixed_line" not in body
    assert await current(db_session, session_id) == []


async def test_a_telling_the_recognizer_does_not_answer_within_the_bound_is_refused(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    scribe: Scribe,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.internalization_room import hearing

    monkeypatch.setattr(hearing, "RECOGNIZER_BOUND_SECONDS", 0.2)
    session_id = await _a_session_in(db_session, "pt")
    take_id = await _rehearse(client, session_id)
    scribe.mode = "hang"

    started = time.monotonic()
    refused = await _tell(client, session_id, take_id)
    waited = time.monotonic() - started

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "WORDLESS_TELLING"
    assert "fixed_line" not in body
    assert await current(db_session, session_id) == []
    assert waited < 2.0


def test_the_recognizers_bound_is_fifteen_seconds() -> None:
    from app.services.internalization_room import hearing

    assert hearing.RECOGNIZER_BOUND_SECONDS == 15


async def test_an_empty_correction_leaves_the_earlier_telling_as_it_was(
    client: httpx.AsyncClient, db_session: AsyncSession, scribe: Scribe
) -> None:
    session_id, take_id = await _one_told_stretch(client, db_session)
    (standing,) = await current(db_session, session_id)
    retros = len(await _retro_takes(db_session, session_id))
    scribe.mode = "empty"

    refused = await _correct(
        client, session_id, standing.id, take_id, audio=b"a correcao sem palavras"
    )

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "WORDLESS_TELLING"
    assert "fixed_line" not in body
    (after,) = await current(db_session, session_id)
    assert (after.id, after.transcript, after.tellings) == (
        standing.id,
        standing.transcript,
        standing.tellings,
    )
    assert await marks(db_session, session_id) == []
    assert len(await _retro_takes(db_session, session_id)) == retros + 1


@pytest.mark.parametrize("mode", ["down", "hang"])
async def test_a_correction_the_recognizer_fails_on_or_runs_past_the_bound_leaves_the_telling(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    scribe: Scribe,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    from app.services.internalization_room import hearing

    monkeypatch.setattr(hearing, "RECOGNIZER_BOUND_SECONDS", 0.2)
    session_id, take_id = await _one_told_stretch(client, db_session)
    (standing,) = await current(db_session, session_id)
    scribe.mode = mode

    refused = await _correct(client, session_id, standing.id, take_id)

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "WORDLESS_TELLING"
    assert "fixed_line" not in body
    (after,) = await current(db_session, session_id)
    assert (after.id, after.transcript, after.tellings) == (
        standing.id,
        standing.transcript,
        standing.tellings,
    )
    assert await marks(db_session, session_id) == []


async def test_empty_corrections_never_make_a_hard_stretch(
    client: httpx.AsyncClient, db_session: AsyncSession, scribe: Scribe
) -> None:
    session_id, take_id = await _one_told_stretch(client, db_session)
    (standing,) = await current(db_session, session_id)
    scribe.mode = "empty"

    for _ in range(RETELLS_BEFORE_A_WARNING):
        refused = await _correct(client, session_id, standing.id, take_id)
        assert refused.status_code == 422, refused.text

    (after,) = await current(db_session, session_id)
    assert after.tellings == standing.tellings
    assert await marks(db_session, session_id) == []
    assert (await row(db_session, session_id)).status is not IRSessionStatus.NEEDS_PERSON


async def test_a_telling_with_words_is_still_a_stretch_on_both_doors(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _a_session_in(db_session, "pt")
    take_id = await _rehearse(client, session_id)

    told = await _tell(client, session_id, take_id)
    assert told.status_code == 200, told.text
    assert told.json()["captured"] is True
    (standing,) = await current(db_session, session_id)

    corrected = await _correct(client, session_id, standing.id, take_id)

    assert corrected.status_code == 200, corrected.text
    assert len(await current(db_session, session_id)) == 1
