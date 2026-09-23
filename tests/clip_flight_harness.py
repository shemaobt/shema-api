from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import clip_flight
from app.services.platform import tts
from tests.release_harness import KEY, PREFIX

GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam uns aos outros sobre ela?"


class Elevenlabs:
    def __init__(self, *renderings: bytes, failures: int = 0) -> None:
        self.renderings = list(renderings) or [b"the only rendering"]
        self.failures = failures
        self.failure_status = 503
        self.refused: dict[str, int] = {}
        self.delay = 0.0
        self.held = asyncio.Event()
        self.held.set()
        self.texts: list[str] = []

    async def post(self, *_: Any, json: dict[str, Any], **__: Any) -> SimpleNamespace:
        self.texts.append(json["text"])
        await self.held.wait()
        await asyncio.sleep(self.delay)
        if self.refused.get(json["text"]):
            self.refused[json["text"]] -= 1
            return SimpleNamespace(status_code=self.failure_status, content=b"", text="no")
        if self.failures:
            self.failures -= 1
            return SimpleNamespace(status_code=self.failure_status, content=b"", text="no")
        audio = self.renderings.pop(0) if len(self.renderings) > 1 else self.renderings[0]
        return SimpleNamespace(status_code=200, content=audio, text="")


class WriteOnceBucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.refusals = 0
        self.unreadable = 0

    async def get(self, key: str) -> bytes | None:
        if self.unreadable:
            self.unreadable -= 1
            raise OSError("the bucket could not be read")
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def put_once(self, key: str, data: bytes, content_type: str) -> bytes:
        if self.refusals:
            self.refusals -= 1
            raise OSError("the bucket refused the write")
        return self.objects.setdefault(key, data)


def voiced_through(
    voice: Callable[..., Awaitable[Any]],
    key_of: Callable[[str], str] = lambda text: (
        f"tts/voice/m/f/{hashlib.sha256(text.encode()).hexdigest()}.mp3"
    ),
) -> Callable[..., tuple[str, Callable[[], Coroutine[Any, Any, bytes]]]]:
    def to_come(text: str, *, language: str | None = None) -> tuple[str, Any]:
        async def voiced() -> bytes:
            await voice(text, language=language)
            return b"audio"

        return key_of(text), voiced

    return to_come


def another_instance() -> None:
    clip_flight.forget_flights()
    tts.forget_what_is_kept()


@asynccontextmanager
async def voice_room_client(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    *,
    elevenlabs: Elevenlabs,
    bucket: WriteOnceBucket,
) -> AsyncIterator[httpx.AsyncClient]:
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import voice as voice_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    monkeypatch.setattr(tts, "_make_client", lambda: elevenlabs)
    monkeypatch.setattr(tts, "_default_store", lambda _: bucket)
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: bucket)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Room-Key": KEY}
    ) as client:
        yield client
