import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class PublicRequest(Base):
    __tablename__ = "public_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    requester_name: Mapped[str] = mapped_column(String(200))
    requester_email: Mapped[str] = mapped_column(String(320), index=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str | None] = mapped_column(String(3), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_id: Mapped[str | None] = mapped_column(
        ForeignKey("languages.id", ondelete="SET NULL"), nullable=True
    )
    new_language_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    new_language_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
