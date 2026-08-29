from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.translation_helper import (
    AgentId,
    ChatMessageRole,
    THChatMessage,
)
from app.services.translation_helper.get_agent_prompt import get_system_prompt_text
from app.services.translation_helper.get_chat_or_404 import get_chat_or_404
from app.services.translation_helper.list_messages import list_messages
from app.services.translation_helper.send_message import (
    _build_contents,
    _fallback_title,
    _generate_title,
    chat_model,
)

logger = logging.getLogger(__name__)


async def _stream_chunks(
    *,
    system_prompt: str,
    contents: list[dict],
    settings: Settings,
) -> AsyncIterator[str]:
    client = genai.Client(api_key=settings.google_api_key)
    stream = await client.aio.models.generate_content_stream(
        model=chat_model(settings),
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    async for event in stream:
        text = getattr(event, "text", None)
        if text:
            yield text


async def stream_message(
    db: AsyncSession,
    chat_id: str,
    user_id: str,
    content: str,
    *,
    agent_id: AgentId | None = None,
    settings: Settings | None = None,
) -> AsyncIterator[str]:
    """Yield assistant text chunks; persist the user turn before streaming and
    persist whatever assistant text (full or partial) was collected once the
    stream ends — so a mid-stream LLM failure doesn't make the user's question
    disappear."""
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
    await db.commit()

    system_prompt = await get_system_prompt_text(db, effective_agent)
    contents = _build_contents(history, content)

    collected: list[str] = []
    try:
        async for chunk in _stream_chunks(
            system_prompt=system_prompt, contents=contents, settings=settings
        ):
            collected.append(chunk)
            yield chunk
    finally:
        try:
            if collected:
                assistant_msg = THChatMessage(
                    chat_id=chat.id,
                    role=ChatMessageRole.ASSISTANT,
                    content="".join(collected),
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
        except Exception as e:
            logger.warning("Failed to persist assistant turn for chat %s: %s", chat.id, e)
