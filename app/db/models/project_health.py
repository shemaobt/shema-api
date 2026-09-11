import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class PHLanguage(enum.StrEnum):
    EN = "en"
    PT = "pt"
    ES = "es"
    FR = "fr"
    ID = "id"
    SW = "sw"


class PHInterviewStatus(enum.StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


_LANGUAGE_TYPE = Enum(
    PHLanguage,
    name="ph_language_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)
_INTERVIEW_STATUS_TYPE = Enum(
    PHInterviewStatus,
    name="ph_interview_status_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)


class PHInterview(Base):
    __tablename__ = "ph_interviews"
    __table_args__ = (Index("ix_ph_interviews_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_name: Mapped[str] = mapped_column(String(200))
    team_name: Mapped[str] = mapped_column(String(200))
    language: Mapped[PHLanguage] = mapped_column(_LANGUAGE_TYPE)
    status: Mapped[PHInterviewStatus] = mapped_column(
        _INTERVIEW_STATUS_TYPE, default=PHInterviewStatus.IN_PROGRESS
    )
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    coverage_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PHReport(Base):
    __tablename__ = "ph_reports"
    __table_args__ = (
        UniqueConstraint("interview_id", name="uq_ph_reports_interview_id"),
        Index("ix_ph_reports_interview_id", "interview_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id: Mapped[str] = mapped_column(ForeignKey("ph_interviews.id", ondelete="CASCADE"))
    team_report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    admin_report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PHAgentPrompt(Base):
    __tablename__ = "ph_agent_prompts"
    __table_args__ = (UniqueConstraint("prompt_key", name="uq_ph_agent_prompts_prompt_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prompt_key: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    template: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
