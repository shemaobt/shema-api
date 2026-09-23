"""What the team plays back is signed or fetched with the database let go.

The routes read on the request's own session before they ask storage for anything, so the
signature and the bucket read `in_transaction()` on that session when they are called.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.voice_handles import team_audio_url
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import KEY, PREFIX, a_claimed_device, team_headers
from tests.room_harness import rehearsed_in_parts, room_client


async def test_a_take_the_team_plays_back_is_signed_with_the_database_let_go(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings
    from app.services.internalization_room import takes as takes_service

    session, (part,) = await rehearsed_in_parts(db_session, 1)
    held: dict[str, bool] = {}

    async def signs(bucket: str, key: str, **_: object) -> str:
        held["sign"] = db_session.in_transaction()
        return f"https://armazenamento.exemplo/{bucket}/{key}?assinado"

    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", "balde-de-teste", raising=False)
    monkeypatch.setattr(takes_service, "generate_signed_download_url", signs)

    async with room_client(db_session, monkeypatch) as client:
        played = await client.get(
            f"{PREFIX}/sessions/{session.id}/takes/{part.id}/audio",
            headers={"X-Room-Key": KEY},
        )

    assert played.status_code == 307, played.text
    assert held == {"sign": False}, (
        "a leitura da sessão e do take ficava aberta enquanto o endereço era assinado"
    )


async def test_a_reply_the_team_plays_back_is_fetched_with_the_credential_read_let_go(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.internalization_room import questions as questions_service

    _, credential = await a_claimed_device(db_session)
    reply = "internalization-room/questions/pergunta-1/resposta-abc123.m4a"
    held: dict[str, bool] = {}

    class WatchedBucket(MemoryStore):
        async def get(self, key: str) -> bytes | None:
            held["get"] = db_session.in_transaction()
            return await super().get(key)

    bucket = WatchedBucket()
    bucket.objects[reply] = b"a facilitadora respondeu"
    monkeypatch.setattr(questions_service, "_store", lambda *_, **__: bucket)

    async with room_client(db_session, monkeypatch) as client:
        heard = await client.get(team_audio_url(reply), headers=team_headers(credential))

    assert heard.status_code == 200, heard.text
    assert held == {"get": False}, (
        "a leitura da credencial ficava aberta enquanto a resposta vinha do balde"
    )
