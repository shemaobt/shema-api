"""Enums for the annotation-studio app module.

Kept isolated from ``app.core.enums`` so the studio's collection semantics
(``pending``/``stored`` upload lifecycle, tier/sort vocabulary) never collide
with the oral-collector ``UploadStatus`` that already lives there.
"""

from enum import StrEnum


class AsStudioRole(StrEnum):
    ADMIN = "admin"
    FACILITATOR = "facilitator"


class AsTierName(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class AsPairSide(StrEnum):
    A = "a"
    B = "b"


class AsSortDimension(StrEnum):
    ONSET = "onset"
    CODA = "coda"


class AsSortRound(StrEnum):
    NORMAL = "normal"
    RELIABILITY = "reliability"


class AsAudioFormat(StrEnum):
    WEBM = "webm"
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"


class AsUploadStatus(StrEnum):
    PENDING = "pending"
    STORED = "stored"


class AsExportStatus(StrEnum):
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
