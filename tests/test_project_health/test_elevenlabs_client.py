from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import UpstreamServiceError
from app.services.project_health.voice.elevenlabs_client import synthesize_speech, transcribe_audio


def _settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///./test.db",
        google_api_key="fake-google",
        ph_elevenlabs_api_key="fake-ph-elevenlabs",
    )


def _ok() -> SimpleNamespace:
    return SimpleNamespace(status_code=200, content=b"MP3DATA", text="")


def _stub_client() -> SimpleNamespace:
    return SimpleNamespace(post=AsyncMock(return_value=_ok()))


def _err(status: int, body: str = "boom") -> SimpleNamespace:
    return SimpleNamespace(status_code=status, content=b"", text=body, json=dict)


def _err_client(response: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(post=AsyncMock(return_value=response))


def _failing_client(error: Exception) -> SimpleNamespace:
    return SimpleNamespace(post=AsyncMock(side_effect=error))


async def test_the_output_format_reaches_elevenlabs_in_the_query_not_the_body() -> None:
    client = _stub_client()

    await synthesize_speech(
        "a phrase this test alone will ever ask ElevenLabs to speak",
        language="en-US",
        settings=_settings(),
        client=client,
    )

    _, kwargs = client.post.await_args
    assert kwargs["params"]["output_format"] == "mp3_44100_128"
    assert "output_format" not in kwargs["json"]


async def test_a_clip_cached_in_one_format_is_not_served_for_another() -> None:
    client = _stub_client()
    text = "a phrase this test alone asks for in two formats"
    low = _settings().model_copy(update={"elevenlabs_output_format": "mp3_22050_32"})

    await synthesize_speech(text, language="en-US", settings=_settings(), client=client)
    _, was_cached = await synthesize_speech(text, language="en-US", settings=low, client=client)

    assert was_cached is False
    assert client.post.await_count == 2


async def test_synthesize_speech_requires_api_key() -> None:
    s = _settings().model_copy(update={"ph_elevenlabs_api_key": ""})
    client = _stub_client()

    with pytest.raises(UpstreamServiceError):
        await synthesize_speech("hello", language="en-US", settings=s, client=client)


async def test_synthesize_speech_treats_a_rate_limit_or_outage_as_upstream_not_ours() -> None:
    client = _err_client(_err(429))

    with pytest.raises(UpstreamServiceError):
        await synthesize_speech("hello", language="en-US", settings=_settings(), client=client)


async def test_transcribe_audio_treats_a_rate_limit_or_outage_as_upstream_not_ours() -> None:
    client = _err_client(_err(503))

    with pytest.raises(UpstreamServiceError):
        await transcribe_audio(b"abc", filename="x.wav", settings=_settings(), client=client)


async def test_synthesize_speech_treats_a_dropped_connection_as_upstream_too() -> None:
    client = _failing_client(httpx.ConnectError("boom"))

    with pytest.raises(UpstreamServiceError):
        await synthesize_speech("hello", language="en-US", settings=_settings(), client=client)


async def test_transcribe_audio_treats_a_dropped_connection_as_upstream_too() -> None:
    client = _failing_client(httpx.ReadTimeout("boom"))

    with pytest.raises(UpstreamServiceError):
        await transcribe_audio(b"abc", filename="x.wav", settings=_settings(), client=client)
