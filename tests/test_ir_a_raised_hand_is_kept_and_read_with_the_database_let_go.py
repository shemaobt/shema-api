"""A raised hand is kept and read back in text with the database let go.

The audio is put in the bucket while the request is still open, so the bucket reads
`in_transaction()` on the request's own session. The transcription runs after the answer, on a
session the task opens for itself, so that double wraps the factory the session comes from.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRQuestion, IRSession
from app.services.internalization_room import background
from app.services.internalization_room import questions as service
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import KEY, PREFIX, TABLET
from tests.room_harness import room_client

SAID = "por que Noemi voltou sozinha?"
RECORDED = Path(__file__).parent / "fixtures" / "pergunta-1500ms.m4a"


async def test_a_question_is_transcribed_with_its_own_session_let_go_not_held_open(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_session.add(IRSession(id="sessao-1", pericope="P03", language="pt"))
    db_session.add(
        IRQuestion(
            id="pergunta-1",
            device_id="tablet-da-equipe-1",
            session_id="sessao-1",
            pericope="P03",
            audio_key="perguntas/pergunta-1.m4a",
        )
    )
    await db_session.commit()
    opens = background.AsyncSessionLocal
    of_its_own: list[AsyncSession] = []
    held: dict[str, bool] = {}

    def a_session_of_its_own() -> AsyncSession:
        of_its_own.append(opens())
        return of_its_own[-1]

    async def transcriber(audio: bytes, *, language: str, mime_type: str) -> str:
        held["stt"] = of_its_own[-1].in_transaction()
        return SAID

    monkeypatch.setattr(background, "AsyncSessionLocal", a_session_of_its_own)
    monkeypatch.setattr(service, "transcribe_speech", transcriber)

    await background.transcribe_question(question_id="pergunta-1", audio=b"uma pergunta")

    kept = await service.get_question(db_session, "pergunta-1")
    await db_session.refresh(kept)
    assert kept.transcript == SAID
    assert held == {"stt": False}, (
        "a transcrição da pergunta segurava a leitura da pergunta e da sessão aberta pelo STT"
    )


async def test_a_raised_hand_is_put_in_the_bucket_with_the_database_let_go_not_held_open(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_session.add(IRSession(id="sessao-1", pericope="P03", language="pt"))
    await db_session.commit()
    held: dict[str, bool] = {}

    class WatchedBucket(MemoryStore):
        async def put(self, key: str, data: bytes, content_type: str) -> None:
            held["put"] = db_session.in_transaction()
            await super().put(key, data, content_type)

    async def transcriber(audio: bytes, *, language: str, mime_type: str) -> str:
        return SAID

    bucket = WatchedBucket()
    monkeypatch.setattr(service, "_store", lambda *_, **__: bucket)
    monkeypatch.setattr(service, "transcribe_speech", transcriber)

    async with room_client(db_session, monkeypatch) as client:
        raised = await client.post(
            f"{PREFIX}/questions",
            params={"session_id": "sessao-1"},
            headers={"X-Room-Key": KEY, "X-Room-Device": TABLET},
            files={"file": ("pergunta.m4a", RECORDED.read_bytes(), "audio/mp4")},
        )

    assert raised.status_code == 200, raised.text
    assert held == {"put": False}, (
        "a mão levantada ia para o balde com a leitura da sessão ainda aberta"
    )
