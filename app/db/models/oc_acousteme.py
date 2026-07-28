from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.enums import AcoustemeStatus


class OC_AcoustemeArtifact(Base):
    """Pointer to one audio's acousteme stream.

    The stream itself (the frame-level ``segments`` produced by the acoustic
    tokenizer) is a blob living in GCS; this row is the queryable pointer + grid
    metadata the backend serves so the frontend can fetch it by ``audio_id`` and
    chunk it client-side. One row per (audio, codebook_version): a codebook
    change is a new version rather than a mutation of an existing one.
    Re-ingesting the same version is an idempotent upsert (same deterministic
    blob path + content hash), not an accumulating edit history.

    Intentionally standalone — it does not require an OC_Recording, so pilot
    collections (e.g. the Terena "ruth" set) can be served to Beads without
    project/genre/recording scaffolding.
    """

    __tablename__ = "oc_acousteme_artifacts"

    # Stable, caller-minted id for the source audio (e.g. a slug). Not an FK.
    # Wide enough for descriptive slugs from long story titles; ingestion caps
    # ids at this length (hash-suffixing longer ones) so they always fit.
    audio_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    # Frozen codebook the unit ids are meaningless without. Part of the key so
    # re-clustering yields a new artifact rather than corrupting existing refs.
    codebook_version: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Grouping label for listing (e.g. "terena-ruth").
    collection: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default=AcoustemeStatus.PENDING, index=True)

    # GCS location of the gzipped JSON acousteme stream. Bucket is stored per row
    # so pilot buckets (e.g. terena-pilot) and the shared bucket can coexist.
    gcs_bucket: Mapped[str] = mapped_column(String(255))
    gcs_object: Mapped[str] = mapped_column(Text)
    content_encoding: Mapped[str] = mapped_column(String(20), default="gzip")

    # GCS location of the source audio (served to Beads via a signed URL).
    audio_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audio_object: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Grid metadata — enough for the frontend to lay out chunks without opening
    # the blob. hop_sec * frame_index = time; num_units is the codebook size.
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hop_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_segments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distinct_units: Mapped[int | None] = mapped_column(Integer, nullable=True)

    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
