"""Platform speech synthesis (ElevenLabs), shared across apps.

Text + language -> MP3. The cache is **durable, in the generic bucket**, under a
content-addressed key — so every phrase is synthesized **once, forever, for every app**, and
a cold worker does not pay ElevenLabs again. That is the difference from the two clients
already in the repo (`project_health/voice/` and `translation_helper/synthesize_speech.py`),
which carry the SAME copy-pasted `AudioCache` class: an in-process LRU, 100 entries, 24h TTL,
that evaporates on every deploy.

> Those two do **not** use this service yet — migrating them is a follow-up (the
> project_health voice module has no tests today and is live product). Until then the repo
> has three paths to ElevenLabs, and that is known debt, not an oversight.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Any, Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.services.platform.voices import language_hint, resolve_voice

logger = logging.getLogger(__name__)

MIME_TYPE = "audio/mpeg"

_DEFAULT_CLIENT: httpx.AsyncClient | None = None

_PENDING_WARMUPS: set[asyncio.Task[None]] = set()

_FRESH_MAX_BYTES = 64 * 1024 * 1024
_FRESH: OrderedDict[str, bytes] = OrderedDict()

_KEPT_FOR_S = 3600
_KEPT: OrderedDict[str, float] = OrderedDict()


@dataclass(frozen=True)
class SynthesizedSpeech:
    audio: bytes
    mime_type: str
    etag: str
    #: Came from the bucket (ElevenLabs was not called).
    cached: bool
    #: Where the clip lives. Content-addressed, so it is also a stable public handle.
    key: str = ""


@dataclass(frozen=True)
class SpeechKey:
    key: str
    cached: bool


class SpeechStore(Protocol):
    """The bucket seam: tests pass an in-memory dict, no GCS."""

    async def get(self, key: str) -> bytes | None: ...

    async def exists(self, key: str) -> bool: ...

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def put_once(self, key: str, data: bytes, content_type: str) -> bytes: ...


def forget_what_is_kept() -> None:
    _KEPT.clear()
    _FRESH.clear()


def _remember_fresh(key: str, audio: bytes) -> None:
    _FRESH[key] = audio
    _FRESH.move_to_end(key)
    while sum(map(len, _FRESH.values())) > _FRESH_MAX_BYTES:
        _FRESH.popitem(last=False)


def _is_kept(key: str) -> bool:
    kept_at = _KEPT.get(key)
    return kept_at is not None and time.monotonic() - kept_at < _KEPT_FOR_S


def _mark_kept(key: str) -> None:
    now = time.monotonic()
    while _KEPT and now - next(iter(_KEPT.values())) >= _KEPT_FOR_S:
        _KEPT.popitem(last=False)
    _KEPT[key] = now
    _KEPT.move_to_end(key)


def cache_key(
    text: str,
    *,
    voice_id: str,
    model: str,
    output_format: str,
    voice_settings: Mapping[str, float | bool] | None = None,
) -> str:
    """Content-addressed key: same text + voice + model + format + tuning = same object.

    Every input that changes the bytes belongs here. `output_format` in particular: leave it
    out and changing the setting keeps serving the old clip in the old format forever, with
    the hardcoded MIME_TYPE hiding the mismatch. `voice_settings` is the same trap one level
    down — stability and speed reshape the delivery without touching text, voice or format.

    A caller that sends no tuning keeps the original key, so clips already in the bucket stay
    addressable.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if not voice_settings:
        return f"tts/{voice_id}/{model}/{output_format}/{digest}.mp3"
    canonical = json.dumps(dict(sorted(voice_settings.items())), separators=(",", ":"))
    tuning = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"tts/{voice_id}/{model}/{output_format}/{tuning}/{digest}.mp3"


async def synthesize_speech(
    text: str,
    *,
    language: str,
    voice_id: str | None = None,
    model: str | None = None,
    voice_settings: Mapping[str, float | bool] | None = None,
    api_key: str | None = None,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
    store: SpeechStore | None = None,
) -> SynthesizedSpeech:
    """Speak `text` in `language` (BCP-47 locale, e.g. `pt-BR`), serving from cache when possible.

    `settings`, `client` and `store` are injectable — that is what makes the service testable
    without network and without GCS.
    """
    key, speech_store, voiced = _addressed(
        text,
        language=language,
        voice_id=voice_id,
        model=model,
        voice_settings=voice_settings,
        api_key=api_key,
        settings=settings,
        client=client,
        store=store,
    )
    cached = await speech_store.get(key)
    if cached is not None:
        return SynthesizedSpeech(cached, MIME_TYPE, etag_of(cached), cached=True, key=key)

    audio, _ = await _try_to_keep(speech_store, key, await voiced())
    return SynthesizedSpeech(audio, MIME_TYPE, etag_of(audio), cached=False, key=key)


async def synthesize_speech_key(
    text: str,
    *,
    language: str,
    voice_id: str | None = None,
    model: str | None = None,
    voice_settings: Mapping[str, float | bool] | None = None,
    api_key: str | None = None,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
    store: SpeechStore | None = None,
) -> SpeechKey:
    key, speech_store, voiced = _addressed(
        text,
        language=language,
        voice_id=voice_id,
        model=model,
        voice_settings=voice_settings,
        api_key=api_key,
        settings=settings,
        client=client,
        store=store,
    )
    if _is_kept(key) or await speech_store.exists(key):
        return SpeechKey(key, cached=True)

    audio, kept = await _try_to_keep(speech_store, key, await voiced())
    if not kept:
        raise UpstreamServiceError("the clip could not be kept")
    _remember_fresh(key, audio)
    return SpeechKey(key, cached=False)


def speech_to_come(
    text: str,
    *,
    language: str,
    voice_id: str | None = None,
    model: str | None = None,
    voice_settings: Mapping[str, float | bool] | None = None,
    api_key: str | None = None,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
    store: SpeechStore | None = None,
) -> tuple[str, Callable[[], Coroutine[Any, Any, bytes]]]:
    key, speech_store, voiced = _addressed(
        text,
        language=language,
        voice_id=voice_id,
        model=model,
        voice_settings=voice_settings,
        api_key=api_key,
        settings=settings,
        client=client,
        store=store,
    )
    return key, partial(_voice_once, key, speech_store, voiced)


async def _voice_once(
    key: str, store: SpeechStore, voiced: Callable[[], Awaitable[bytes]]
) -> bytes:
    try:
        audio = await fetch_clip(key, store=store)
    except Exception:
        logger.warning("a clip could not be read back; voicing it: key=%s", key)
        audio = None
    if audio is None:
        audio = await store.put_once(key, await voiced(), MIME_TYPE)
        _mark_kept(key)
    _remember_fresh(key, audio)
    return audio


def warm_connection_in_background(*, api_key: str, settings: Settings | None = None) -> None:
    """Open a no-cost connection to ElevenLabs ahead of the synthesis call that will need it.

    Fire-and-forget: the caller does not await this, so a slow or failing warm-up never
    delays or breaks the turn it is meant to speed up. The task is kept in `_PENDING_WARMUPS`
    until it finishes, because an unreferenced `asyncio.Task` can be garbage-collected
    mid-flight, silently cancelling it before the connection ever opens.
    """
    if not api_key:
        # The synthesis refuses before the network when no key is configured
        # (`_addressed`); a warm-up with nothing to authenticate with has nothing to open.
        return
    task = asyncio.create_task(_warm_connection(api_key=api_key, settings=settings))
    _PENDING_WARMUPS.add(task)
    task.add_done_callback(_PENDING_WARMUPS.discard)


async def _warm_connection(*, api_key: str, settings: Settings | None) -> None:
    cfg = settings or get_settings()
    http = _make_client()
    try:
        await http.get(f"{cfg.elevenlabs_base_url}/v1/models", headers={"xi-api-key": api_key})
    except Exception as exc:
        logger.warning("ElevenLabs warm-up failed: %s", type(exc).__name__)


def _addressed(
    text: str,
    *,
    language: str,
    voice_id: str | None,
    model: str | None,
    voice_settings: Mapping[str, float | bool] | None,
    api_key: str | None,
    settings: Settings | None,
    client: httpx.AsyncClient | None,
    store: SpeechStore | None,
) -> tuple[str, SpeechStore, Callable[[], Awaitable[bytes]]]:
    if not text or not text.strip():
        raise ValidationError("text must not be empty")

    cfg = settings or get_settings()
    credential = api_key or cfg.elevenlabs_api_key
    if not credential:
        # ponytail: project_health uses a SECOND key (`ph_elevenlabs_api_key`), and the
        # internalization room now brings its own. A caller that passes none still falls
        # back to the shared one, so nothing that worked before needs to change.
        raise UpstreamServiceError("ELEVENLABS_API_KEY is not configured")

    voice = voice_id or resolve_voice(language)
    chosen_model = model or cfg.elevenlabs_tts_model
    key = cache_key(
        text,
        voice_id=voice,
        model=chosen_model,
        output_format=cfg.elevenlabs_output_format,
        voice_settings=voice_settings,
    )
    voiced = partial(
        _synthesize,
        text,
        voice_id=voice,
        language=language,
        model=chosen_model,
        voice_settings=voice_settings,
        cfg=cfg,
        client=client,
        api_key=credential,
    )
    return key, store or _default_store(cfg), voiced


async def fetch_clip(key: str, *, store: SpeechStore) -> bytes | None:
    """Read back a clip by the key `synthesize_speech` minted for it.

    Content-addressed keys never point at different bytes, which is what lets the route
    that serves them promise an immutable cache.
    """
    fresh = _FRESH.get(key)
    if fresh is not None:
        _FRESH.move_to_end(key)
        return fresh
    return await store.get(key)


async def _try_to_keep(store: SpeechStore, key: str, audio: bytes) -> tuple[bytes, bool]:
    """Write the clip once, never raising, and say whether the bucket kept it.

    The bytes that come back are the bucket's when it kept them — the first rendering
    written under the key, which may not be the caller's — and the caller's own when the
    write failed. What a failed write means is the caller's to decide, because it differs:
    `synthesize_speech` hands the audio straight back, so the bytes already paid for are
    still worth serving; `synthesize_speech_key` hands back only a key, and a key the bucket
    never kept is an address every instance answers with a 404, so it raises and the room
    reports an outage instead.
    """
    try:
        kept = await store.put_once(key, audio, MIME_TYPE)
    except Exception:
        logger.exception("failed to cache TTS clip key=%s", key)
        return audio, False
    _mark_kept(key)
    return kept, True


async def _synthesize(
    text: str,
    *,
    voice_id: str,
    language: str,
    cfg: Settings,
    client: httpx.AsyncClient | None,
    model: str,
    voice_settings: Mapping[str, float | bool] | None = None,
    api_key: str | None = None,
) -> bytes:
    body: dict[str, object] = {
        "text": text,
        "model_id": model,
        "language_code": language_hint(language),
    }
    if voice_settings:
        body["voice_settings"] = dict(voice_settings)

    http = client or _make_client()
    try:
        response = await http.post(
            f"{cfg.elevenlabs_base_url}/v1/text-to-speech/{voice_id}",
            json=body,
            params={"output_format": cfg.elevenlabs_output_format},
            headers={"xi-api-key": api_key or cfg.elevenlabs_api_key, "accept": MIME_TYPE},
        )
    except httpx.HTTPError as error:
        logger.warning("ElevenLabs TTS unreachable: %s", error)
        raise UpstreamServiceError(f"Speech request could not reach ElevenLabs: {error}") from error
    if response.status_code >= 400:
        logger.warning(
            "ElevenLabs TTS failed: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise _upstream_or_validation_error(response.status_code)

    return bytes(response.content)


def _upstream_or_validation_error(status_code: int) -> Exception:
    """Their outage is not our client's bad request.

    429 and 5xx mean ElevenLabs is rate limiting or down: that is an upstream failure (502),
    and dressing it as a 400 means the right alert never fires. Other 4xx really are a
    malformed request we sent, so they stay a business error.
    """
    message = f"TTS request failed with status {status_code}"
    if status_code == 429 or status_code >= 500:
        return UpstreamServiceError(message)
    return ValidationError(message)


def etag_of(audio: bytes) -> str:
    return hashlib.sha256(audio).hexdigest()[:32]


def _default_store(cfg: Settings) -> SpeechStore:
    from app.services.platform.storage import GcsPlatformStore

    return GcsPlatformStore(cfg)


def _make_client() -> httpx.AsyncClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(keepalive_expiry=60.0),
        )
    return _DEFAULT_CLIENT
