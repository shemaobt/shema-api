import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AgentId(enum.StrEnum):
    STORYTELLER = "storyteller"
    CONVERSATION = "conversation"
    ORAL = "oral"
    HEALTH = "health"
    BACKTRANS = "backtrans"


class ChatMessageRole(enum.StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


_AGENT_ID_TYPE = Enum(
    AgentId,
    name="th_agent_id_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)
_CHAT_MESSAGE_ROLE_TYPE = Enum(
    ChatMessageRole,
    name="th_chat_message_role_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)


class THChat(Base):
    __tablename__ = "th_chats"
    __table_args__ = (Index("ix_th_chats_user_updated", "user_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[AgentId] = mapped_column(_AGENT_ID_TYPE, default=AgentId.STORYTELLER)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class THChatMessage(Base):
    __tablename__ = "th_chat_messages"
    __table_args__ = (Index("ix_th_chat_messages_chat_created", "chat_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id: Mapped[str] = mapped_column(ForeignKey("th_chats.id", ondelete="CASCADE"), index=True)
    role: Mapped[ChatMessageRole] = mapped_column(_CHAT_MESSAGE_ROLE_TYPE)
    content: Mapped[str] = mapped_column(Text)
    agent_id: Mapped[AgentId | None] = mapped_column(_AGENT_ID_TYPE, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class THAgentPrompt(Base):
    __tablename__ = "th_agent_prompts"
    __table_args__ = (UniqueConstraint("agent_id", name="uq_th_agent_prompts_agent_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[AgentId] = mapped_column(_AGENT_ID_TYPE, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
