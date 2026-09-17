from __future__ import annotations

import logging

from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.db.models.translation_helper import (
    AgentId,
    ChatMessageRole,
    THChatMessage,
)
from app.services.translation_helper.get_agent_prompt import get_system_prompt_text
from app.services.translation_helper.get_chat_or_404 import get_chat_or_404
from app.services.translation_helper.list_messages import list_messages

logger = logging.getLogger(__name__)


def chat_model(settings: Settings) -> str:
    """The model behind a Translation Helper reply."""
    return settings.gemini_fast_model


def title_model(settings: Settings) -> str:
    """The model that names a new thread from its first message."""
    return settings.gemini_fast_model


TITLE_PROMPT = (
    "Summarize the following user message as a chat title in 50 characters or fewer."
    " Return only the title, no quotes, no period."
    " Message: {message}"
)


def _build_contents(history: list[THChatMessage], next_user_message: str) -> list[dict]:
    contents: list[dict] = []
    for msg in history:
        role = "user" if msg.role == ChatMessageRole.USER else "model"
        contents.append({"role": role, "parts": [{"text": msg.content}]})
    contents.append({"role": "user", "parts": [{"text": next_user_message}]})
    return contents


async def _generate_assistant_text(
    *,
    system_prompt: str,
    contents: list[dict],
    settings: Settings,
) -> str:
    client = genai.Client(api_key=settings.google_api_key)
    response = await client.aio.models.generate_content(
        model=chat_model(settings),
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    if not response.text:
        raise ValidationError("LLM returned empty response")
    return response.text


def _fallback_title(user_message: str) -> str:
    """Best-effort title from the user's own first message when Gemini can't help."""
    cleaned = " ".join(user_message.split())  # collapse whitespace
    truncated = cleaned[:50].strip()
    if len(cleaned) > 50:
        truncated = f"{truncated.rstrip()}…"
    return truncated or "New chat"


async def _generate_title(user_message: str, settings: Settings) -> str:
    client = genai.Client(api_key=settings.google_api_key)
    response = await client.aio.models.generate_content(
        model=title_model(settings),
        contents=TITLE_PROMPT.format(message=user_message[:1000]),
    )
    title = (response.text or "").strip().strip('"').strip("'")
    if len(title) > 100:
        title = title[:100]
    return title or _fallback_title(user_message)


async def send_message(
    db: AsyncSession,
    chat_id: str,
    user_id: str,
    content: str,
    *,
    agent_id: AgentId | None = None,
    settings: Settings | None = None,
) -> THChatMessage:
    settings = settings or get_settings()
    chat = await get_chat_or_404(db, chat_id, user_id=user_id)
    effective_agent = agent_id or chat.agent_id

    history = await list_messages(db, chat_id)
    is_first_user_message = not any(m.role == ChatMessageRole.USER for m in history)

    user_msg = THChatMessage(
        chat_id=chat.id,
        role=ChatMessageRole.USER,
        content=content,
        agent_id=None,
    )
    db.add(user_msg)

    system_prompt = await get_system_prompt_text(db, effective_agent)
    contents = _build_contents(history, content)
    assistant_text = await _generate_assistant_text(
        system_prompt=system_prompt,
        contents=contents,
        settings=settings,
    )

    assistant_msg = THChatMessage(
        chat_id=chat.id,
        role=ChatMessageRole.ASSISTANT,
        content=assistant_text,
        agent_id=effective_agent,
    )
    db.add(assistant_msg)

    if is_first_user_message and not chat.title:
        try:
            chat.title = await _generate_title(content, settings)
        except Exception as e:
            logger.warning("Auto-title failed for chat %s: %s", chat.id, e)
            chat.title = _fallback_title(content)

    await db.commit()
    await db.refresh(assistant_msg)
    return assistant_msg
