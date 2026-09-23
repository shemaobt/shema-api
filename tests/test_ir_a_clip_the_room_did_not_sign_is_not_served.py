"""A clip address is served only when the room itself signed it."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.voice_handles import clip_url

PREFIX = "/api/internalization-room"
KEY = "tts/RoomVoice/m/f/a.mp3"
HANDLE = "dHRzL1Jvb21Wb2ljZS9tL2YvYS5tcDM"
SIGNATURE = "zuiUCdy6TUby_jXXqzbLVTCKmLfvZ5C4zFzx2QmI_oM"
CLIP = b"x" * 1234


class _Bucket:
    def __init__(self) -> None:
        self.asked: list[str] = []

    async def get(self, key: str) -> bytes | None:
        self.asked.append(key)
        return CLIP


async def _welcome(db: AsyncSession, credential: str) -> Any:
    return SimpleNamespace(project_id=None)


@pytest.fixture()
def bucket() -> _Bucket:
    return _Bucket()


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket):
    from fastapi import FastAPI

    from app.api.internalization_room import _deps, router
    from app.api.internalization_room import voice as voice_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_voice_id", "RoomVoice")
    monkeypatch.setattr(get_settings(), "internalization_room_clip_signing_key", "chave-de-teste")
    monkeypatch.setattr(_deps, "authenticate_device", _welcome)
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: bucket)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_the_address_the_room_signed_plays(client: httpx.AsyncClient) -> None:
    response = await client.get(clip_url(KEY), headers={"X-Device-Credential": "tablet"})

    assert response.status_code == 200
    assert response.content == CLIP, "o handle assinado não decodificava e a linha não tocava"


@pytest.mark.parametrize(
    "handle",
    [
        pytest.param(HANDLE, id="sem-assinatura"),
        pytest.param(f"{HANDLE}.{SIGNATURE[:-1]}A", id="assinatura-adulterada"),
        pytest.param(
            f"{HANDLE}.Pb0G9dxSb0-lefdl1R5IWGM0UiqKiUaLNVOfeC1D8NA", id="assinada-com-outra-chave"
        ),
        pytest.param(
            f"{HANDLE}.pVDpzX2LofccVF4Mi8Qu_YA8gY10_YMYb2zAQYq5WQA", id="assinatura-de-outro-clipe"
        ),
        pytest.param(f"{HANDLE}.é", id="assinatura-nao-ascii"),
        pytest.param(f"{HANDLE}.", id="assinatura-vazia"),
    ],
)
async def test_an_address_the_room_did_not_sign_is_no_clip_and_never_reaches_the_bucket(
    client: httpx.AsyncClient, bucket: _Bucket, handle: str
) -> None:
    response = await client.get(
        f"{PREFIX}/voice/{handle}", headers={"X-Device-Credential": "tablet"}
    )

    assert response.status_code == 404, "um handle fabricado tocava como se a sala o tivesse dado"
    assert bucket.asked == [], "o handle fabricado comprava uma leitura no bucket antes da recusa"
