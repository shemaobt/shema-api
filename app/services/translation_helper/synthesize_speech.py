from __future__ import annotations

import base64
import logging
import re

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.services.translation_helper.audio_cache import CachedAudio, audio_cache
from app.services.translation_helper.detect_language import detect_language_code

logger = logging.getLogger(__name__)

# Locale → ElevenLabs voice. Multilingual model speaks any supported language with
# any voice; per-locale entries pick gender/accent. Default is Sarah, the same
# multilingual voice the project_health interview facilitator uses
# (app/services/project_health/voice/voice_map.py) and confirmed accessible on
# this account. The v2 redesigned default voices (Aria, Sarah-MAC, Lily, etc.)
# are NOT available here — stick to v1-library IDs.
DEFAULT_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # Sarah — warm multilingual female

VOICE_MAP: dict[str, dict[str, str]] = {
    "en-US": {"voice_id": "21m00Tcm4TlvDq8ikWAM", "language_code": "en"},  # Rachel
    "en-GB": {"voice_id": "ThT5KcBeYPX3keUQqHPh", "language_code": "en"},  # Dorothy
    "es-ES": {"voice_id": DEFAULT_VOICE_ID, "language_code": "es"},
    "es-MX": {"voice_id": "pNInz6obpgDQGcFmaJgB", "language_code": "es"},  # Adam
    "fr-FR": {"voice_id": DEFAULT_VOICE_ID, "language_code": "fr"},
    "pt-BR": {"voice_id": DEFAULT_VOICE_ID, "language_code": "pt"},
    "de-DE": {"voice_id": DEFAULT_VOICE_ID, "language_code": "de"},
    "it-IT": {"voice_id": DEFAULT_VOICE_ID, "language_code": "it"},
    "ja-JP": {"voice_id": DEFAULT_VOICE_ID, "language_code": "ja"},
    "ko-KR": {"voice_id": DEFAULT_VOICE_ID, "language_code": "ko"},
    "zh-CN": {"voice_id": DEFAULT_VOICE_ID, "language_code": "zh"},
    "hi-IN": {"voice_id": DEFAULT_VOICE_ID, "language_code": "hi"},
    "ar-SA": {"voice_id": DEFAULT_VOICE_ID, "language_code": "ar"},
    "ru-RU": {"voice_id": DEFAULT_VOICE_ID, "language_code": "ru"},
    "nl-NL": {"voice_id": DEFAULT_VOICE_ID, "language_code": "nl"},
    "sv-SE": {"voice_id": DEFAULT_VOICE_ID, "language_code": "sv"},
    "da-DK": {"voice_id": DEFAULT_VOICE_ID, "language_code": "da"},
}

DEFAULT_LOCALE = "en-US"


_SENTENCE_RE = re.compile(r"[^.!?]*[.!?]+|[^.!?]+\Z", re.DOTALL)


def split_sentences(text: str) -> list[str]:
    """Split text into sentences. Mirrors the JS splitter in the UI so the
    backend's mark order matches the frontend's sentence index."""
    out: list[str] = []
    for match in _SENTENCE_RE.finditer(text):
        chunk = match.group(0).strip()
        if chunk:
            out.append(chunk)
    return out


def _resolve_voice(language_code: str, voice_id_override: str | None) -> dict[str, str]:
    config = VOICE_MAP.get(language_code) or VOICE_MAP[DEFAULT_LOCALE]
    if voice_id_override:
        return {"voice_id": voice_id_override, "language_code": config["language_code"]}
    return config


_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)

#: How many opening words identify a sentence. One is not enough: in "…does this boy
#: think he is? Does he think he will rule over us?" the second sentence's opening word
#: is a whole word inside the first, so a one-word anchor fires seconds early and the
#: error compounds down the message. Four words separate ordinary prose without
#: demanding so much that normalization can break the match.
_ANCHOR_WORDS = 4


def _opening_words(sentence: str) -> list[str]:
    """The sentence's first few words, case-folded."""
    return [m.group(0).casefold() for m in _WORD_RE.finditer(sentence)][:_ANCHOR_WORDS]


def _word_at(alignment_chars: list[str], j: int, word: str) -> int | None:
    """Index just past `word` if it sits whole at `j`, else `None`.

    Both boundaries are checked. Without the leading one an anchor can land mid-word;
    without the trailing one a short opener like "do" matches inside "does".
    """
    n = len(alignment_chars)
    if j > 0 and alignment_chars[j - 1].isalnum():
        return None
    k = j
    for want in word:
        if k >= n or alignment_chars[k].casefold() != want:
            return None
        k += 1
    return None if k < n and alignment_chars[k].isalnum() else k


def _phrase_starts_at(alignment_chars: list[str], j: int, words: list[str]) -> bool:
    """Whether `words` run in order from `j`, separated by anything non-alphanumeric."""
    n = len(alignment_chars)
    k = j
    for index, word in enumerate(words):
        if index:
            while k < n and not alignment_chars[k].isalnum():
                k += 1
        after = _word_at(alignment_chars, k, word)
        if after is None:
            return False
        k = after
    return True


def _anchor_for(sentence: str, alignment_chars: list[str], cursor: int, n: int) -> int | None:
    """Index of the synthesized character where `sentence` begins, or `None`.

    Matching an opening phrase rather than a single character is what keeps the
    highlight on the voice, and why it is a phrase rather than one word is recorded on
    `_ANCHOR_WORDS`. A sentence carrying no word characters at all falls back to its
    first character, which is all there is to match on.
    """
    words = _opening_words(sentence)
    for j in range(cursor, n):
        if not alignment_chars[j].strip():
            continue
        if words:
            if _phrase_starts_at(alignment_chars, j, words):
                return j
        elif alignment_chars[j].casefold() == sentence.lstrip()[0].casefold():
            return j
    return None


def aggregate_sentence_marks(
    text: str,
    alignment_chars: list[str],
    alignment_starts: list[float],
) -> list[tuple[str, float]]:
    """Fold ElevenLabs character-level alignment into the sentence-mark shape
    consumed by the UI karaoke highlight (`s0`, `s1`, …).

    For each sentence from `split_sentences(text)`, find the first synthesized
    character whose case-folded value matches the sentence's first non-blank
    char, advancing a cursor so later sentences cannot match earlier positions.
    Falls back to a proportional time when matching cannot find an anchor.
    """
    sentences = split_sentences(text)
    if not sentences:
        return []
    n = min(len(alignment_chars), len(alignment_starts))
    if n == 0:
        return [(f"s{i}", 0.0) for i in range(len(sentences))]

    marks: list[tuple[str, float]] = []
    cursor = 0
    total = float(alignment_starts[n - 1])

    for idx, sentence in enumerate(sentences):
        stripped = sentence.lstrip()
        if not stripped:
            marks.append((f"s{idx}", 0.0))
            continue

        found = _anchor_for(sentence, alignment_chars, cursor, n)

        if found is None:
            time = total * (idx / len(sentences))
        else:
            time = float(alignment_starts[found])
            cursor = found + 1

        marks.append((f"s{idx}", time))

    return marks


_DEFAULT_CLIENT: httpx.AsyncClient | None = None


def _make_client() -> httpx.AsyncClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
    return _DEFAULT_CLIENT


async def synthesize_speech(
    text: str,
    *,
    language_code: str | None = None,
    voice_name: str | None = None,
    model_id: str | None = None,
    voice_settings: dict[str, float | bool] | None = None,
    client: httpx.AsyncClient | None = None,
    settings: Settings | None = None,
) -> tuple[CachedAudio, bool]:
    """Synthesize MP3 speech via ElevenLabs and return (cached entry, cached?).

    `voice_name` is passed through as an explicit ElevenLabs `voice_id` override
    when provided, preserving the existing public signature.
    """
    if not text or not text.strip():
        raise ValidationError("text must not be empty")

    if language_code is None:
        language_code = detect_language_code(text)

    cache_key = audio_cache.make_key(
        text, language_code, f"{voice_name}|{model_id}|{voice_settings}"
    )
    cached = audio_cache.get(cache_key)
    if cached is not None:
        return cached, True

    cfg = settings or get_settings()
    if not cfg.elevenlabs_api_key:
        raise ValidationError("ELEVENLABS_API_KEY is not configured")

    voice_cfg = _resolve_voice(language_code, voice_name)
    body: dict[str, object] = {
        "text": text,
        "model_id": model_id or cfg.elevenlabs_tts_model,
        "language_code": voice_cfg["language_code"],
        "output_format": cfg.elevenlabs_output_format,
    }
    if voice_settings:
        body["voice_settings"] = voice_settings
    url = f"{cfg.elevenlabs_base_url}/v1/text-to-speech/{voice_cfg['voice_id']}/with-timestamps"
    headers = {
        "xi-api-key": cfg.elevenlabs_api_key,
        "accept": "application/json",
    }

    http = client or _make_client()
    response = await http.post(url, json=body, headers=headers)
    if response.status_code >= 400:
        logger.warning(
            "ElevenLabs TTS failed: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise ValidationError(f"TTS request failed with status {response.status_code}")

    payload = response.json()
    audio_b64 = payload.get("audio_base64") or ""
    if not audio_b64:
        raise ValidationError("TTS returned empty audio content")
    audio_bytes = base64.b64decode(audio_b64)

    alignment = payload.get("normalized_alignment") or payload.get("alignment") or {}
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    timepoints = aggregate_sentence_marks(text, chars, starts)

    entry = audio_cache.put(cache_key, audio_bytes, mime_type="audio/mpeg", timepoints=timepoints)
    return entry, False
