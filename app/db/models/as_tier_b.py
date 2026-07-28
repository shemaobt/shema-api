from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.as_enums import AsUploadStatus
from app.core.database import Base


class AsTierBPair(Base):
    __tablename__ = "as_tier_b_pairs"
    __table_args__ = (UniqueConstraint("language_id", "pair_number", name="uq_as_tier_b_pair"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    language_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("languages.id", ondelete="CASCADE"), index=True
    )
    pair_number: Mapped[int] = mapped_column(Integer)
    word_a_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    word_b_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    speaker_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("as_speakers.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AsTierBRecording(Base):
    __tablename__ = "as_tier_b_recordings"
    __table_args__ = (
        UniqueConstraint("pair_id", "side", "rep_index", name="uq_as_tier_b_recording"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pair_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("as_tier_b_pairs.id", ondelete="CASCADE"), index=True
    )
    side: Mapped[str] = mapped_column(String(1))
    rep_index: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(500))
    export_filename: Mapped[str] = mapped_column(String(200))
    upload_format: Mapped[str] = mapped_column(String(10))
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_status: Mapped[str] = mapped_column(String(12), default=AsUploadStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
