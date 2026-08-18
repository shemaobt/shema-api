"""A stretch the room could not transcribe is still the stretch the team told.

The route returned 200 above the store when the transcript came back empty — and `heard`
cannot tell a silent recording from a transcription outage, so an ElevenLabs hiccup
erased work. The app trusted the docstring's promise and kept no copy of its own.
"""

import base64
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRTake, IRTakeKind
from app.services.platform.storage import StoredObject

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
AUDIO = b"a equipe explicou este trecho em portugues"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    async def _silence(*_: Any, **__: Any) -> str:
        return ""

    monkeypatch.setattr(bt_api, "heard", _silence)

    class MemoryStore:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}

        async def get(self, key: str) -> bytes | None:
            return self.objects.get(key)

        async def put(self, key: str, data: bytes, content_type: str) -> None:
            self.objects[key] = data

        async def stat(self, key: str) -> Any:
            stored = self.objects.get(key)
            if stored is None:
                return None
            checksum = Checksum()
            checksum.update(stored)
            return StoredObject(
                size=len(stored),
                crc32c=base64.b64encode(checksum.digest()).decode("ascii"),
            )

    bucket = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: bucket)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.bucket = bucket  # type: ignore[attr-defined]
        yield c


async def test_a_stretch_with_no_transcript_is_still_stored(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    created = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": "P01"}
    )
    session_id = created.json()["session_id"]

    answer = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        files={"file": ("trecho.m4a", AUDIO, "audio/mp4")},
    )

    assert answer.status_code == 200
    assert answer.json()["captured"] is False

    rows = (
        (await db_session.execute(select(IRTake).where(IRTake.session_id == session_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].kind is IRTakeKind.RETRO
    assert list(client.bucket.objects.values()) == [AUDIO]  # type: ignore[attr-defined]
