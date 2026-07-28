from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.as_enums import AsUploadStatus
from app.core.database import Base


class AsTierAWord(Base):
    __tablename__ = "as_tier_a_words"
    __table_args__ = (UniqueConstraint("language_id", "label", name="uq_as_tier_a_word"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    language_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("languages.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(80))
    gloss: Mapped[str | None] = mapped_column(String(120), nullable=True)
    emblem: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reference_status: Mapped[str | None] = mapped_column(String(12), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def reference_key(self) -> str | None:
        """The reference-audio storage key, exposed only once the upload is stored."""
        if self.reference_status == AsUploadStatus.STORED.value:
            return self.reference_storage_key
        return None


class AsTierARecording(Base):
    __tablename__ = "as_tier_a_recordings"
    __table_args__ = (
        UniqueConstraint("word_id", "speaker_id", "rep_index", name="uq_as_tier_a_recording"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    word_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("as_tier_a_words.id", ondelete="CASCADE"), index=True
    )
    speaker_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("as_speakers.id", ondelete="CASCADE"), index=True
    )
    rep_index: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(500))
    export_filename: Mapped[str] = mapped_column(String(200))
    upload_format: Mapped[str] = mapped_column(String(10))
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_status: Mapped[str] = mapped_column(String(12), default=AsUploadStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
