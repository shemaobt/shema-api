from __future__ import annotations

import base64
import json
import logging
import re

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.services.platform.tts import SpeechStore
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

#: Never fewer than this. A single word is what made the anchors ambiguous to begin with.
_MIN_ANCHOR_WORDS = 2


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
    if not words:
        target = sentence.lstrip()[0].casefold()
        for j in range(cursor, n):
            if alignment_chars[j].strip() and alignment_chars[j].casefold() == target:
                return j
        return None

    # Shortening the phrase before giving up. The match is exact against a stream the model
    # has already normalized, so a single reshaped word — a numeral spelled out, an
    # abbreviation expanded — would otherwise drop the whole sentence to the proportional
    # guess and put the highlight nowhere near the voice. Two words is the floor: one word
    # is what made the anchors ambiguous in the first place.
    # The floor governs how far a phrase may be truncated, not how short a sentence may be:
    # "Yes." and "Thank you." are whole sentences and must still anchor on what they have.
    floor = min(len(words), _MIN_ANCHOR_WORDS)
    for length in range(len(words), floor - 1, -1):
        prefix = words[:length]
        for j in range(cursor, n):
            if not alignment_chars[j].strip():
                continue
            if _phrase_starts_at(alignment_chars, j, prefix):
                return j
    return None


def aggregate_sentence_marks(
    text: str,
    alignment_chars: list[str],
    alignment_starts: list[float],
) -> list[tuple[str, float]]:
    """Fold ElevenLabs character-level alignment into the sentence-mark shape
    consumed by the UI karaoke highlight (`s0`, `s1`, …).

    For each sentence from `split_sentences(text)`, find where its opening words appear in
    the synthesized character stream — see `_anchor_for` — advancing a cursor so later
    sentences cannot match earlier positions. Falls back to a proportional time when no
    anchor is found.
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


def _durable_keys(cache_key: str) -> tuple[str, str]:
    """Bucket keys for a clip's audio and its sentence marks.

    The marks are a sidecar rather than an envelope so the audio object stays exactly the
    bytes the browser plays, addressable on its own.
    """
    return f"th-tts/{cache_key}.mp3", f"th-tts/{cache_key}.marks.json"


def _decode_marks(raw: bytes | None) -> list[tuple[str, float]]:
    """Sentence marks from their stored form, or an empty list if unreadable.

    Unreadable marks cost the karaoke highlight on one clip; they must never cost the
    audio, which is the part the listener actually needs.
    """
    if not raw:
        return []
    try:
        return [(str(mark), float(time)) for mark, time in json.loads(raw)]
    except Exception:
        logger.warning("discarding unreadable cached sentence marks")
        return []


async def _read_durable(
    store: SpeechStore, cache_key: str
) -> tuple[bytes, list[tuple[str, float]]] | None:
    """A previously synthesized clip from the bucket, or `None`.

    Never raises: a bucket that is missing or unreachable means a cache miss and a fresh
    synthesis, not a failed request.
    """
    audio_key, marks_key = _durable_keys(cache_key)
    try:
        audio = await store.get(audio_key)
        if audio is None:
            return None
        return audio, _decode_marks(await store.get(marks_key))
    except Exception:
        logger.exception("failed to read cached TTS clip key=%s", audio_key)
        return None


async def _write_durable(
    store: SpeechStore, cache_key: str, audio: bytes, timepoints: list[tuple[str, float]]
) -> None:
    """Store the clip, but never fail the request over it.

    ElevenLabs has already been paid for these bytes; a missing bucket or a wrong IAM
    binding would otherwise bill the synthesis and hand the caller nothing.
    """
    audio_key, marks_key = _durable_keys(cache_key)
    try:
        await store.put(audio_key, audio, "audio/mpeg")
        await store.put(marks_key, json.dumps(timepoints).encode("utf-8"), "application/json")
    except Exception:
        logger.exception("failed to cache TTS clip key=%s", audio_key)


def _default_store() -> SpeechStore:
    from app.services.platform.storage import GcsPlatformStore

    return GcsPlatformStore()


def _key_variant(
    settings: Settings,
    voice_name: str | None,
    model_id: str | None,
    voice_settings: dict[str, float | bool] | None,
) -> str:
    """Everything besides the text and language that changes the synthesized bytes.

    `output_format` belongs here and was missing. `platform/tts.py` states the trap plainly
    on the key it mints — leave the format out and changing the setting keeps serving the old
    clip in the old shape forever, with the hardcoded `audio/mpeg` hiding the mismatch. That
    was survivable while the cache lived in one process for a day; it became permanent the
    moment these clips started going to the bucket, so it is fixed here.

    `voice_settings` is canonicalized rather than interpolated: the old f-string took the
    dict's repr, so the same tuning written in a different order produced a different key and
    paid for the same audio twice.
    """
    tuning = json.dumps(dict(sorted((voice_settings or {}).items())), separators=(",", ":"))
    return "|".join(
        [
            voice_name or "",
            model_id or settings.elevenlabs_tts_model,
            settings.elevenlabs_output_format,
            tuning,
        ]
    )


async def synthesize_speech(
    text: str,
    *,
    language_code: str | None = None,
    voice_name: str | None = None,
    model_id: str | None = None,
    voice_settings: dict[str, float | bool] | None = None,
    client: httpx.AsyncClient | None = None,
    settings: Settings | None = None,
    store: SpeechStore | None = None,
) -> tuple[CachedAudio, bool]:
    """Synthesize MP3 speech via ElevenLabs and return (cached entry, cached?).

    Two caches sit in front of ElevenLabs. The in-process one answers repeat clicks on the
    same worker without a network hop; the bucket behind it is what makes a clip survive a
    deploy and be shared by every instance, which the in-process cache alone never could —
    `tripod-backend` scales to twenty of them, so a second click routinely landed on a cold
    worker and paid for the same audio twice.

    `voice_name` is passed through as an explicit ElevenLabs `voice_id` override
    when provided, preserving the existing public signature. `store` is injectable so tests
    exercise the caching without GCS.
    """
    if not text or not text.strip():
        raise ValidationError("text must not be empty")

    if language_code is None:
        language_code = detect_language_code(text)

    cfg = settings or get_settings()

    cache_key = audio_cache.make_key(
        text, language_code, _key_variant(cfg, voice_name, model_id, voice_settings)
    )
    cached = audio_cache.get(cache_key)
    if cached is not None:
        return cached, True

    speech_store = store or (_default_store() if cfg.gcs_platform_bucket else None)
    if speech_store is not None:
        durable = await _read_durable(speech_store, cache_key)
        if durable is not None:
            audio_bytes, timepoints = durable
            entry = audio_cache.put(
                cache_key, audio_bytes, mime_type="audio/mpeg", timepoints=timepoints
            )
            return entry, True

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
    if speech_store is not None:
        await _write_durable(speech_store, cache_key, audio_bytes, timepoints)
    return entry, False
