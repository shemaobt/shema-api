"""How long the clip route spent at the door and at the bucket, and whether it voiced the clip.

The gate and the bucket are each stubbed to take a known time, so the two numbers in the line
can only have come from the route's own clock.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import re
import threading
import time
from hashlib import sha256
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import _deps
from app.api.internalization_room import voice as voice_api
from app.core.config import get_settings
from app.core.exceptions import DeviceRevoked
from app.services.internalization_room.voice_handles import to_handle
from app.services.platform import tts
from app.services.platform.tts import SpeechKey

PREFIX = "/api/internalization-room"
VOICED_HERE = "tts/RoomVoice/eleven_turbo_v2_5/mp3_44100_128/aaa111/voiced-here.mp3"
VOICED_ELSEWHERE = "tts/RoomVoice/eleven_turbo_v2_5/mp3_44100_128/bbb222/voiced-elsewhere.mp3"
NEVER_STORED = "tts/RoomVoice/eleven_turbo_v2_5/mp3_44100_128/ccc333/never-stored.mp3"
#: Well-formed base64, but not this room's own voice namespace — `from_handle` refuses it
#: the same way it refuses garbage, and neither should be answered before the gate.
FOREIGN_HANDLE = to_handle("tts/AnotherApp/m/f/x.mp3")
CLIP = b"x" * 1234
AUTH_MS = 100
BUCKET_MS = 100

synthesis = importlib.import_module(
    "app.services.internalization_room.synthesize_facilitator_speech"
)


class _SlowBucket:
    def __init__(self) -> None:
        self.asked: list[str] = []

    async def get(self, key: str) -> bytes | None:
        self.asked.append(key)
        await asyncio.sleep(BUCKET_MS / 1000)
        return None if key == NEVER_STORED else CLIP


async def _slow_gate(db: AsyncSession, credential: str) -> Any:
    await asyncio.sleep(AUTH_MS / 1000)
    return SimpleNamespace(project_id=None)


@pytest.fixture()
def bucket() -> _SlowBucket:
    return _SlowBucket()


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: _SlowBucket):
    from fastapi import FastAPI

    from app.api.internalization_room import _deps, router
    from app.api.internalization_room import voice as voice_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_voice_id", "RoomVoice", raising=False)
    monkeypatch.setattr(_deps, "authenticate_device", _slow_gate)
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


async def _fetch(client: httpx.AsyncClient, key: str) -> httpx.Response:
    return await client.get(
        f"{PREFIX}/voice/{to_handle(key)}", headers={"X-Device-Credential": "tablet"}
    )


async def _fetch_range(
    client: httpx.AsyncClient, key: str, range_header: str, **extra_headers: str
) -> httpx.Response:
    return await client.get(
        f"{PREFIX}/voice/{to_handle(key)}",
        headers={"X-Device-Credential": "tablet", "Range": range_header, **extra_headers},
    )


def _voice_get_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if "[voice-get]" in r.getMessage()]


async def test_a_clip_fetch_says_how_long_the_gate_and_the_bucket_each_took(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        fetched = await _fetch(client, VOICED_ELSEWHERE)

    assert fetched.status_code == 200, fetched.text
    lines = _voice_get_lines(caplog)
    assert len(lines) == 1, "a leitura do clipe nunca tinha sido cronometrada"
    spent = {name: int(ms) for name, ms in re.findall(r" (\w+)=(\d+)ms", lines[0])}
    assert spent["auth"] >= AUTH_MS, "a autenticação do tablet não era medida"
    assert spent["gcs"] >= BUCKET_MS
    assert spent["auth"] < AUTH_MS + BUCKET_MS, "o tempo do bucket caía na conta da porta"
    assert spent["gcs"] < AUTH_MS + BUCKET_MS, "o tempo da porta caía na conta do bucket"
    assert " bytes=1234 " in lines[0]
    assert lines[0].endswith(" same_instance=no range=full")


async def test_a_clip_this_instance_voiced_is_told_apart_from_one_voiced_elsewhere(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def _voiced(text: str, **_: Any) -> SpeechKey:
        return SpeechKey(key=VOICED_HERE, cached=False)

    monkeypatch.setattr(synthesis, "synthesize_speech_key", _voiced)
    await synthesis.synthesize_facilitator_speech("Vamos ouvir de novo.", language="pt")

    with caplog.at_level(logging.INFO):
        await _fetch(client, VOICED_HERE)
        await _fetch(client, VOICED_ELSEWHERE)

    here, elsewhere = _voice_get_lines(caplog)
    assert here.endswith(" same_instance=yes range=full"), (
        "ninguém sabia quantos clipes um cache em memória desta instância teria servido"
    )
    assert elsewhere.endswith(" same_instance=no range=full")


async def test_an_instance_up_for_months_remembers_only_its_latest_clips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _voiced(text: str, **_: Any) -> SpeechKey:
        return SpeechKey(key=f"tts/v/{text}.mp3", cached=False)

    monkeypatch.setattr(synthesis, "synthesize_speech_key", _voiced)
    monkeypatch.setattr(synthesis, "_VOICED_HERE", synthesis.OrderedDict())
    monkeypatch.setattr(synthesis, "_VOICED_HERE_KEPT", 2)

    for line in ("primeira", "segunda", "primeira", "terceira"):
        await synthesis.synthesize_facilitator_speech(line, language="pt")

    assert not synthesis.voiced_here("tts/v/segunda.mp3"), "o registro crescia sem limite"
    assert synthesis.voiced_here("tts/v/primeira.mp3"), "a fala repetida era a primeira a sair"
    assert synthesis.voiced_here("tts/v/terceira.mp3")


async def test_a_clip_the_bucket_does_not_hold_still_says_how_long_the_miss_took(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        fetched = await _fetch(client, NEVER_STORED)

    assert fetched.status_code == 404
    lines = _voice_get_lines(caplog)
    assert len(lines) == 1, "o clipe que o bucket não tinha sumia do cronômetro"
    missed = re.search(r" gcs=(\d+)ms bytes=0 same_instance=no range=full$", lines[0])
    assert missed is not None and int(missed.group(1)) >= BUCKET_MS


class _Elevenlabs:
    def __init__(self) -> None:
        self.spoken = 0

    async def post(self, *_: Any, **__: Any) -> SimpleNamespace:
        self.spoken += 1
        return SimpleNamespace(status_code=200, content=f"mp3-{self.spoken}".encode() * 100)


class _Written:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


async def _voiced_here(line: str, voice: _Elevenlabs) -> str:
    speech, _ = await synthesis.synthesize_facilitator_speech(
        line, language="pt", client=voice, store=_Written(), settings=get_settings()
    )
    return speech.key


@pytest.fixture()
def the_room_can_speak(monkeypatch: pytest.MonkeyPatch) -> _Elevenlabs:
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    return _Elevenlabs()


async def test_a_clip_fetched_right_after_it_was_voiced_here_never_reaches_the_bucket(
    client: httpx.AsyncClient,
    bucket: _SlowBucket,
    the_room_can_speak: _Elevenlabs,
    caplog: pytest.LogCaptureFixture,
) -> None:
    key = await _voiced_here("Vamos ouvir a parte de novo.", the_room_can_speak)

    with caplog.at_level(logging.INFO):
        fetched = await _fetch(client, key)

    assert fetched.status_code == 200, fetched.text
    assert fetched.content == b"mp3-1" * 100
    assert bucket.asked == [], (
        "o tablet pedia o clipe à mesma instância que acabara de gravá-lo, e ela ia buscá-lo "
        "no GCS em vez de entregar os bytes que ainda tinha na mão"
    )
    (line,) = _voice_get_lines(caplog)
    assert " gcs=0ms " in line


async def test_the_clips_kept_in_memory_are_bounded_by_bytes_the_oldest_leaving_first(
    client: httpx.AsyncClient,
    bucket: _SlowBucket,
    the_room_can_speak: _Elevenlabs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tts, "_FRESH_MAX_BYTES", 1000)
    oldest = await _voiced_here("Primeira fala.", the_room_can_speak)
    middle = await _voiced_here("Segunda fala.", the_room_can_speak)
    newest = await _voiced_here("Terceira fala.", the_room_can_speak)

    for key in (newest, middle, oldest):
        assert (await _fetch(client, key)).status_code == 200

    assert bucket.asked == [oldest], (
        "a memória de clipes crescia sem limite numa instância que fica de pé por semanas"
    )


async def test_a_clip_the_tablet_just_played_outlives_one_nobody_asked_for(
    client: httpx.AsyncClient,
    bucket: _SlowBucket,
    the_room_can_speak: _Elevenlabs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tts, "_FRESH_MAX_BYTES", 1000)
    played = await _voiced_here("Primeira fala.", the_room_can_speak)
    ignored = await _voiced_here("Segunda fala.", the_room_can_speak)
    assert (await _fetch(client, played)).status_code == 200
    await _voiced_here("Terceira fala.", the_room_can_speak)

    await _fetch(client, played)
    await _fetch(client, ignored)

    assert bucket.asked == [ignored], (
        "a memória esquecia pela ordem de gravação, e o clipe que o tablet acabara de "
        "tocar saía antes de um que ninguém pediu"
    )


class _RealisticSlowBucket:
    """Shaped like `GcsPlatformStore`: the blocking read runs on a thread via
    `asyncio.to_thread`, the same primitive production uses — so, exactly like
    production, cancelling the coroutine that awaits it does not stop the thread. This
    file cannot claim the read was stopped, only that its bytes never reached the client.
    """

    def __init__(self) -> None:
        self.entered = False

    async def get(self, key: str) -> bytes | None:
        self.entered = True
        return await asyncio.to_thread(self._blocking_read)

    def _blocking_read(self) -> bytes:
        time.sleep(0.05)
        return CLIP


async def test_a_revoked_credential_is_refused_with_zero_bytes_even_with_a_read_already_on_a_thread(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _revoked_gate(db: AsyncSession, credential: str) -> Any:
        await asyncio.sleep(0)  # a real device check awaits the database at least once
        raise DeviceRevoked("This device is no longer linked.")

    monkeypatch.setattr(_deps, "authenticate_device", _revoked_gate)
    bucket = _RealisticSlowBucket()
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: bucket)

    fetched = await _fetch(client, VOICED_ELSEWHERE)

    assert fetched.status_code == 403
    assert fetched.json()["code"] == "DEVICE_REVOKED"
    assert bucket.entered, "a leitura nem chegava a começar ao lado da porta"
    assert CLIP not in fetched.content, "os bytes do clipe chegaram numa resposta de recusa"


async def test_a_refusal_leaves_no_read_task_behind_once_the_download_on_its_thread_ends(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _revoked_gate(db: AsyncSession, credential: str) -> Any:
        await asyncio.sleep(0)
        raise DeviceRevoked("This device is no longer linked.")

    monkeypatch.setattr(_deps, "authenticate_device", _revoked_gate)
    bucket = _RealisticSlowBucket()
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: bucket)
    before = asyncio.all_tasks()

    fetched = await _fetch(client, VOICED_ELSEWHERE)

    assert fetched.status_code == 403
    for _ in range(100):
        leftover = asyncio.all_tasks() - before - {asyncio.current_task()}
        if not leftover:
            break
        await asyncio.sleep(0.01)
    assert not leftover, (
        "a leitura ficou pendurada depois que o download da thread terminou — a recusa "
        "só pode deixá-la viva enquanto a thread, que nenhum cancel alcança, ainda roda"
    )


async def test_when_the_semaphore_is_full_the_read_waits_for_the_gate_like_before(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(voice_api, "_SPECULATIVE_READS", asyncio.Semaphore(0))
    bucket = _EventGatedBucket()
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: bucket)
    observed_while_still_at_the_gate = []

    async def _gate_that_peeks(db: AsyncSession, credential: str) -> Any:
        await asyncio.sleep(AUTH_MS / 1000)
        observed_while_still_at_the_gate.append(bucket.entered.is_set())
        return SimpleNamespace(project_id=None)

    monkeypatch.setattr(_deps, "authenticate_device", _gate_that_peeks)

    fetched = await _fetch(client, VOICED_ELSEWHERE)

    assert fetched.status_code == 200
    assert observed_while_still_at_the_gate == [False], (
        "a leitura começava mesmo com o semáforo cheio, disputando threads com o upload "
        "da voz por um pedido que talvez nem passasse na porta"
    )


async def test_a_revoked_credential_refuses_a_foreign_handle_before_the_bucket_gets_a_say(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _revoked_gate(db: AsyncSession, credential: str) -> Any:
        await asyncio.sleep(0)
        raise DeviceRevoked("This device is no longer linked.")

    monkeypatch.setattr(_deps, "authenticate_device", _revoked_gate)

    fetched = await client.get(
        f"{PREFIX}/voice/{FOREIGN_HANDLE}", headers={"X-Device-Credential": "tablet"}
    )

    assert fetched.status_code == 403, (
        "um handle que não decodifica respondia antes da porta, e a recusa virava um 404 "
        "que não diz nada sobre a credencial"
    )
    assert fetched.json()["code"] == "DEVICE_REVOKED"


async def test_no_credential_gets_401_not_404_on_a_foreign_handle(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        get_settings(), "internalization_room_api_key", "the-room-key", raising=False
    )

    fetched = await client.get(f"{PREFIX}/voice/{FOREIGN_HANDLE}")

    assert fetched.status_code == 401, (
        "sem nenhuma credencial, um handle que não decodifica ainda assim virava 404 antes "
        "da porta, o que diz a quem não tem credencial nenhuma se o handle é nosso"
    )


async def test_an_unrecognised_credential_gets_401_not_404_on_a_foreign_handle(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _unrecognised_gate(db: AsyncSession, credential: str) -> Any:
        await asyncio.sleep(0)
        return None

    monkeypatch.setattr(_deps, "authenticate_device", _unrecognised_gate)

    fetched = await client.get(
        f"{PREFIX}/voice/{FOREIGN_HANDLE}", headers={"X-Device-Credential": "unknown"}
    )

    assert fetched.status_code == 401, (
        "uma credencial desconhecida também virava 404 antes da porta, num handle que "
        "não decodifica"
    )


class _EventGatedBucket:
    def __init__(self) -> None:
        self.entered = asyncio.Event()

    async def get(self, key: str) -> bytes | None:
        self.entered.set()
        return CLIP


async def test_the_read_begins_before_a_slow_gate_lets_the_caller_through(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    bucket = _EventGatedBucket()
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: bucket)
    observed_while_still_at_the_gate = []

    async def _gate_that_peeks(db: AsyncSession, credential: str) -> Any:
        await asyncio.sleep(AUTH_MS / 1000)
        observed_while_still_at_the_gate.append(bucket.entered.is_set())
        return SimpleNamespace(project_id=None)

    monkeypatch.setattr(_deps, "authenticate_device", _gate_that_peeks)

    fetched = await _fetch(client, VOICED_ELSEWHERE)

    assert fetched.status_code == 200
    assert observed_while_still_at_the_gate == [True], (
        "a leitura só começava depois que a porta liberava o pedido, e devia correr ao lado dela"
    )


async def test_refusals_that_never_let_the_read_start_give_every_speculative_permit_back(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    permits = asyncio.Semaphore(4)
    monkeypatch.setattr(voice_api, "_SPECULATIVE_READS", permits)

    for _ in range(5):
        refused = await client.get(f"{PREFIX}/voice/{to_handle(VOICED_ELSEWHERE)}")
        assert refused.status_code in (400, 401), refused.text[:200]

    assert permits._value == 4, (
        "uma recusa sem await cancelava a leitura antes do primeiro passo, e a licença "
        "que a rota tinha pego nunca voltava — quatro dessas e a leitura ao lado da porta "
        "morria para a instância inteira"
    )


class _HeldOnAThreadBucket:
    def __init__(self) -> None:
        self.release = threading.Event()

    async def get(self, key: str) -> bytes | None:
        return await asyncio.to_thread(self._blocking_read)

    def _blocking_read(self) -> bytes:
        self.release.wait(timeout=2)
        return CLIP


async def test_a_refused_read_keeps_its_permit_until_the_download_on_its_thread_ends(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _revoked_gate(db: AsyncSession, credential: str) -> Any:
        await asyncio.sleep(0.01)
        raise DeviceRevoked("This device is no longer linked.")

    permits = asyncio.Semaphore(1)
    monkeypatch.setattr(voice_api, "_SPECULATIVE_READS", permits)
    monkeypatch.setattr(_deps, "authenticate_device", _revoked_gate)
    bucket = _HeldOnAThreadBucket()
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: bucket)

    fetched = await _fetch(client, VOICED_ELSEWHERE)

    assert fetched.status_code == 403
    assert permits.locked(), (
        "a recusa devolvia a licença enquanto o download seguia na thread — o limite "
        "contava esperas, não threads, e recusas em rajada empilhavam downloads"
    )
    bucket.release.set()
    for _ in range(100):
        if not permits.locked():
            break
        await asyncio.sleep(0.01)
    assert not permits.locked(), "a licença não voltou depois que o download terminou"


async def test_a_full_clip_says_it_can_be_answered_by_range(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch(client, VOICED_ELSEWHERE)

    assert fetched.status_code == 200
    assert fetched.headers["accept-ranges"] == "bytes"


async def test_the_etag_comes_from_the_clips_key_not_a_hash_of_its_bytes(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch(client, VOICED_ELSEWHERE)

    assert fetched.status_code == 200
    assert fetched.headers["etag"] == sha256(VOICED_ELSEWHERE.encode()).hexdigest()[:32]
    assert fetched.headers["etag"] != sha256(CLIP).hexdigest()[:32]


async def test_a_range_inside_the_clip_returns_only_those_bytes(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch_range(client, VOICED_ELSEWHERE, "bytes=10-19")

    assert fetched.status_code == 206, fetched.text
    assert fetched.content == CLIP[10:20]
    assert fetched.headers["content-range"] == f"bytes 10-19/{len(CLIP)}"


async def test_an_open_range_returns_everything_from_its_start_to_the_end(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch_range(client, VOICED_ELSEWHERE, "bytes=1200-")

    assert fetched.status_code == 206, fetched.text
    assert fetched.content == CLIP[1200:]
    assert fetched.headers["content-range"] == f"bytes 1200-{len(CLIP) - 1}/{len(CLIP)}"


async def test_a_suffix_range_returns_only_the_last_bytes(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch_range(client, VOICED_ELSEWHERE, "bytes=-34")

    assert fetched.status_code == 206, fetched.text
    assert fetched.content == CLIP[-34:]
    assert fetched.headers["content-range"] == f"bytes {len(CLIP) - 34}-{len(CLIP) - 1}/{len(CLIP)}"


async def test_a_range_past_the_end_of_the_clip_is_refused_not_clamped(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch_range(client, VOICED_ELSEWHERE, f"bytes={len(CLIP)}-{len(CLIP) + 10}")

    assert fetched.status_code == 416, fetched.text
    assert fetched.headers["content-range"] == f"bytes */{len(CLIP)}"
    assert fetched.content == b""


async def test_multiple_ranges_are_ignored_not_refused(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch_range(client, VOICED_ELSEWHERE, "bytes=0-10,20-30")

    assert fetched.status_code == 200, fetched.text
    assert fetched.content == CLIP
    assert "content-range" not in fetched.headers


async def test_a_range_behind_a_stale_if_range_etag_is_ignored_not_honoured(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch_range(
        client, VOICED_ELSEWHERE, "bytes=10-19", **{"If-Range": "not-the-current-etag"}
    )

    assert fetched.status_code == 200, fetched.text
    assert fetched.content == CLIP
    assert "content-range" not in fetched.headers


async def test_the_voice_get_line_names_the_slice_it_served(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        fetched = await _fetch_range(client, VOICED_ELSEWHERE, "bytes=10-19")

    assert fetched.status_code == 206, fetched.text
    (line,) = _voice_get_lines(caplog)
    assert line.endswith(" same_instance=no range=10-19")


async def test_a_revoked_credential_is_still_refused_with_zero_bytes_when_a_range_is_asked(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _revoked_gate(db: AsyncSession, credential: str) -> Any:
        await asyncio.sleep(0)
        raise DeviceRevoked("This device is no longer linked.")

    monkeypatch.setattr(_deps, "authenticate_device", _revoked_gate)

    fetched = await _fetch_range(client, VOICED_ELSEWHERE, "bytes=0-10")

    assert fetched.status_code == 403
    assert fetched.json()["code"] == "DEVICE_REVOKED"
    assert CLIP not in fetched.content


async def test_a_range_whose_end_reaches_past_the_clip_is_clamped_to_its_last_byte(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch_range(client, VOICED_ELSEWHERE, "bytes=1200-9999")

    assert fetched.status_code == 206, fetched.text
    assert fetched.content == CLIP[1200:]
    assert fetched.headers["content-range"] == f"bytes 1200-{len(CLIP) - 1}/{len(CLIP)}"


async def test_a_zero_length_suffix_range_is_refused_not_served_inverted(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch_range(client, VOICED_ELSEWHERE, "bytes=-0")

    assert fetched.status_code == 416, fetched.text
    assert fetched.headers["content-range"] == f"bytes */{len(CLIP)}"
    assert fetched.content == b""


async def test_a_suffix_range_longer_than_the_clip_serves_the_whole_clip(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch_range(client, VOICED_ELSEWHERE, f"bytes=-{len(CLIP) + 9999}")

    assert fetched.status_code == 206, fetched.text
    assert fetched.content == CLIP
    assert fetched.headers["content-range"] == f"bytes 0-{len(CLIP) - 1}/{len(CLIP)}"


async def test_an_inverted_range_is_ignored_not_served_as_an_empty_slice(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch_range(client, VOICED_ELSEWHERE, "bytes=10-5")

    assert fetched.status_code == 200, fetched.text
    assert fetched.content == CLIP
    assert "content-range" not in fetched.headers


async def test_a_range_this_route_does_not_understand_is_ignored_not_refused(
    client: httpx.AsyncClient,
) -> None:
    fetched = await _fetch_range(client, VOICED_ELSEWHERE, "items=0-10")

    assert fetched.status_code == 200, fetched.text
    assert fetched.content == CLIP
    assert "content-range" not in fetched.headers
