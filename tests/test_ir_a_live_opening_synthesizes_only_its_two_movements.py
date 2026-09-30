"""A live opening now speaks only its two movements, and waits for neither the whole line.

Before this file, `_voice_the_turn` synthesized the whole line and the two movements in
parallel on every two-movement opening, and `audio_url` was always the whole line's clip
even once both movements were ready — the segments were purely additive, and the reply
waited for whichever of the three came back last.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.sessions import create_session
from app.services.platform import tts

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"

WHOLE = "O todo da passagem.\n\nA cena e o convite."
FIRST = "O todo da passagem."
SECOND = "A cena e o convite."


class _Bucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def put(self, key: str, data: bytes, content_type: str) -> bytes:
        return self.objects.setdefault(key, data)


class _Elevenlabs:
    """Every call is recorded; a chosen text can be held back or refused on command."""

    def __init__(self, *, holds: str | None = None, refuses: str | None = None) -> None:
        self.calls: list[str] = []
        self._holds = holds
        self._refuses = refuses
        self.may_proceed = asyncio.Event()

    async def post(self, *_: Any, json: dict[str, Any], **__: Any) -> SimpleNamespace:
        text = json["text"]
        if text == self._holds:
            await asyncio.wait_for(self.may_proceed.wait(), timeout=2)
        self.calls.append(text)
        if text == self._refuses:
            return SimpleNamespace(status_code=503, content=b"", text="busy")
        return SimpleNamespace(status_code=200, content=f"audio-for-{text}".encode(), text="")


class _ElevenlabsWhereAMovementWaitsForTheWholeLine:
    """Each movement answers once the whole line has been asked for, or gives up waiting.

    Whether the whole line was under way by then is written down per movement, so a
    fallback that asks for it only after both movements came back reads as two falses
    rather than as a race the test happened to win.
    """

    def __init__(self, *, refuses: str) -> None:
        self.calls: list[str] = []
        self.whole_under_way: dict[str, bool] = {}
        self._refuses = refuses
        self._whole_started = asyncio.Event()

    async def post(self, *_: Any, json: dict[str, Any], **__: Any) -> SimpleNamespace:
        text = json["text"]
        self.calls.append(text)
        if text == WHOLE:
            self._whole_started.set()
        else:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._whole_started.wait(), timeout=0.5)
            self.whole_under_way[text] = self._whole_started.is_set()
        if text == self._refuses:
            return SimpleNamespace(status_code=503, content=b"", text="busy")
        return SimpleNamespace(status_code=200, content=f"audio-for-{text}".encode(), text="")


@pytest.fixture()
def bucket() -> _Bucket:
    return _Bucket()


@pytest.fixture(autouse=True)
async def _no_whole_line_outlives_its_test() -> AsyncIterator[None]:
    from app.services.internalization_room import clip_flight

    yield
    left = set(clip_flight._IN_FLIGHT.values())
    for task in left:
        task.cancel()
    if left:
        await asyncio.wait(left)
    clip_flight.forget_flights()


async def _client(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: _Elevenlabs | _ElevenlabsWhereAMovementWaitsForTheWholeLine,
    bucket: _Bucket,
) -> httpx.AsyncClient:
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    monkeypatch.setattr(tts, "_make_client", lambda: elevenlabs)
    monkeypatch.setattr(tts, "_default_store", lambda _: bucket)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _opens_in_two_movements(
    monkeypatch: pytest.MonkeyPatch, *, movements: list[str] | None = None
) -> None:
    from app.api.internalization_room import sessions as sessions_api
    from app.services.internalization_room.run_turn import TurnOutcome

    chosen = [FIRST, SECOND] if movements is None else movements

    async def _opening(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech=WHOLE, transcript="", movements=chosen)

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _opening)


def _whole_line_in_flight() -> asyncio.Task[bytes]:
    from app.services.internalization_room import clip_flight
    from app.services.internalization_room.synthesize_facilitator_speech import (
        facilitator_speech_to_come,
    )

    key, _ = facilitator_speech_to_come(WHOLE, language="pt")
    flight = clip_flight.in_flight(key)
    assert flight is not None, "a linha inteira nem chegou a ser agendada em segundo plano"
    return flight


async def test_a_live_opening_synthesizes_only_its_two_movements(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    elevenlabs = _Elevenlabs(holds=WHOLE)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )

    assert opened.status_code == 200
    assert elevenlabs.calls == [FIRST, SECOND], (
        "a resposta esperava pela linha inteira mesmo sem precisar de suas palavras"
    )
    body = opened.json()
    urls = [segment["audio_url"] for segment in body["segments"]]
    assert body["audio_url"] == urls[0], (
        "audio_url continuava sendo a fala inteira mesmo com os dois movimentos prontos"
    )


async def test_the_whole_line_is_voiced_in_the_background_so_a_repeat_costs_nothing(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    elevenlabs = _Elevenlabs(holds=WHOLE)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )
        assert opened.status_code == 200
        elevenlabs.may_proceed.set()
        again = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )

    assert again.status_code == 200
    assert elevenlabs.calls == [FIRST, SECOND, WHOLE], (
        "o diga de novo pagou a ElevenLabs outra vez por uma linha que já estava sendo feita"
    )


async def test_a_say_it_again_asked_while_the_whole_line_is_still_in_flight_joins_it(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    elevenlabs = _Elevenlabs(holds=WHOLE)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )
        assert opened.status_code == 200

        _whole_line_in_flight()

        again = asyncio.create_task(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY})
        )
        await asyncio.wait({again}, timeout=0.2)
        assert not again.done(), "o diga de novo respondeu sem esperar a linha inteira ainda em voo"

        elevenlabs.may_proceed.set()
        again_resp = await asyncio.wait_for(again, timeout=2)

    assert again_resp.status_code == 200, again_resp.text[:300]
    assert elevenlabs.calls.count(WHOLE) == 1, (
        "o diga de novo pediu a linha inteira de novo enquanto ela ainda estava em voo, em "
        "vez de se juntar à síntese já a caminho"
    )
    assert again_resp.json()["audio_url"], "o diga de novo voltou sem áudio nenhum"


async def test_a_cancelled_say_it_again_does_not_cancel_the_whole_line_it_joined(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    """Giving up on "say it again" must not reach into another request's synthesis.

    `_say_it_again` awaits the shared whole-line flight; a task suspended on
    `await other_task` ties its own cancellation to `other_task` (asyncio sets it as the
    `_fut_waiter` and cancels it too), so a client that stops waiting on its own "say it
    again" would cancel the opening's still-running background synthesis along with the
    clip it was about to cache — a request belonging to someone else.
    """
    elevenlabs = _Elevenlabs(holds=WHOLE)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )
        assert opened.status_code == 200

        whole_task = _whole_line_in_flight()

        again = asyncio.create_task(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY})
        )
        await asyncio.wait({again}, timeout=0.2)
        assert not again.done(), "o diga de novo respondeu sem esperar a linha inteira ainda em voo"

        again.cancel()
        await asyncio.wait({again})
        assert again.cancelled()
        assert not whole_task.done(), "a tarefa em voo terminou cedo demais para este teste"
        assert not whole_task.cancelled(), (
            "cancelar o diga de novo cancelou a síntese em voo de outra sessão"
        )

        elevenlabs.may_proceed.set()
        result = await asyncio.wait_for(whole_task, timeout=2)

    assert result == f"audio-for-{WHOLE}".encode(), (
        "a linha inteira não terminou nem guardou o clipe depois do cancelamento"
    )
    assert elevenlabs.calls.count(WHOLE) == 1


async def test_a_say_it_again_whose_whole_line_was_cancelled_falls_back_to_its_own_synthesis(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    """The shield keeps "say it again" out of the background task, not the other way round.

    A flight cancelled under a joined "say it again" reaches it as CancelledError, which
    `except Exception` does not catch. It must fall back to one synthesis of its own, the
    fallback promised for a flight that did not deliver, not answer with nothing.
    """
    elevenlabs = _Elevenlabs(holds=WHOLE)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )
        assert opened.status_code == 200
        whole_task = _whole_line_in_flight()

        again = asyncio.create_task(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY})
        )
        await asyncio.wait({again}, timeout=0.2)
        assert not again.done(), "o diga de novo respondeu sem esperar a linha inteira ainda em voo"

        whole_task.cancel()
        await asyncio.wait({whole_task})
        assert whole_task.cancelled()

        elevenlabs.may_proceed.set()
        again_resp = await asyncio.wait_for(again, timeout=2)

    assert again_resp.status_code == 200, again_resp.text[:300]
    assert again_resp.json()["audio_url"], (
        "com a linha inteira cancelada, o diga de novo voltou sem áudio em vez de sintetizar"
    )
    # The fake records a call only once it completes; the cancelled background call never
    # did, so the one recorded is the fallback's own synthesis.
    assert elevenlabs.calls.count(WHOLE) == 1, "o diga de novo não caiu na própria síntese"


async def test_a_stale_whole_line_callback_does_not_evict_a_newer_tasks_entry() -> None:
    """Two openings landing on the same whole line share one key; only one may hold it.

    Two sessions on the same pericope and language can produce the very same whole line,
    so a second flight can take the key a first one held. The first flight's own
    done-callback still fires after that — it must forget only the entry it put there,
    never whatever the second flight left behind, or a `_say_it_again` for the second
    session finds nothing to join and pays ElevenLabs again, the exact bug this file
    guards against, reached from two sessions instead of one.
    """
    from app.services.internalization_room import clip_flight

    async def _done() -> bytes:
        return b"audio"

    key = "tts/mesma-linha"
    stale_task = asyncio.create_task(_done())
    current_task = asyncio.create_task(_done())
    await stale_task
    await current_task
    clip_flight._IN_FLIGHT[key] = current_task

    clip_flight._landed(key, stale_task)

    assert clip_flight.in_flight(key) is current_task, (
        "o callback de uma tarefa antiga apagou a entrada da tarefa atual para a mesma chave"
    )

    clip_flight._landed(key, current_task)
    assert clip_flight.in_flight(key) is None


async def test_a_background_synthesis_failure_does_not_change_the_turns_answer(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    bucket: _Bucket,
    caplog: pytest.LogCaptureFixture,
) -> None:
    elevenlabs = _Elevenlabs(holds=WHOLE, refuses=WHOLE)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    with caplog.at_level(logging.WARNING, logger="app.services.internalization_room.clip_flight"):
        async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
            opened = await asyncio.wait_for(
                client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
                timeout=2,
            )
            assert opened.status_code == 200, (
                "a resposta da abertura dependia de uma síntese que roda em segundo plano"
            )
            elevenlabs.may_proceed.set()
            for _ in range(20):
                if WHOLE in elevenlabs.calls:
                    break
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.01)

    body = opened.json()
    urls = [segment["audio_url"] for segment in body["segments"]]
    assert body["audio_url"] == urls[0]
    assert elevenlabs.calls == [FIRST, SECOND, WHOLE]
    assert "a clip could not be voiced: UpstreamServiceError" in caplog.text, (
        "a falha da linha inteira que ninguém esperava sumiu sem deixar rastro no log"
    )


async def test_a_movement_that_cannot_be_voiced_falls_back_to_the_whole_line(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    elevenlabs = _Elevenlabs(refuses=SECOND)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )
        heard = await client.get(opened.json()["audio_url"], headers={"X-Room-Key": KEY})

    assert opened.status_code == 200
    assert elevenlabs.calls.count(WHOLE) == 1, "a fala inteira foi sintetizada mais de uma vez"
    body = opened.json()
    assert body["segments"] == [], "o fallback ainda devolvia os movimentos parciais"
    assert heard.content == f"audio-for-{WHOLE}".encode(), (
        "a fala inteira deveria ter voltado como o áudio do turno"
    )


async def test_a_refused_movement_finds_the_whole_line_already_under_way(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    elevenlabs = _ElevenlabsWhereAMovementWaitsForTheWholeLine(refuses=SECOND)
    _opens_in_two_movements(monkeypatch)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )

    assert opened.status_code == 200
    assert elevenlabs.whole_under_way[FIRST] and elevenlabs.whole_under_way[SECOND], (
        "a fala inteira só começava depois de os dois movimentos voltarem, e uma cena "
        "recusada pagava os movimentos e a fala inteira em série"
    )
    assert elevenlabs.calls.count(WHOLE) == 1, (
        "a mesma abertura sintetizou a fala inteira mais de uma vez"
    )
    assert opened.json()["segments"] == []


def _clip_behind(audio_url: str, bucket: _Bucket) -> bytes | None:
    from app.core.config import get_settings
    from app.services.internalization_room.voice_handles import from_handle

    key = from_handle(audio_url.rsplit("/", 1)[-1], settings=get_settings())
    return bucket.objects.get(key) if key else None


async def test_a_turn_without_movements_still_speaks_only_the_whole_line(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _Bucket
) -> None:
    elevenlabs = _Elevenlabs()
    _opens_in_two_movements(monkeypatch, movements=[])
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}),
            timeout=2,
        )

    assert opened.status_code == 200
    assert elevenlabs.calls == [WHOLE], (
        "um turno sem movimentos passou a sintetizar mais do que a fala inteira"
    )
    assert opened.json()["segments"] == []
