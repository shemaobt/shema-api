"""A raised hand is kept and read back in text with the database let go.

The transcription runs after the answer, on a session the task opens for itself, so the double
wraps the factory that session comes from and reads `in_transaction()` on it when the
transcriber is called.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRQuestion, IRSession
from app.services.internalization_room import background
from app.services.internalization_room import questions as service

SAID = "por que Noemi voltou sozinha?"


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
