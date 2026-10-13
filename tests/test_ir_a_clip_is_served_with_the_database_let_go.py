"""The clip route lets go of its read before it waits on the bucket or on the voice.

Each double reads `in_transaction()` on the request's own session, the one the gate's credential
lookup and the session read ran on: a transaction still open there is a pooled connection held
idle through a GCS read or an ElevenLabs call.

The bucket is asked for the clip beside the gate, while the gate's own lookup is still running,
so a double that looked the moment it was called would find the read open whether the route lets
it go or not, and its red would say nothing about the route. Every double waits instead, up to a
ceiling, for the database to be let go, and records whether it still was not. The route cannot
pass a call it is waiting on, so the only let-go a double can see is one the route made before it
waited, and a route that never makes one keeps the double waiting out the whole ceiling.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import voice as voice_api
from app.services.internalization_room.synthesize_facilitator_speech import facilitator_speech_key
from app.services.internalization_room.voice_handles import clip_url
from app.services.platform import tts
from tests.room_harness import room_client

LINE = "Vamos ficar nesta cena. O que vocês contariam?"
CLIP = b"som guardado" * 100
CEILING_S = 2.0


async def _held(db: AsyncSession) -> bool:
    deadline = time.monotonic() + CEILING_S
    while db.in_transaction() and time.monotonic() < deadline:
        await asyncio.sleep(0.01)
    return db.in_transaction()


class _Bucket:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.objects: dict[str, bytes] = {}
        self.held: list[bool] = []

    async def get(self, key: str) -> bytes | None:
        self.held.append(await _held(self.db))
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        self.held.append(await _held(self.db))
        return key in self.objects

    async def put(self, key: str, data: bytes, content_type: str) -> bytes:
        self.held.append(await _held(self.db))
        self.objects[key] = data
        return data


@pytest.fixture()
def bucket(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> _Bucket:
    store = _Bucket(db_session)
    monkeypatch.setattr(tts, "_default_store", lambda _: store)
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: store)
    return store


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def test_a_clip_read_beside_the_gate_is_waited_on_with_the_database_let_go(
    client: httpx.AsyncClient, bucket: _Bucket
) -> None:
    key = facilitator_speech_key(LINE, language="pt")
    bucket.objects[key] = CLIP

    heard = await client.get(clip_url(key))

    assert heard.status_code == 200, heard.text[:300]
    assert heard.content == CLIP
    assert bucket.held == [False], (
        "a leitura do clipe esperava o GCS com a transação da porta ainda aberta"
    )


async def test_a_clip_read_only_once_the_gate_has_passed_is_read_with_the_database_let_go(
    client: httpx.AsyncClient, bucket: _Bucket, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(voice_api, "_SPECULATIVE_READS", asyncio.Semaphore(0))
    key = facilitator_speech_key(LINE, language="pt")
    bucket.objects[key] = CLIP

    heard = await client.get(clip_url(key))

    assert heard.status_code == 200, heard.text[:300]
    assert heard.content == CLIP
    assert bucket.held == [False], (
        "sem vaga para ler junto da porta, o clipe era lido depois dela com a transação aberta"
    )
