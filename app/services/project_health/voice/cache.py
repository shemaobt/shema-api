from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock


@dataclass
class CachedAudio:
    audio: bytes
    mime_type: str
    etag: str
    created_at: float


class AudioCache:
    """Thread-safe in-process LRU + TTL cache for synthesized speech."""

    def __init__(self, *, max_entries: int = 100, ttl_seconds: int = 24 * 60 * 60) -> None:
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._lock = Lock()
        self._entries: OrderedDict[str, CachedAudio] = OrderedDict()

    @staticmethod
    def make_key(text: str, language: str, voice_id: str, output_format: str) -> str:
        raw = f"{language}|{voice_id}|{output_format}|{text}".encode()
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def make_etag(audio: bytes) -> str:
        return hashlib.sha256(audio).hexdigest()[:32]

    def get(self, key: str) -> CachedAudio | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if time.time() - entry.created_at > self._ttl_seconds:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return entry

    def put(self, key: str, audio: bytes, mime_type: str) -> CachedAudio:
        entry = CachedAudio(
            audio=audio,
            mime_type=mime_type,
            etag=self.make_etag(audio),
            created_at=time.time(),
        )
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
        return entry


audio_cache = AudioCache()
