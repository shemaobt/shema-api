"""The opening turn as the app actually sends it.

A turn carries the team's recording, but the very first one has nothing to carry: the
session opens with the facilitator speaking. Asserting that `file` is optional on the
signature proves nothing — what matters is the shape of the request that leaves the
phone, which is where this broke.
"""

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.run_turn import TurnOutcome
from app.services.platform.tts import SynthesizedSpeech

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    async def _panorama(**_: Any) -> TurnOutcome:
        return TurnOutcome(
            speech="Bem-vindos.",
            transcript="",
            peer_cue=False,
            redrafts=0,
            issues=[],
            used_fail_safe=False,
        )

    async def _speech(_text: str) -> tuple[SynthesizedSpeech, bool]:
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/{get_settings().internalization_room_voice_id}/m/f/abc.mp3",
        )
        return entry, False

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _speech)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_the_opening_turn_carries_no_body_at_all(client: httpx.AsyncClient) -> None:
    created = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": "OV"}
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    opened = await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})

    assert opened.status_code == 200, (
        "a abertura sem corpo e o que o app envia; recusa-la deixa a sala muda e "
        f"parecendo sem rede — veio {opened.status_code}: {opened.text[:200]}"
    )
    assert opened.json()["audio_url"].startswith("/api/internalization-room/voice/")
