from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.as_enums import AsUploadStatus
from app.core.database import Base


class AsTierCClip(Base):
    __tablename__ = "as_tier_c_clips"
    __table_args__ = (UniqueConstraint("language_id", "clip_number", name="uq_as_tier_c_clip"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    language_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("languages.id", ondelete="CASCADE"), index=True
    )
    clip_number: Mapped[int] = mapped_column(Integer)
    source_recording_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_word_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    position: Mapped[str | None] = mapped_column(String(12), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    export_clip_id: Mapped[str] = mapped_column(String(80))
    export_filename: Mapped[str] = mapped_column(String(200))
    upload_format: Mapped[str] = mapped_column(String(10))
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_status: Mapped[str] = mapped_column(String(12), default=AsUploadStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AsTierCSortAssignment(Base):
    __tablename__ = "as_tier_c_sort_assignments"
    __table_args__ = (UniqueConstraint("clip_id", "dimension", "round", name="uq_as_tier_c_sort"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    clip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("as_tier_c_clips.id", ondelete="CASCADE"), index=True
    )
    dimension: Mapped[str] = mapped_column(String(8))
    round: Mapped[str] = mapped_column(String(12))
    group_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
