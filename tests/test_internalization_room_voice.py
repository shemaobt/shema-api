"""The one voice the team ever hears, and the bucket that keeps it.

The room speaks in a single configured voice, and the same sentence must never be bought
from ElevenLabs twice — not by a second worker, and not by the process that replaces this
one on the next deploy.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.services.internalization_room import synthesize_facilitator_speech

ROOM_VOICE_ID = "83Nae6GFQiNslSbuzmE7"
ROOM_MODEL = "eleven_turbo_v2_5"


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "elevenlabs_api_key": "fake-elevenlabs",
        "gcs_platform_bucket": "tripod-platform-test",
    }
    base.update(overrides)
    return Settings(**base)


def _ok(audio: bytes = b"audio") -> SimpleNamespace:
    return SimpleNamespace(status_code=200, content=audio, text="")


def _client(*responses: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(post=AsyncMock(side_effect=list(responses) or [_ok()]))


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


async def test_the_rooms_configured_voice_is_the_one_that_speaks() -> None:
    client = _client()
    store = MemoryStore()

    speech, cached = await synthesize_facilitator_speech(
        "Que bom ter vocês aqui.", client=client, store=store, settings=_settings()
    )

    assert speech.audio == b"audio"
    assert cached is False
    assert ROOM_VOICE_ID in client.post.await_args.args[0]


async def test_the_language_is_stated_rather_than_guessed() -> None:
    """`eleven_multilingual_v2` reads the language off the text; turbo obeys this field."""
    client = _client()

    await synthesize_facilitator_speech(
        "Vamos contar de novo?", client=client, store=MemoryStore(), settings=_settings()
    )

    body = client.post.await_args.kwargs["json"]
    assert body["language_code"] == "pt"
    assert body["model_id"] == ROOM_MODEL


async def test_the_delivery_is_tuned_rather_than_left_to_the_defaults() -> None:
    client = _client()

    await synthesize_facilitator_speech(
        "Eu escuto até o fim.", client=client, store=MemoryStore(), settings=_settings()
    )

    tuning = client.post.await_args.kwargs["json"]["voice_settings"]
    assert tuning["speed"] == pytest.approx(0.96)
    assert tuning["stability"] == pytest.approx(0.45)


async def test_a_repeated_line_is_never_bought_twice() -> None:
    client = _client(_ok(), _ok())
    store = MemoryStore()
    settings = _settings()

    _, first = await synthesize_facilitator_speech(
        "Eu escuto até o fim.", client=client, store=store, settings=settings
    )
    _, second = await synthesize_facilitator_speech(
        "Eu escuto até o fim.", client=client, store=store, settings=settings
    )

    assert (first, second) == (False, True)
    assert client.post.await_count == 1


async def test_a_cold_process_still_finds_the_line_in_the_bucket() -> None:
    """The old in-process cache started empty on every worker and every deploy."""
    warm = MemoryStore()
    await synthesize_facilitator_speech(
        "A sala continua aqui.", client=_client(), store=warm, settings=_settings()
    )

    cold = MemoryStore()
    cold.objects = dict(warm.objects)
    client = _client()

    _, cached = await synthesize_facilitator_speech(
        "A sala continua aqui.", client=client, store=cold, settings=_settings()
    )

    assert cached is True
    assert client.post.await_count == 0


async def test_retuning_the_voice_does_not_serve_the_old_delivery() -> None:
    store = MemoryStore()
    client = _client(_ok(b"firme"), _ok(b"mais-solto"))

    await synthesize_facilitator_speech(
        "Vamos juntos.", client=client, store=store, settings=_settings()
    )
    speech, cached = await synthesize_facilitator_speech(
        "Vamos juntos.",
        client=client,
        store=store,
        settings=_settings(internalization_room_voice_stability=0.9),
    )

    assert cached is False
    assert speech.audio == b"mais-solto"


async def test_a_different_voice_id_is_honoured() -> None:
    client = _client()

    await synthesize_facilitator_speech(
        "Outra voz.",
        client=client,
        store=MemoryStore(),
        settings=_settings(internalization_room_voice_id="OtherVoiceId123"),
    )

    assert "OtherVoiceId123" in client.post.await_args.args[0]
