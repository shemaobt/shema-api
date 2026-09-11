import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class BCDStatus(enum.StrEnum):
    GENERATING = "generating"
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"


class BookContextDocument(Base):
    __tablename__ = "book_context_documents"
    __table_args__ = (
        Index("ix_bcd_book_active", "book_id", "is_active"),
        UniqueConstraint(
            "book_id",
            "section_range_start",
            "section_range_end",
            "version",
            name="uq_bcd_book_section_version",
        ),
        Index("ix_bcd_book_status", "book_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id: Mapped[str] = mapped_column(
        ForeignKey("bible_books.id", ondelete="RESTRICT"), index=True
    )
    section_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    section_range_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_range_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[BCDStatus] = mapped_column(
        Enum(BCDStatus, name="bcd_status_enum", values_callable=lambda e: [m.value for m in e]),
        default=BCDStatus.DRAFT,
    )
    structural_outline: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    participant_register: Mapped[list | None] = mapped_column(JSON, nullable=True)
    discourse_threads: Mapped[list | None] = mapped_column(JSON, nullable=True)
    theological_spine: Mapped[str | None] = mapped_column(Text, nullable=True)
    places: Mapped[list | None] = mapped_column(JSON, nullable=True)
    objects: Mapped[list | None] = mapped_column(JSON, nullable=True)
    institutions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    genre_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    maintenance_notes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generation_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    regeneration_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    translations: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    locked_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    prepared_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BCDApproval(Base):
    __tablename__ = "bcd_approvals"
    __table_args__ = (UniqueConstraint("bcd_id", "user_id", name="uq_bcd_approval_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bcd_id: Mapped[str] = mapped_column(
        ForeignKey("book_context_documents.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    role_at_approval: Mapped[str] = mapped_column(String(50))
    roles_at_approval: Mapped[list | None] = mapped_column(JSON, nullable=True)
    reviewer_locale: Mapped[str | None] = mapped_column(String(10), nullable=True)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BCDSectionFeedback(Base):
    __tablename__ = "bcd_section_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bcd_id: Mapped[str] = mapped_column(
        ForeignKey("book_context_documents.id", ondelete="CASCADE"), index=True
    )
    section_key: Mapped[str] = mapped_column(String(50))
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    content: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BCDGenerationLog(Base):
    __tablename__ = "bcd_generation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bcd_id: Mapped[str] = mapped_column(
        ForeignKey("book_context_documents.id", ondelete="CASCADE"), index=True
    )
    step_name: Mapped[str] = mapped_column(String(100))
    step_order: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
