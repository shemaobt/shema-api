from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.services.platform.stt import transcribe_speech

WEBM = b"\x1a\x45\xdf\xa3 fake webm/opus bytes"


def _settings(**over: Any) -> Settings:
    fields: dict[str, Any] = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "google_api_key": "fake-google",
        "elevenlabs_api_key": "fake-elevenlabs",
    }
    fields.update(over)
    return Settings(**fields)


def _ok(text: str = "a história começa no rio") -> SimpleNamespace:
    return SimpleNamespace(status_code=200, text="", json=lambda: {"text": text})


def _err(status: int) -> SimpleNamespace:
    return SimpleNamespace(status_code=status, text="boom", json=dict)


def _client(*responses: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(post=AsyncMock(side_effect=list(responses) or [_ok()]))


async def test_transcribes_in_the_spoken_language() -> None:
    client = _client(_ok())

    text = await transcribe_speech(WEBM, language="pt-BR", settings=_settings(), client=client)

    assert text == "a história começa no rio"
    url, kwargs = client.post.await_args
    assert url[0].endswith("/v1/speech-to-text")
    assert kwargs["headers"]["xi-api-key"] == "fake-elevenlabs"
    assert kwargs["files"]["file"][1] == WEBM
    assert kwargs["files"]["file"][2] == "audio/webm"


async def test_the_language_hint_is_the_interview_language_not_a_fixed_one() -> None:
    client = _client(_ok(), _ok("the story starts by the river"))

    await transcribe_speech(WEBM, language="pt-BR", settings=_settings(), client=client)
    await transcribe_speech(WEBM, language="en-US", settings=_settings(), client=client)

    hints = [call.kwargs["data"]["language_code"] for call in client.post.await_args_list]
    assert hints == ["pt", "en"]


async def test_the_model_comes_from_settings_so_swapping_it_is_configuration() -> None:
    client = _client(_ok())

    await transcribe_speech(
        WEBM, language="pt-BR", settings=_settings(elevenlabs_stt_model="scribe_v1"), client=client
    )

    assert client.post.await_args.kwargs["data"]["model_id"] == "scribe_v1"


async def test_a_silent_take_transcribes_to_nothing_and_that_is_not_a_failure() -> None:
    # A recording with no speech is a real answer state, not an error: marking the whole job
    # failed over it would put a red row in front of the facilitator for a take that is simply
    # empty. The two legacy clients raise here; this one does not, deliberately.
    text = await transcribe_speech(
        WEBM, language="pt-BR", settings=_settings(), client=_client(_ok("   "))
    )

    assert text == ""


async def test_empty_audio_is_an_error() -> None:
    with pytest.raises(ValidationError):
        await transcribe_speech(b"", language="pt-BR", settings=_settings(), client=_client())


async def test_without_an_api_key_it_is_a_configuration_error() -> None:
    with pytest.raises(ValidationError):
        await transcribe_speech(
            WEBM,
            language="pt-BR",
            settings=_settings(elevenlabs_api_key=""),
            client=_client(),
        )


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_elevenlabs_unavailability_is_an_upstream_failure_not_a_client_error(
    status: int,
) -> None:
    with pytest.raises(UpstreamServiceError):
        await transcribe_speech(
            WEBM, language="pt-BR", settings=_settings(), client=_client(_err(status))
        )


async def test_a_malformed_request_to_elevenlabs_stays_a_business_error() -> None:
    with pytest.raises(ValidationError):
        await transcribe_speech(
            WEBM, language="pt-BR", settings=_settings(), client=_client(_err(422))
        )


@pytest.mark.parametrize("language", ["", "   ", "-BR"])
async def test_a_blank_language_never_reaches_the_provider(language: str) -> None:
    # An empty `language_code` is not the same request as sending no hint at all: the
    # engine is told to expect a language named nothing.
    client = _client(_ok())

    with pytest.raises(ValidationError):
        await transcribe_speech(WEBM, language=language, settings=_settings(), client=client)

    assert client.post.await_count == 0
