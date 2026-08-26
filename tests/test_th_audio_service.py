import base64
import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.services.translation_helper.audio_cache import AudioCache, audio_cache
from app.services.translation_helper.synthesize_speech import (
    VOICE_MAP,
    aggregate_sentence_marks,
    split_sentences,
    synthesize_speech,
)
from app.services.translation_helper.transcribe_audio import transcribe_audio


def _settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///./test.db",
        google_api_key="fake-google",
        elevenlabs_api_key="fake-elevenlabs",
    )


def _ok(json_payload: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(status_code=200, json=lambda: json_payload, text="")


def _err(status: int, body: str = "boom") -> SimpleNamespace:
    return SimpleNamespace(status_code=status, json=dict, text=body)


def _stt_response(text: str) -> SimpleNamespace:
    return _ok({"text": text, "language_code": "en", "language_probability": 0.99})


def _tts_response(
    audio: bytes,
    chars: list[str] | None = None,
    starts: list[float] | None = None,
) -> SimpleNamespace:
    starts = starts or []
    return _ok(
        {
            "audio_base64": base64.b64encode(audio).decode("ascii"),
            "normalized_alignment": {
                "characters": chars or [],
                "character_start_times_seconds": starts,
                "character_end_times_seconds": [s + 0.05 for s in starts],
            },
        }
    )


def _stub_client(response: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(post=AsyncMock(return_value=response))


# ---------------------------------------------------------------------------
# transcribe_audio
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcribe_audio_returns_trimmed_text() -> None:
    client = _stub_client(_stt_response("  hello world  "))
    text = await transcribe_audio(b"abc", filename="clip.wav", settings=_settings(), client=client)
    assert text == "hello world"
    assert client.post.await_count == 1


@pytest.mark.asyncio
async def test_transcribe_audio_hits_elevenlabs_url_with_scribe_model() -> None:
    client = _stub_client(_stt_response("ok"))
    await transcribe_audio(b"abc", filename="clip.wav", settings=_settings(), client=client)
    call = client.post.await_args
    url = call.args[0]
    assert url.endswith("/v1/speech-to-text")
    assert call.kwargs["data"]["model_id"] == "scribe_v2"
    assert call.kwargs["headers"]["xi-api-key"] == "fake-elevenlabs"


@pytest.mark.asyncio
async def test_transcribe_audio_sniffs_wav_when_filename_and_mime_missing() -> None:
    """B-4: unknown audio + no metadata should sniff the magic bytes, not fall back
    silently to audio/mpeg."""
    client = _stub_client(_stt_response("hello"))
    wav_header = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 16
    await transcribe_audio(wav_header, settings=_settings(), client=client)
    sent_mime = client.post.await_args.kwargs["files"]["file"][2]
    assert sent_mime == "audio/wav"


@pytest.mark.asyncio
async def test_transcribe_audio_warns_on_missing_mime(caplog) -> None:
    """B-4: when neither filename, mime, nor a sniffable magic byte is available,
    we should log a warning so the operator can debug a confused STT call."""
    client = _stub_client(_stt_response("ok"))
    caplog.set_level(logging.WARNING, logger="app.services.translation_helper.transcribe_audio")
    await transcribe_audio(
        b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b",
        settings=_settings(),
        client=client,
    )
    assert any("mime-type fallback" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_transcribe_audio_rejects_empty_payload() -> None:
    client = _stub_client(_stt_response("ignored"))
    with pytest.raises(ValidationError):
        await transcribe_audio(b"", filename="clip.wav", settings=_settings(), client=client)
    assert client.post.await_count == 0


@pytest.mark.asyncio
async def test_transcribe_audio_raises_when_empty_response() -> None:
    client = _stub_client(_stt_response(""))
    with pytest.raises(ValidationError):
        await transcribe_audio(b"abc", filename="x.wav", settings=_settings(), client=client)


@pytest.mark.asyncio
async def test_transcribe_audio_raises_when_api_error() -> None:
    client = _stub_client(_err(500, "internal"))
    with pytest.raises(ValidationError):
        await transcribe_audio(b"abc", filename="x.wav", settings=_settings(), client=client)


@pytest.mark.asyncio
async def test_transcribe_audio_requires_api_key() -> None:
    s = Settings(database_url="sqlite+aiosqlite:///./test.db", elevenlabs_api_key="")
    client = _stub_client(_stt_response("ignored"))
    with pytest.raises(ValidationError):
        await transcribe_audio(b"abc", filename="x.wav", settings=s, client=client)


# ---------------------------------------------------------------------------
# synthesize_speech
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesize_speech_caches_on_repeat_calls() -> None:
    audio_cache.clear()
    client = _stub_client(_tts_response(b"MP3DATA"))

    entry1, cached1 = await synthesize_speech(
        "hello", language_code="en-US", client=client, settings=_settings()
    )
    entry2, cached2 = await synthesize_speech(
        "hello", language_code="en-US", client=client, settings=_settings()
    )

    assert cached1 is False
    assert cached2 is True
    assert entry1.audio == b"MP3DATA"
    assert entry2.etag == entry1.etag
    assert client.post.await_count == 1


def _voice_id_in_url(call) -> str:
    url = call.args[0]
    # /v1/text-to-speech/{voice_id}/with-timestamps
    return url.split("/v1/text-to-speech/", 1)[1].split("/with-timestamps", 1)[0]


def _request_body(call) -> dict[str, Any]:
    return call.kwargs["json"]


@pytest.mark.asyncio
async def test_synthesize_speech_detects_portuguese_and_picks_pt_voice() -> None:
    audio_cache.clear()
    client = _stub_client(_tts_response(b"PT_MP3"))
    await synthesize_speech(
        "Olá, conte-me uma história sobre o Filho Pródigo, por favor.",
        client=client,
        settings=_settings(),
    )
    call = client.post.await_args
    assert _voice_id_in_url(call) == VOICE_MAP["pt-BR"]["voice_id"]
    assert _request_body(call)["language_code"] == "pt"


@pytest.mark.asyncio
async def test_synthesize_speech_detects_spanish_and_picks_es_voice() -> None:
    audio_cache.clear()
    client = _stub_client(_tts_response(b"ES_MP3"))
    await synthesize_speech(
        "Hola, cuéntame una historia sobre la oveja perdida, por favor.",
        client=client,
        settings=_settings(),
    )
    call = client.post.await_args
    assert _voice_id_in_url(call) == VOICE_MAP["es-ES"]["voice_id"]
    assert _request_body(call)["language_code"] == "es"


@pytest.mark.asyncio
async def test_synthesize_speech_falls_back_to_default_on_short_text() -> None:
    audio_cache.clear()
    client = _stub_client(_tts_response(b"OK_MP3"))
    await synthesize_speech("ok then", client=client, settings=_settings())
    call = client.post.await_args
    assert _voice_id_in_url(call) == VOICE_MAP["en-US"]["voice_id"]
    assert _request_body(call)["language_code"] == "en"


@pytest.mark.asyncio
async def test_synthesize_speech_explicit_language_overrides_detection() -> None:
    audio_cache.clear()
    client = _stub_client(_tts_response(b"FORCED_MP3"))
    await synthesize_speech(
        "Olá, conte-me uma história sobre o Filho Pródigo.",
        language_code="en-US",
        client=client,
        settings=_settings(),
    )
    call = client.post.await_args
    assert _voice_id_in_url(call) == VOICE_MAP["en-US"]["voice_id"]


@pytest.mark.asyncio
async def test_synthesize_speech_voice_name_overrides_voice_id() -> None:
    audio_cache.clear()
    client = _stub_client(_tts_response(b"CUSTOM_MP3"))
    await synthesize_speech(
        "hello",
        language_code="en-US",
        voice_name="custom_voice_xyz",
        client=client,
        settings=_settings(),
    )
    call = client.post.await_args
    assert _voice_id_in_url(call) == "custom_voice_xyz"


@pytest.mark.asyncio
async def test_synthesize_speech_sends_model_and_output_format() -> None:
    audio_cache.clear()
    client = _stub_client(_tts_response(b"MP3"))
    await synthesize_speech("hello", language_code="en-US", client=client, settings=_settings())
    body = _request_body(client.post.await_args)
    assert body["model_id"] == "eleven_multilingual_v2"
    assert body["output_format"] == "mp3_44100_128"


@pytest.mark.asyncio
async def test_synthesize_speech_rejects_empty_text() -> None:
    client = _stub_client(_tts_response(b""))
    with pytest.raises(ValidationError):
        await synthesize_speech("   ", client=client, settings=_settings())


@pytest.mark.asyncio
async def test_synthesize_speech_raises_when_no_audio() -> None:
    audio_cache.clear()
    client = _stub_client(_tts_response(b""))
    with pytest.raises(ValidationError):
        await synthesize_speech("hello world", client=client, settings=_settings())


@pytest.mark.asyncio
async def test_synthesize_speech_raises_when_api_error() -> None:
    audio_cache.clear()
    client = _stub_client(_err(429, "rate limit"))
    with pytest.raises(ValidationError):
        await synthesize_speech("hello", client=client, settings=_settings())


@pytest.mark.asyncio
async def test_synthesize_speech_requires_api_key() -> None:
    audio_cache.clear()
    s = Settings(database_url="sqlite+aiosqlite:///./test.db", elevenlabs_api_key="")
    client = _stub_client(_tts_response(b"MP3"))
    with pytest.raises(ValidationError):
        await synthesize_speech("hello", client=client, settings=s)


# ---------------------------------------------------------------------------
# Sentence-mark aggregation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesize_speech_aggregates_sentence_marks_from_alignment() -> None:
    audio_cache.clear()
    text = "Hello world. Second sentence here."
    chars = list("Hello world. Second sentence here.")
    starts = [i * 0.1 for i in range(len(chars))]
    client = _stub_client(_tts_response(b"MP3", chars=chars, starts=starts))

    entry, cached = await synthesize_speech(
        text, language_code="en-US", client=client, settings=_settings()
    )

    assert cached is False
    assert [m for m, _ in entry.timepoints] == ["s0", "s1"]
    assert entry.timepoints[0][1] == pytest.approx(0.0, abs=1e-6)
    # "Second" starts at index 13 in "Hello world. Second sentence here."
    assert entry.timepoints[1][1] == pytest.approx(1.3, abs=1e-6)


def test_aggregate_sentence_marks_basic() -> None:
    text = "Alpha. Beta."
    chars = list("Alpha. Beta.")
    starts = [i * 0.5 for i in range(len(chars))]
    marks = aggregate_sentence_marks(text, chars, starts)
    assert [m for m, _ in marks] == ["s0", "s1"]
    assert marks[0][1] == pytest.approx(0.0)
    # "B" is at index 7
    assert marks[1][1] == pytest.approx(3.5)


def test_aggregate_sentence_marks_handles_empty_alignment() -> None:
    marks = aggregate_sentence_marks("Hello. World.", [], [])
    assert marks == [("s0", 0.0), ("s1", 0.0)]


def test_aggregate_sentence_marks_handles_empty_text() -> None:
    assert aggregate_sentence_marks("", ["a"], [0.0]) == []


def test_aggregate_sentence_marks_falls_back_proportionally_when_no_match() -> None:
    # Alignment has none of the sentence-start chars (simulates heavy normalization).
    text = "Alpha. Beta. Gamma."
    chars = list("xxxxxxxxxxxx")  # no a/b/g
    starts = [i * 0.1 for i in range(len(chars))]
    marks = aggregate_sentence_marks(text, chars, starts)
    assert [m for m, _ in marks] == ["s0", "s1", "s2"]
    total = starts[-1]
    assert marks[0][1] == pytest.approx(0.0)
    assert marks[1][1] == pytest.approx(total * (1 / 3))
    assert marks[2][1] == pytest.approx(total * (2 / 3))


# ---------------------------------------------------------------------------
# split_sentences (unchanged helper)
# ---------------------------------------------------------------------------


def test_split_sentences_basic() -> None:
    assert split_sentences("Hello. World!") == ["Hello.", "World!"]
    assert split_sentences("One.  Two?  Three!") == ["One.", "Two?", "Three!"]


def test_split_sentences_trailing_remainder_without_punctuation() -> None:
    assert split_sentences("Hello. Trailing fragment") == [
        "Hello.",
        "Trailing fragment",
    ]


def test_split_sentences_handles_spanish_inverted_punctuation() -> None:
    assert split_sentences("¿Qué pasa? ¡Hola!") == ["¿Qué pasa?", "¡Hola!"]


def test_split_sentences_drops_empty_strings() -> None:
    assert split_sentences("") == []
    assert split_sentences("   ") == []


# ---------------------------------------------------------------------------
# AudioCache LRU (unchanged)
# ---------------------------------------------------------------------------


def test_audio_cache_lru_eviction() -> None:
    cache = AudioCache(max_entries=2, ttl_seconds=999)
    cache.put("a", b"1", "audio/mpeg")
    cache.put("b", b"2", "audio/mpeg")
    cache.put("c", b"3", "audio/mpeg")
    assert cache.get("a") is None
    assert cache.get("b") is not None
    assert cache.get("c") is not None


def test_aggregate_sentence_marks_anchors_on_the_whole_opening_word() -> None:
    """A sentence anchors where it really starts, not on a stray matching letter.

    Reported from the Joseph story: the highlight ran ahead of the voice and lit the
    wrong sentence. Anchoring on a single character finds the first `d` after the
    previous anchor, and "Does he think..." is preceded by "...does this boy think he
    is?" — so the mark landed on that earlier `does` and every later sentence drifted
    further ahead. Matching the opening word puts the anchor back on the sentence.
    """
    text = "Who does this boy think he is? Does he think he will rule over us?"
    chars = list(text)
    starts = [i * 0.1 for i in range(len(chars))]

    marks = aggregate_sentence_marks(text, chars, starts)

    assert [m for m, _ in marks] == ["s0", "s1"]
    # The second sentence begins at the "D" of "Does", index 31 — not at the "d" of
    # "does" inside the first sentence, which sits at index 4.
    assert marks[1][1] == pytest.approx(starts[text.index("Does he")])


def test_aggregate_sentence_marks_keeps_anchors_moving_forward() -> None:
    """Repeated openings must not collapse onto the same early position."""
    text = "Go now. Go again. Go once more."
    chars = list(text)
    starts = [i * 0.1 for i in range(len(chars))]

    marks = aggregate_sentence_marks(text, chars, starts)

    times = [t for _, t in marks]
    assert times == sorted(times)
    assert len(set(times)) == 3
