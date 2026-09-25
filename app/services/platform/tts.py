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
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.services.platform.voices import language_hint, resolve_voice

logger = logging.getLogger(__name__)

MIME_TYPE = "audio/mpeg"

Upload = Callable[[], Awaitable[None]]

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

    async def put(self, key: str, data: bytes, content_type: str) -> bytes: ...


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

    audio = await voiced()
    # The route serves this as immutable for a day under a hash-addressed key, so a
    # synthesis that lost the write must hand back the rendering the bucket holds, not
    # its own: the loser's device would otherwise cache bytes no other instance serves.
    winner = await _cache_quietly(speech_store, key, audio)
    served = audio if winner is None else winner
    return SynthesizedSpeech(served, MIME_TYPE, etag_of(served), cached=False, key=key)


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
    uploads: list[Upload] | None = None,
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

    audio = await voiced()
    _remember_fresh(key, audio)
    upload = partial(_cache_and_correct, speech_store, key, audio)
    if uploads is None:
        await upload()
    else:
        uploads.append(upload)
    return SpeechKey(key, cached=False)


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


async def _cache_quietly(store: SpeechStore, key: str, audio: bytes) -> bytes | None:
    """Store the clip, but never fail the request over it. Returns the bytes now at `key`.

    We already paid ElevenLabs for these bytes. A missing bucket or a wrong IAM binding is
    an infrastructure problem — throwing a 500 here would bill the synthesis and hand the
    caller nothing.
    """
    try:
        winner = await store.put(key, audio, MIME_TYPE)
    except Exception:
        logger.exception("failed to cache TTS clip key=%s", key)
        return None
    _mark_kept(key)
    return winner


async def _cache_and_correct(store: SpeechStore, key: str, audio: bytes) -> None:
    winner = await _cache_quietly(store, key, audio)
    if winner is not None:
        _remember_fresh(key, winner)


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
