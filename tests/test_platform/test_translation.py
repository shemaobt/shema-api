from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.services.platform.translation import translate_to_english

PT = "a história começa no rio"


def _settings(**over: Any) -> Settings:
    fields: dict[str, Any] = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "google_api_key": "fake-google",
    }
    fields.update(over)
    return Settings(**fields)


def _client(*texts: str | Exception) -> SimpleNamespace:
    """A genai-shaped client: `client.aio.models.generate_content(...)` -> `.text`."""
    replies: list[Any] = [t if isinstance(t, Exception) else SimpleNamespace(text=t) for t in texts]
    generate = AsyncMock(side_effect=replies)
    return SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))


async def test_translates_the_spoken_answer_to_english() -> None:
    client = _client("the story starts by the river")

    result = await translate_to_english(
        PT, source_language="pt-BR", settings=_settings(), client=client
    )

    assert result == "the story starts by the river"
    prompt = client.aio.models.generate_content.await_args.kwargs["contents"]
    assert PT in prompt
    assert "Portuguese" in prompt


async def test_an_english_answer_is_not_sent_to_the_model_at_all() -> None:
    # Nothing to translate, and every call is billed: the cheapest translation is the one
    # that never leaves.
    client = _client("should not be used")

    result = await translate_to_english(
        "the story starts by the river",
        source_language="en-US",
        settings=_settings(),
        client=client,
    )

    assert result == "the story starts by the river"
    assert client.aio.models.generate_content.await_count == 0


async def test_a_silent_answer_is_not_sent_to_the_model_either() -> None:
    client = _client("should not be used")

    assert (
        await translate_to_english(
            "  ", source_language="pt-BR", settings=_settings(), client=client
        )
        == ""
    )
    assert client.aio.models.generate_content.await_count == 0


async def test_a_provider_failure_is_an_upstream_error() -> None:
    with pytest.raises(UpstreamServiceError):
        await translate_to_english(
            PT, source_language="pt-BR", settings=_settings(), client=_client(RuntimeError("503"))
        )


async def test_an_empty_reply_is_an_upstream_error_not_an_empty_draft() -> None:
    # An empty draft would look like a silent recording and be confirmed as one.
    with pytest.raises(UpstreamServiceError):
        await translate_to_english(
            PT, source_language="pt-BR", settings=_settings(), client=_client("")
        )


async def test_without_an_api_key_it_is_a_configuration_error() -> None:
    # Same shape as the TTS service: missing configuration is ours to fix, not the provider's.
    with pytest.raises(ValidationError):
        await translate_to_english(
            PT, source_language="pt-BR", settings=_settings(google_api_key=""), client=None
        )


async def test_a_rotated_key_is_not_served_by_the_cached_client(monkeypatch) -> None:
    """The key is baked into the client, so it belongs in what the cache is keyed by.

    Same rule as the TTS cache key carrying the output format: an input that changes the
    object cannot be left out, or the process serves the stale one until it restarts.
    """
    from app.services.platform import translation

    monkeypatch.setattr(translation, "_DEFAULT_CLIENT", None)
    monkeypatch.setattr(translation, "_DEFAULT_CLIENT_KEY", None)
    built: list[str] = []

    def _fake_client(*, api_key: str) -> SimpleNamespace:
        built.append(api_key)
        return _client("english", "english")

    monkeypatch.setattr(translation.genai, "Client", _fake_client)

    for key in ("k1", "k1", "k2"):
        await translate_to_english(
            PT, source_language="pt-BR", settings=_settings(google_api_key=key)
        )

    assert built == ["k1", "k2"]
