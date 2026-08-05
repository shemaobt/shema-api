import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class PhaseCategory(Base):
    __tablename__ = "phase_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(9))
    icon: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Phase(Base):
    __tablename__ = "phases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    journey_id: Mapped[str | None] = mapped_column(
        ForeignKey("journeys.id", ondelete="CASCADE"), nullable=True, index=True
    )
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("phase_categories.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProjectPhase(Base):
    __tablename__ = "project_phases"
    __table_args__ = (UniqueConstraint("project_id", "phase_id", name="uq_project_phase"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    phase_id: Mapped[str] = mapped_column(ForeignKey("phases.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="not_started")


class PhaseDependency(Base):
    __tablename__ = "phase_dependencies"
    __table_args__ = (UniqueConstraint("phase_id", "depends_on_id", name="uq_phase_dependency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phase_id: Mapped[str] = mapped_column(ForeignKey("phases.id", ondelete="CASCADE"), index=True)
    depends_on_id: Mapped[str] = mapped_column(
        ForeignKey("phases.id", ondelete="CASCADE"), index=True
    )


class PhaseStatusLog(Base):
    __tablename__ = "phase_status_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    phase_id: Mapped[str] = mapped_column(ForeignKey("phases.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
