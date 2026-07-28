from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.services.platform.tts import cache_key, synthesize_speech
from app.services.platform.voices import VOICES, resolve_voice

MP3 = b"\xff\xfb\x90fake-mpeg-frame"
QUESTION = "Onde essa história acontece?"


def _settings(**over: Any) -> Settings:
    fields: dict[str, Any] = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "google_api_key": "fake-google",
        "elevenlabs_api_key": "fake-elevenlabs",
        "gcs_platform_bucket": "tripod-platform-test",
    }
    fields.update(over)
    return Settings(**fields)


def _ok(audio: bytes = MP3) -> SimpleNamespace:
    return SimpleNamespace(status_code=200, content=audio, text="")


def _err(status: int) -> SimpleNamespace:
    return SimpleNamespace(status_code=status, content=b"", text="boom")


def _client(*responses: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(post=AsyncMock(side_effect=list(responses) or [_ok()]))


class MemoryStore:
    """In-memory bucket — the seam that replaces GCS in tests."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.reads = 0
        self.writes = 0

    async def get(self, key: str) -> bytes | None:
        self.reads += 1
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.writes += 1
        self.objects[key] = data


async def test_synthesizes_and_returns_the_mp3() -> None:
    client = _client(_ok())
    store = MemoryStore()

    result = await synthesize_speech(
        QUESTION, language="pt-BR", settings=_settings(), client=client, store=store
    )

    assert result.audio == MP3
    assert result.mime_type == "audio/mpeg"
    assert result.cached is False
    assert client.post.await_count == 1

    url, kwargs = client.post.await_args
    assert VOICES["pt-BR"] in url[0]
    assert kwargs["json"]["text"] == QUESTION
    assert kwargs["json"]["model_id"] == "eleven_multilingual_v2"
    assert kwargs["headers"]["xi-api-key"] == "fake-elevenlabs"


async def test_second_call_with_same_text_does_not_hit_elevenlabs() -> None:
    """The heart of the issue: each question is synthesized ONCE, forever, for every app."""
    client = _client(_ok(), _ok())
    store = MemoryStore()

    first = await synthesize_speech(
        QUESTION, language="pt-BR", settings=_settings(), client=client, store=store
    )
    second = await synthesize_speech(
        QUESTION, language="pt-BR", settings=_settings(), client=client, store=store
    )

    assert client.post.await_count == 1  # ElevenLabs was called ONCE
    assert first.cached is False
    assert second.cached is True
    assert second.audio == first.audio
    assert store.writes == 1


async def test_the_cache_survives_the_process_because_it_lives_in_the_bucket() -> None:
    # A cold worker (new store, same bucket) still finds the object: this is what the
    # in-process LRU in project_health/translation_helper does NOT do.
    store = MemoryStore()
    await synthesize_speech(
        QUESTION, language="pt-BR", settings=_settings(), client=_client(_ok()), store=store
    )

    cold = MemoryStore()
    cold.objects = dict(store.objects)  # same bucket; different process
    client = _client(_ok())

    result = await synthesize_speech(
        QUESTION, language="pt-BR", settings=_settings(), client=client, store=cold
    )

    assert client.post.await_count == 0
    assert result.cached is True


async def test_the_key_is_addressed_by_content_voice_model_and_format() -> None:
    store = MemoryStore()
    await synthesize_speech(
        QUESTION, language="pt-BR", settings=_settings(), client=_client(_ok()), store=store
    )

    key = next(iter(store.objects))
    assert key == cache_key(
        QUESTION,
        voice_id=VOICES["pt-BR"],
        model="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    assert key.startswith(f"tts/{VOICES['pt-BR']}/eleven_multilingual_v2/mp3_44100_128/")
    assert key.endswith(".mp3")


async def test_changing_the_output_format_does_not_serve_the_old_clip() -> None:
    # `output_format` changes the BYTES: leave it out of the key and the bucket serves the
    # old-format clip forever — and the hardcoded content-type would not give it away.
    store = MemoryStore()
    client = _client(_ok(b"128kbps"), _ok(b"64kbps"))

    await synthesize_speech(
        QUESTION, language="pt-BR", settings=_settings(), client=client, store=store
    )
    second = await synthesize_speech(
        QUESTION,
        language="pt-BR",
        settings=_settings(elevenlabs_output_format="mp3_44100_64"),
        client=client,
        store=store,
    )

    assert client.post.await_count == 2
    assert len(store.objects) == 2
    assert second.audio == b"64kbps"


async def test_different_texts_are_different_clips() -> None:
    store = MemoryStore()
    client = _client(_ok(b"one"), _ok(b"two"))

    await synthesize_speech(
        "primeira", language="pt-BR", settings=_settings(), client=client, store=store
    )
    await synthesize_speech(
        "segunda", language="pt-BR", settings=_settings(), client=client, store=store
    )

    assert client.post.await_count == 2
    assert len(store.objects) == 2


async def test_the_same_text_in_another_language_uses_another_voice_and_clip() -> None:
    store = MemoryStore()
    client = _client(_ok(b"pt"), _ok(b"en"))

    await synthesize_speech(
        QUESTION, language="pt-BR", settings=_settings(), client=client, store=store
    )
    await synthesize_speech(
        QUESTION, language="en-US", settings=_settings(), client=client, store=store
    )

    assert client.post.await_count == 2
    assert len(store.objects) == 2
    urls = [call.args[0] for call in client.post.await_args_list]
    assert VOICES["pt-BR"] in urls[0]
    assert VOICES["en-US"] in urls[1]
    assert VOICES["pt-BR"] != VOICES["en-US"]  # NATIVE voices, not a single multilingual one


async def test_a_language_without_a_configured_voice_is_an_explicit_error() -> None:
    # Silently falling back to another language's voice would come out unintelligible.
    with pytest.raises(ValidationError):
        await synthesize_speech(
            QUESTION, language="ja-JP", settings=_settings(), client=_client(), store=MemoryStore()
        )


async def test_resolve_voice_accepts_the_base_language() -> None:
    assert resolve_voice("pt") == VOICES["pt-BR"]
    assert resolve_voice("en") == VOICES["en-US"]


async def test_empty_text_is_an_error() -> None:
    with pytest.raises(ValidationError):
        await synthesize_speech(
            "   ", language="pt-BR", settings=_settings(), client=_client(), store=MemoryStore()
        )


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_elevenlabs_unavailability_is_an_upstream_failure_not_a_client_error(
    status: int,
) -> None:
    # Their 429/5xx is not a bad request from the SPA: as a 400, the right alert never fires.
    store = MemoryStore()

    with pytest.raises(UpstreamServiceError):
        await synthesize_speech(
            QUESTION,
            language="pt-BR",
            settings=_settings(),
            client=_client(_err(status)),
            store=store,
        )

    assert store.writes == 0  # no half-clip in the cache


async def test_a_malformed_request_to_elevenlabs_stays_a_business_error() -> None:
    with pytest.raises(ValidationError):
        await synthesize_speech(
            QUESTION,
            language="pt-BR",
            settings=_settings(),
            client=_client(_err(422)),
            store=MemoryStore(),
        )


async def test_a_cache_write_failure_does_not_throw_away_the_audio_we_paid_for() -> None:
    # The window between merge and the two manual `gcloud` commands: with no bucket (or a
    # wrong IAM binding) the upload raises. We paid for the synthesis — a 500 burns money.
    class BrokenStore(MemoryStore):
        async def put(self, key: str, data: bytes, content_type: str) -> None:
            raise RuntimeError("404 bucket does not exist")

    result = await synthesize_speech(
        QUESTION, language="pt-BR", settings=_settings(), client=_client(_ok()), store=BrokenStore()
    )

    assert result.audio == MP3
    assert result.cached is False


async def test_without_an_api_key_it_is_a_configuration_error() -> None:
    with pytest.raises(ValidationError):
        await synthesize_speech(
            QUESTION,
            language="pt-BR",
            settings=_settings(elevenlabs_api_key=""),
            client=_client(),
            store=MemoryStore(),
        )
