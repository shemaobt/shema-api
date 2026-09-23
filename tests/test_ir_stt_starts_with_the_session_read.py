"""ENG-991: transcription starts beside the session read, not after it.

`get_session` used to finish before the audio was even handed to the transcriber, and Neon
is a 20-30 ms round trip away. Once a session's language has been seen once in this process,
a later turn starts transcription right beside that read instead of behind it, and cancels it
if the session turns out to be gone. The resend check (`answered_turn`) stays in front of
transcription rather than beside it: a resend that lands after the first request has already
finished re-runs from scratch, and a cancel some milliseconds later is not a guarantee a real
network call already sent to the transcriber never lands.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import OrderedDict
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import create_session
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import KEY, PREFIX, P

TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"


class _Model:
    """A Guide that always drafts one line and a Validator that always passes it."""

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


class _Voice:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        self.calls += 1
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/v/{self.calls}.mp3",
        )
        return entry, False


async def _hearing(*_: Any, **__: Any) -> HeardSpeech:
    return HeardSpeech(text=TEAM_ANSWER)


async def _noop_settle(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", _Model()
    )
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _Voice())
    monkeypatch.setattr(sessions_api, "heard_speech", _hearing)
    monkeypatch.setattr(sessions_api, "settle_coverage", _noop_settle)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _an_opening_turn(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    """A turn with no audio — the shape the app sends first, which reads the session too."""
    return await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})


async def _a_spoken_turn(
    client: httpx.AsyncClient, session_id: str, *, turn_id: str | None = None
) -> httpx.Response:
    data = {"turn_id": turn_id} if turn_id else {}
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        data=data,
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )


async def test_the_session_language_is_remembered_once_the_session_has_been_read(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sessions_api, "_LANGUAGE_MEMO", OrderedDict())
    session = await create_session(db_session, language="pt", pericope=P)

    opened = await _an_opening_turn(client, session.id)

    assert opened.status_code == 200, opened.text[:300]
    assert sessions_api._LANGUAGE_MEMO.get(session.id) == ("pt", None), (
        "a sessão foi lida e a língua dela não ficou guardada para o próximo turno"
    )


def test_the_memo_holds_at_most_a_thousand_and_twenty_four_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sessions_api, "_LANGUAGE_MEMO", OrderedDict())

    for n in range(sessions_api._LANGUAGE_MEMO_MAX + 5):
        sessions_api._remember_language(f"session-{n}", "pt", None)

    assert len(sessions_api._LANGUAGE_MEMO) == sessions_api._LANGUAGE_MEMO_MAX
    assert "session-0" not in sessions_api._LANGUAGE_MEMO, (
        "o memo cresceu sem teto, e a entrada mais antiga sobreviveu"
    )
    newest = f"session-{sessions_api._LANGUAGE_MEMO_MAX + 4}"
    assert newest in sessions_api._LANGUAGE_MEMO


class _HearingThatSignalsItStarted:
    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def __call__(self, *_: Any, **__: Any) -> HeardSpeech:
        self.started.set()
        return HeardSpeech(text=TEAM_ANSWER)


class _SessionReadThatWaitsToBeReleased:
    """The real `session_for_room_caller`, held open until the test says the STT has had
    its turn.

    A room-key caller names no project, so this resolves to the by-id read it always has —
    `session_for_room_caller` is the one entry point every caller shape now goes through.
    """

    def __init__(self, real_session_for_room_caller: Any) -> None:
        self._real = real_session_for_room_caller
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, db: AsyncSession, session_id: str, project_id: str | None) -> Any:
        self.entered.set()
        await asyncio.wait_for(self.release.wait(), timeout=1)
        return await self._real(db, session_id, project_id)


async def test_a_known_language_starts_transcription_before_the_session_read_finishes(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sessions_api, "_LANGUAGE_MEMO", OrderedDict())
    session = await create_session(db_session, language="pt", pericope=P)
    sessions_api._remember_language(session.id, session.language, None)

    hearing = _HearingThatSignalsItStarted()
    monkeypatch.setattr(sessions_api, "heard_speech", hearing)
    reads = _SessionReadThatWaitsToBeReleased(sessions_api.room.session_for_room_caller)
    monkeypatch.setattr(sessions_api.room, "session_for_room_caller", reads)

    async def _release_the_read_once_stt_has_started() -> None:
        await asyncio.wait_for(hearing.started.wait(), timeout=1)
        reads.release.set()

    answered, _ = await asyncio.gather(
        _a_spoken_turn(client, session.id), _release_the_read_once_stt_has_started()
    )

    assert answered.status_code == 200, (
        f"a leitura da sessão nunca terminava porque a transcrição não tinha começado: "
        f"{answered.text[:300]}"
    )


class _HearingThatWaitsToBeCancelled:
    """A transcription that never finishes on its own — only a cancel ends it."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False
        self.charged = False

    async def __call__(self, *_: Any, **__: Any) -> HeardSpeech:
        self.started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        self.charged = True
        return HeardSpeech(text=TEAM_ANSWER)


async def test_a_resend_with_a_warm_memo_never_calls_the_transcriber(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resend that lands after the first request has already finished is not joined by
    `answer_once` — it re-runs `_answer_the_turn` from scratch, so the resend check
    (`answered_turn`) has to be read before the language memo can start the transcriber,
    never beside it. A cancel some milliseconds later is not a guarantee a real network
    call already sent to the transcriber never lands, so this is the one read this ticket
    does not overlap."""
    monkeypatch.setattr(sessions_api, "_LANGUAGE_MEMO", OrderedDict())
    session = await create_session(db_session, language="pt", pericope=P)
    first = await _a_spoken_turn(client, session.id, turn_id="turno-1")
    assert first.status_code == 200, first.text[:300]

    calls = 0

    async def _hearing_that_counts(*_: Any, **__: Any) -> HeardSpeech:
        nonlocal calls
        calls += 1
        return HeardSpeech(text=TEAM_ANSWER)

    monkeypatch.setattr(sessions_api, "heard_speech", _hearing_that_counts)

    second = await _a_spoken_turn(client, session.id, turn_id="turno-1")

    assert second.status_code == 200, second.text[:300]
    assert second.json() == first.json(), "um reenvio tem de responder com o turno já dado"
    assert calls == 0, "a transcrição especulativa rodou para um turno já respondido"


async def test_a_missing_session_cancels_the_speculative_transcription_and_still_answers_404(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sessions_api, "_LANGUAGE_MEMO", OrderedDict())
    sessions_api._remember_language("sessao-fantasma", "pt", None)
    hearing = _HearingThatWaitsToBeCancelled()
    monkeypatch.setattr(sessions_api, "heard_speech", hearing)

    answered = await _a_spoken_turn(client, "sessao-fantasma")

    assert answered.status_code == 404, answered.text[:300]
    assert hearing.started.is_set(), (
        "a asserção só prova cancelamento se a transcrição especulativa tiver mesmo começado"
    )
    assert hearing.cancelled is True, (
        "a transcrição especulativa continuou correndo depois de a sessão não ser encontrada"
    )
    assert hearing.charged is False, (
        "a transcrição especulativa terminou e cobrou mesmo com a sessão inexistente"
    )


async def test_without_a_known_language_the_session_is_still_read_before_transcription_starts(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first turn a process sees for a session has nothing in the memo yet — same order
    as before this ticket: the session read finishes before transcription is ever started."""
    monkeypatch.setattr(sessions_api, "_LANGUAGE_MEMO", OrderedDict())
    session = await create_session(db_session, language="pt", pericope=P)

    hearing = _HearingThatSignalsItStarted()
    monkeypatch.setattr(sessions_api, "heard_speech", hearing)
    reads = _SessionReadThatWaitsToBeReleased(sessions_api.room.session_for_room_caller)
    monkeypatch.setattr(sessions_api.room, "session_for_room_caller", reads)

    async def _confirm_no_overlap_then_release() -> None:
        await asyncio.wait_for(reads.entered.wait(), timeout=1)
        await asyncio.sleep(0.05)  # give a wrongly-started speculative task a chance to run
        assert not hearing.started.is_set(), (
            "a transcrição começou antes de a sessão ser lida, mesmo sem a língua no memo"
        )
        reads.release.set()

    answered, _ = await asyncio.gather(
        _a_spoken_turn(client, session.id), _confirm_no_overlap_then_release()
    )

    assert answered.status_code == 200, answered.text[:300]
    assert hearing.started.is_set(), "a transcrição nunca chegou a rodar"


async def _slow_to_actually_cancel() -> None:
    """A stand-in for the STT task: its own cancellation handling takes a moment, the way a
    real network call's teardown would, so a test can reliably catch `_cancelled` mid-wait."""
    try:
        await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await asyncio.sleep(0.2)
        raise


async def test_cancelling_the_request_does_not_get_swallowed_while_stopping_the_stt() -> None:
    """`_cancelled` runs while `_answer_the_turn` itself is unwinding from a failure, so a
    cancellation of the request landing at that exact suspension point must reach the caller,
    never read as if it were the stopped transcription's own outcome."""
    hung = asyncio.create_task(_slow_to_actually_cancel())
    entered_cleanup = asyncio.Event()

    async def _cleaning_up() -> None:
        entered_cleanup.set()
        await sessions_api._cancelled(hung)

    request = asyncio.create_task(_cleaning_up())
    await asyncio.wait_for(entered_cleanup.wait(), timeout=1)
    await asyncio.sleep(0.05)  # _cancelled has called hung.cancel() and is now inside its wait
    request.cancel()

    with pytest.raises(asyncio.CancelledError):
        await request


async def test_a_read_that_cannot_be_let_go_still_cancels_the_speculative_transcription(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sessions_api, "_LANGUAGE_MEMO", OrderedDict())
    session = await create_session(db_session, language="pt", pericope=P)
    sessions_api._remember_language(session.id, session.language, None)
    hearing = _HearingThatWaitsToBeCancelled()
    monkeypatch.setattr(sessions_api, "heard_speech", hearing)
    commit = db_session.commit

    async def the_connection_drops() -> None:
        monkeypatch.setattr(db_session, "commit", commit)
        raise ConnectionResetError("a conexão caiu no COMMIT da leitura")

    monkeypatch.setattr(db_session, "commit", the_connection_drops)

    answered = await _a_spoken_turn(client, session.id)

    assert answered.status_code >= 500, answered.text[:300]
    assert hearing.started.is_set(), (
        "a asserção só prova cancelamento se a transcrição especulativa tiver mesmo começado"
    )
    assert hearing.cancelled is True, (
        "o COMMIT da leitura falhou fora do try e a transcrição especulativa ficou sem dono"
    )
    stranded = [
        task
        for task in asyncio.all_tasks()
        if task.get_coro().__name__ == "_timed_stt" and not task.done()
    ]
    assert stranded == []
