import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.enums import CleaningStatus, SplittingStatus, UploadStatus


class OC_Recording(Base):
    __tablename__ = "oc_recordings"
    __table_args__ = (
        Index(
            "uq_oc_recordings_project_title",
            "project_id",
            "title",
            unique=True,
            postgresql_where=text(
                "split_from_id IS NULL AND splitting_status <> 'archived_after_split'"
            ),
            sqlite_where=text(
                "split_from_id IS NULL AND splitting_status <> 'archived_after_split'"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    genre_id: Mapped[str] = mapped_column(
        ForeignKey("oc_genres.id", ondelete="CASCADE"), index=True
    )
    subcategory_id: Mapped[str] = mapped_column(
        ForeignKey("oc_subcategories.id", ondelete="CASCADE"), index=True
    )
    register_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    secondary_genre_id: Mapped[str | None] = mapped_column(
        ForeignKey("oc_genres.id", ondelete="SET NULL"), nullable=True
    )
    secondary_subcategory_id: Mapped[str | None] = mapped_column(
        ForeignKey("oc_subcategories.id", ondelete="SET NULL"), nullable=True
    )
    secondary_register_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    storyteller_id: Mapped[str | None] = mapped_column(
        ForeignKey("oc_storytellers.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float)
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(String(20))
    gcs_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    upload_status: Mapped[str] = mapped_column(String(20), default=UploadStatus.LOCAL)
    upload_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleaning_status: Mapped[str] = mapped_column(String(20), default=CleaningStatus.NONE)
    cleaning_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    splitting_status: Mapped[str] = mapped_column(String(20), default=SplittingStatus.NONE)
    split_from_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    split_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    split_segment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
