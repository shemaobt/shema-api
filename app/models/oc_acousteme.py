from datetime import datetime

from pydantic import BaseModel


class AcoustemeArtifactResponse(BaseModel):
    """Queryable metadata for one audio's acousteme stream (no payload)."""

    audio_id: str
    codebook_version: str
    collection: str | None = None
    title: str | None = None
    status: str
    duration_sec: float | None = None
    num_frames: int | None = None
    hop_sec: float | None = None
    num_segments: int | None = None
    num_units: int | None = None
    distinct_units: int | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AcoustemeListItem(BaseModel):
    """Compact row for listing a collection (one entry per audio)."""

    audio_id: str
    codebook_version: str
    collection: str | None = None
    title: str | None = None
    status: str
    duration_sec: float | None = None
    num_frames: int | None = None

    model_config = {"from_attributes": True}


class AcoustemeStreamResponse(BaseModel):
    """Everything the frontend needs to load + chunk one stream.

    ``download_url`` is a short-lived signed GET URL for the gzipped JSON blob;
    the grid fields let the client lay out Small/Medium/Large chunks before the
    blob arrives. Chunk indices are a client-side view — never persisted.
    """

    audio_id: str
    codebook_version: str
    download_url: str
    expires_at: datetime
    content_encoding: str
    duration_sec: float | None = None
    num_frames: int | None = None
    hop_sec: float | None = None
    num_units: int | None = None
    granularity_frames: dict[str, int]


class AcoustemeAudioResponse(BaseModel):
    """Short-lived signed GET URL for the source audio file."""

    audio_id: str
    download_url: str
    expires_at: datetime
