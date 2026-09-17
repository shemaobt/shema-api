"""Pressing `terminei` again must not re-voice a verdict the room already reached.

A second press with nothing new told back is the same question, and the room already has
its answer. Asking the model again costs two calls nobody asked for; appending again writes
the room into the transcript as having spoken twice, which is a false record of what
happened in front of the team.

The controls matter more than the fix. A guard that also refuses the press *after* real new
work leaves the team unable to get a fresh verdict at all — a worse room than the one with
the bug.

None of these cases reads the guard's own bookkeeping: they watch how many times a model was
consulted, what the room said, and what reached the conversation a facilitator reads.
"""

from __future__ import annotations

import base64
import importlib
import json
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRTakeKind
from app.services.internalization_room.sessions import get_session
from app.services.platform.storage import StoredObject

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


class Consulted:
    """Every model the room can reach on this route, and how often each was asked.

    Kept apart because "the room did not run again" is not readable from the answer: a
    reused verdict and a freshly recomputed identical one look the same from outside.
    """

    def __init__(self) -> None:
        self.analyst = 0
        self.speaker = 0
        self.validator = 0
        self.voice = 0

    @property
    def total(self) -> int:
        return self.analyst + self.speaker + self.validator + self.voice


@pytest.fixture()
async def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    from app.services.internalization_room import takes as takes_service

    store = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: store)
    return store


@pytest.fixture()
def consulted(monkeypatch: pytest.MonkeyPatch) -> Consulted:
    from app.api.internalization_room import back_translation as bt_api
    from app.services.internalization_room import back_translation as bt_service

    tally = Consulted()
    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    async def _analyst(*, system_prompt: str, user_content: str, **_: Any) -> str:
        tally.analyst += 1
        return '{"evidence_sufficient": true, "findings": []}'

    async def _verdict(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            tally.validator += 1
            return json.dumps({"verdict": "pass", "issues": []})
        tally.speaker += 1
        return "Vocês contaram bem."

    async def _voice(text: str, *_: Any, **__: Any):
        tally.voice += 1
        return (type("Voiced", (), {"key": f"clipe-{tally.voice}"})(), 0)

    monkeypatch.setattr(bt_service, "call_agent", _analyst)
    monkeypatch.setattr(turn_module, "call_agent", _verdict)
    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _voice)
    return tally


@pytest.fixture()
async def client(db_session: AsyncSession, bucket: MemoryStore, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    said: list[str] = []

    async def _transcribe(*_: Any, **__: Any) -> str:
        return said.pop(0) if said else "algo que a equipe contou"

    monkeypatch.setattr(bt_api, "heard", _transcribe)

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
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY},
        json={"pericope": PASSAGE, "language": "pt"},
    )
    assert created.status_code == 200, created.text
    return str(created.json()["session_id"])


async def _record(client: httpx.AsyncClient, session_id: str) -> str:
    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"kind": IRTakeKind.ENSAIO.value, "scope": PASSAGE},
        files={"file": ("tomada.m4a", b"a equipe ensaiou a passagem", "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def _tell_back(
    client: httpx.AsyncClient, session_id: str, *, take_id: str, starts_ms: int, ends_ms: int
) -> None:
    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("trecho.m4a", b"um trecho contado de volta", "audio/mp4")},
    )
    assert told.status_code == 200, told.text


async def _press_terminei(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/finish", headers={"X-Room-Key": KEY}
    )


async def _a_passage_told_back(client: httpx.AsyncClient) -> tuple[str, str]:
    """One rehearsal, one stretch told back — the smallest press that reaches a verdict."""
    session_id = await _open_session(client)
    take_id = await _record(client, session_id)
    client.said.append("Noemi mandou Rute voltar.")  # type: ignore[attr-defined]
    await _tell_back(client, session_id, take_id=take_id, starts_ms=0, ends_ms=9000)
    return session_id, take_id


async def _what_the_room_said(db: AsyncSession, session_id: str) -> list[str]:
    """The guide's side of the conversation a facilitator reads, in order."""
    session = await get_session(db, session_id)
    return [
        message.get("text", "")
        for message in (session.messages or [])
        if message.get("role") == "guide"
    ]


@pytest.mark.asyncio
async def test_a_second_terminei_with_nothing_new_consults_no_model(
    client: httpx.AsyncClient, consulted: Consulted
) -> None:
    """Case 1. The same question, already answered, is not paid for twice.

    Counted across every model the route can reach, because skipping only the analyst still
    leaves the validator and the spoken synthesis running on every press.
    """
    session_id, _ = await _a_passage_told_back(client)

    first = await _press_terminei(client, session_id)
    assert first.status_code == 200, first.text
    after_first = consulted.total
    assert after_first > 0, "the first press must actually reach the models"

    again = await _press_terminei(client, session_id)
    assert again.status_code == 200, again.text

    assert consulted.total == after_first


@pytest.mark.asyncio
async def test_a_second_terminei_does_not_write_a_second_exchange(
    client: httpx.AsyncClient, db_session: AsyncSession, consulted: Consulted
) -> None:
    """Case 2. The transcript is a record of what happened, not of how often it was asked.

    A doubled turn reads as the room having spoken twice to the team, which it did not.
    """
    session_id, _ = await _a_passage_told_back(client)

    await _press_terminei(client, session_id)
    after_first = await _what_the_room_said(db_session, session_id)
    assert len(after_first) == 1, after_first

    await _press_terminei(client, session_id)

    assert await _what_the_room_said(db_session, session_id) == after_first


@pytest.mark.asyncio
async def test_a_terminei_after_something_new_was_told_back_does_run(
    client: httpx.AsyncClient, db_session: AsyncSession, consulted: Consulted
) -> None:
    """Case 3. Control, and the direction that hurts more when it breaks.

    A guard that cannot tell "asked again" from "told more" leaves a team that did real work
    with no way to be judged on it.
    """
    session_id, take_id = await _a_passage_told_back(client)

    await _press_terminei(client, session_id)
    after_first = consulted.total
    said_after_first = await _what_the_room_said(db_session, session_id)

    client.said.append("Rute disse que ia junto.")  # type: ignore[attr-defined]
    await _tell_back(client, session_id, take_id=take_id, starts_ms=9000, ends_ms=21000)

    fresh = await _press_terminei(client, session_id)
    assert fresh.status_code == 200, fresh.text

    assert consulted.total > after_first
    assert len(await _what_the_room_said(db_session, session_id)) == len(said_after_first) + 1


@pytest.mark.asyncio
async def test_the_first_terminei_is_untouched(
    client: httpx.AsyncClient, db_session: AsyncSession, consulted: Consulted
) -> None:
    """Case 4. Control. Nothing about reaching a verdict the first time changes."""
    session_id, _ = await _a_passage_told_back(client)

    verdict = await _press_terminei(client, session_id)

    assert verdict.status_code == 200, verdict.text
    body = verdict.json()
    assert body["checked"] is True
    assert body["audio_url"]
    assert body["findings_remaining"] == 0
    assert consulted.analyst == 1
    assert consulted.speaker == 1
    assert len(await _what_the_room_said(db_session, session_id)) == 1
