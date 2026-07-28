import gzip
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AcoustemeStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.oc_acousteme import OC_AcoustemeArtifact
from app.models.oc_acousteme import AcoustemeAudioResponse, AcoustemeStreamResponse
from app.services.oral_collector.constants import GCS_OC_BUCKET
from app.services.oral_collector.gcs_utils import (
    generate_signed_download_url,
    upload_gcs_object,
)

logger = logging.getLogger(__name__)

# The acousteme grid is fixed by the tokenizer: 20 ms hop, 100-unit codebook.
# These are uniform across every audio — do not vary them per file.
ACOUSTEME_HOP_SEC = 0.02
ACOUSTEME_NUM_UNITS = 100

# Chunk-size presets (in frames) the frontend groups acoustemes by, mirroring the
# beads viewer's Small/Medium/Large. The smallest respects the 20 ms supervision
# grid; sizes are whole frames so chunk boundaries land on frame edges.
ACOUSTEME_GRANULARITY_FRAMES: dict[str, int] = {"small": 10, "medium": 25, "large": 50}

DOWNLOAD_URL_EXPIRY_MINUTES = 15


def acousteme_blob_path(audio_id: str, codebook_version: str) -> str:
    return f"acoustemes/{audio_id}/{codebook_version}.json.gz"


async def get_artifact(
    db: AsyncSession,
    audio_id: str,
    *,
    codebook_version: str | None = None,
) -> OC_AcoustemeArtifact:
    """Fetch one artifact pointer.

    With a pinned version, returns that exact row. Unpinned, "newest" means
    newest *usable* — the latest READY row — falling back to the latest of any
    status only when none are READY, so a failed newer ingest doesn't shadow a
    servable older version.

    Every consumer resolves "newest" through here, so the tiebreak lives here too:
    created_at is a transaction timestamp, so a batch re-clustering ingests two
    versions at the same instant, and the codebook keeps the winner deterministic.
    Without it, the listing and the play route can pick different versions of the
    same audio — and unit ids don't survive a codebook swap.
    """

    newest_first = (
        OC_AcoustemeArtifact.created_at.desc(),
        OC_AcoustemeArtifact.codebook_version.desc(),
    )
    base = select(OC_AcoustemeArtifact).where(OC_AcoustemeArtifact.audio_id == audio_id)
    if codebook_version is not None:
        stmt = base.where(OC_AcoustemeArtifact.codebook_version == codebook_version)
        artifact = (await db.execute(stmt)).scalars().first()
    else:
        ready = base.where(OC_AcoustemeArtifact.status == AcoustemeStatus.READY).order_by(
            *newest_first
        )
        artifact = (await db.execute(ready)).scalars().first()
        if artifact is None:
            latest = base.order_by(*newest_first)
            artifact = (await db.execute(latest)).scalars().first()

    if artifact is None:
        raise NotFoundError(f"No acousteme artifact for audio {audio_id}")
    return artifact


async def list_artifacts(db: AsyncSession, audio_id: str) -> list[OC_AcoustemeArtifact]:
    """List every codebook version available for an audio, newest first."""

    stmt = (
        select(OC_AcoustemeArtifact)
        .where(OC_AcoustemeArtifact.audio_id == audio_id)
        .order_by(OC_AcoustemeArtifact.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_by_collection(db: AsyncSession, collection: str) -> list[OC_AcoustemeArtifact]:
    """List one ready artifact per audio in a collection (e.g. 'terena-ruth').

    When multiple codebook versions exist for an audio, only the newest READY
    one is returned, so the collection stays one entry per audio_id.
    """

    stmt = (
        select(OC_AcoustemeArtifact)
        .where(
            OC_AcoustemeArtifact.collection == collection,
            OC_AcoustemeArtifact.status == AcoustemeStatus.READY,
        )
        .order_by(OC_AcoustemeArtifact.audio_id, OC_AcoustemeArtifact.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    seen: set[str] = set()
    latest_per_audio: list[OC_AcoustemeArtifact] = []
    for row in rows:
        if row.audio_id in seen:
            continue
        seen.add(row.audio_id)
        latest_per_audio.append(row)
    return latest_per_audio


async def get_stream(
    db: AsyncSession,
    audio_id: str,
    *,
    codebook_version: str | None = None,
) -> AcoustemeStreamResponse:
    """Return a signed download URL + grid metadata for the frontend."""

    artifact = await get_artifact(db, audio_id, codebook_version=codebook_version)
    if artifact.status != AcoustemeStatus.READY:
        raise ValidationError(
            f"Acousteme artifact for audio {audio_id} is not ready (status: {artifact.status})"
        )

    download_url = await generate_signed_download_url(
        artifact.gcs_bucket,
        artifact.gcs_object,
        expiry_minutes=DOWNLOAD_URL_EXPIRY_MINUTES,
        response_content_type="application/json",
    )
    expires_at = datetime.now(UTC) + timedelta(minutes=DOWNLOAD_URL_EXPIRY_MINUTES)

    return AcoustemeStreamResponse(
        audio_id=artifact.audio_id,
        codebook_version=artifact.codebook_version,
        download_url=download_url,
        expires_at=expires_at,
        content_encoding=artifact.content_encoding,
        duration_sec=artifact.duration_sec,
        num_frames=artifact.num_frames,
        hop_sec=artifact.hop_sec,
        num_units=artifact.num_units,
        granularity_frames=ACOUSTEME_GRANULARITY_FRAMES,
    )


async def get_audio_url(
    db: AsyncSession,
    audio_id: str,
    *,
    codebook_version: str | None = None,
) -> AcoustemeAudioResponse:
    """Return a signed download URL for the source audio file."""

    artifact = await get_artifact(db, audio_id, codebook_version=codebook_version)
    if not artifact.audio_bucket or not artifact.audio_object:
        raise NotFoundError(f"No source audio recorded for audio {audio_id}")

    download_url = await generate_signed_download_url(
        artifact.audio_bucket,
        artifact.audio_object,
        expiry_minutes=DOWNLOAD_URL_EXPIRY_MINUTES,
    )
    expires_at = datetime.now(UTC) + timedelta(minutes=DOWNLOAD_URL_EXPIRY_MINUTES)

    return AcoustemeAudioResponse(
        audio_id=artifact.audio_id,
        download_url=download_url,
        expires_at=expires_at,
    )


async def store_artifact(
    db: AsyncSession,
    *,
    audio_id: str,
    codebook_version: str,
    stream: dict[str, Any],
    bucket: str = GCS_OC_BUCKET,
    audio_bucket: str | None = None,
    audio_object: str | None = None,
    title: str | None = None,
    collection: str | None = None,
) -> OC_AcoustemeArtifact:
    """Persist a tokenizer-produced stream: gzip → upload → upsert pointer row.

    ``stream`` is the tokenizer output, at minimum ``duration_sec``,
    ``num_frames`` and ``segments`` ([{start, end, unit_id}, ...]). The
    redundant per-frame ``timestamps`` array is dropped if present — it is
    derivable from hop_sec and num_frames. Called by the ingestion pipeline, not
    by request handlers.
    """

    segments = stream.get("segments") or []
    payload = {
        "audio_id": audio_id,
        "codebook_version": codebook_version,
        "hop_sec": ACOUSTEME_HOP_SEC,
        "num_units": ACOUSTEME_NUM_UNITS,
        "duration_sec": stream.get("duration_sec"),
        "num_frames": stream.get("num_frames"),
        "segments": segments,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    # mtime=0 keeps the gzip byte-reproducible; hash the uncompressed payload so
    # the digest is a stable content hash (gzip stamps a timestamp otherwise).
    gz = gzip.compress(raw, mtime=0)
    sha256 = hashlib.sha256(raw).hexdigest()

    blob_name = acousteme_blob_path(audio_id, codebook_version)
    await upload_gcs_object(bucket, blob_name, gz, "application/json", content_encoding="gzip")

    artifact = await db.get(
        OC_AcoustemeArtifact,
        {"audio_id": audio_id, "codebook_version": codebook_version},
    )
    if artifact is None:
        artifact = OC_AcoustemeArtifact(audio_id=audio_id, codebook_version=codebook_version)
        db.add(artifact)

    if collection is not None:
        artifact.collection = collection
    if title is not None:
        artifact.title = title
    artifact.status = AcoustemeStatus.READY
    artifact.gcs_bucket = bucket
    artifact.gcs_object = blob_name
    artifact.content_encoding = "gzip"
    artifact.audio_bucket = audio_bucket
    artifact.audio_object = audio_object
    artifact.duration_sec = stream.get("duration_sec")
    artifact.num_frames = stream.get("num_frames")
    artifact.hop_sec = ACOUSTEME_HOP_SEC
    artifact.num_segments = len(segments)
    artifact.num_units = ACOUSTEME_NUM_UNITS
    artifact.distinct_units = len({s["unit_id"] for s in segments})
    artifact.size_bytes = len(gz)
    artifact.sha256 = sha256
    artifact.error = None

    await db.commit()
    await db.refresh(artifact)
    return artifact
