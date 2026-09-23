from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.config import Settings
from app.services.project_health.voice.elevenlabs_client import synthesize_speech


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
