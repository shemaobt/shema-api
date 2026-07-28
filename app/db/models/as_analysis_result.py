from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AsAnalysisResult(Base):
    __tablename__ = "as_analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    language_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("languages.id", ondelete="CASCADE"), index=True
    )
    export_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    recommended_layer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tiers: Mapped[str | None] = mapped_column(String(80), nullable=True)
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    plot_keys_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
