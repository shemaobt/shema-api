from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.as_enums import AsExportStatus
from app.core.database import Base


class AsExport(Base):
    __tablename__ = "as_exports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    language_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("languages.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(12), default=AsExportStatus.BUILDING.value)
    bundle_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manifest_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tiers_included: Mapped[str | None] = mapped_column(String(40), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
