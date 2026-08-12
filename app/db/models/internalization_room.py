import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class IRPromptKey(enum.StrEnum):
    GUIDE = "guide"
    VALIDATOR = "validator"
    COVERAGE_CLASSIFIER = "coverage_classifier"
    BOOK_PANORAMA = "book_panorama"
    DRAFT_SELF_CHECK = "draft_self_check"
    BT_ANALYST = "bt_analyst"
    BT_VERDICT_SPEAKER = "bt_verdict_speaker"


class IRSessionStatus(enum.StrEnum):
    IN_PROGRESS = "in_progress"
    DONE = "done"
    NEEDS_PERSON = "needs_person"


_PROMPT_KEY_TYPE = Enum(
    IRPromptKey,
    name="ir_prompt_key_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)
_SESSION_STATUS_TYPE = Enum(
    IRSessionStatus,
    name="ir_session_status_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)


class IRSession(Base):
    __tablename__ = "ir_sessions"
    __table_args__ = (Index("ix_ir_sessions_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pericope: Mapped[str] = mapped_column(String(120))
    status: Mapped[IRSessionStatus] = mapped_column(
        _SESSION_STATUS_TYPE, default=IRSessionStatus.IN_PROGRESS
    )
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    after_panorama: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    coverage_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    kept_takes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    back_translation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IRPrompt(Base):
    __tablename__ = "ir_prompts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key: Mapped[IRPromptKey] = mapped_column(_PROMPT_KEY_TYPE, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IRQuestionStatus(enum.StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    RESOLVED = "resolved"


_QUESTION_STATUS_TYPE = Enum(
    IRQuestionStatus,
    name="ir_question_status_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)


class IRQuestion(Base):
    """A question the team raised by the hand, addressed to a person rather than the app.

    It belongs to the device, not to the session it was asked in. A facilitator may answer
    hours later, long after that passage is closed, and the team must still receive it —
    otherwise the necklace shows a knot for a question that went nowhere.
    """

    __tablename__ = "ir_questions"
    __table_args__ = (Index("ix_ir_questions_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(36))
    pericope: Mapped[str] = mapped_column(String(120))
    audio_key: Mapped[str] = mapped_column(String(512))
    status: Mapped[IRQuestionStatus] = mapped_column(
        _QUESTION_STATUS_TYPE, default=IRQuestionStatus.OPEN
    )
    reply_audio_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    answered_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heard_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
