from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AsLanguageMember(Base):
    """Per-language access grant for annotation-studio facilitators.

    App-wide ``annotation-studio`` access (via ``UserAppRole``) lets a user *into*
    the studio; this table scopes a ``facilitator`` to the specific languages they
    may collect/edit. The ``admin`` role and platform admins bypass it entirely
    (they see and manage every language). Kept inside the annotation-studio feature
    so the shared cross-app RBAC is untouched.
    """

    __tablename__ = "as_language_members"
    __table_args__ = (UniqueConstraint("language_id", "user_id", name="uq_as_language_member"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    language_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("languages.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    granted_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
