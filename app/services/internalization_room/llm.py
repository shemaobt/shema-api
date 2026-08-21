from __future__ import annotations

import logging

from google import genai
from google.genai import types

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

ROOM_MODEL = "gemini-3-flash-preview"

DELIBERATE = types.ThinkingLevel.LOW


async def call_agent(
    *,
    system_prompt: str,
    user_content: str,
    model: str = ROOM_MODEL,
    temperature: float = 0.4,
    max_output_tokens: int = 2000,
    thinking: types.ThinkingLevel = DELIBERATE,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    client = genai.Client(api_key=settings.google_api_key)
    response = await client.aio.models.generate_content(
        model=model,
        contents=[{"role": "user", "parts": [{"text": user_content}]}],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_level=thinking),
        ),
    )
    _report_unfinished(response, max_output_tokens)
    return response.text or ""


def _report_unfinished(response: types.GenerateContentResponse, max_output_tokens: int) -> None:
    candidates = response.candidates or []
    if not candidates:
        logger.warning("Room agent returned no candidates at all")
        return
    reason = candidates[0].finish_reason
    if reason is types.FinishReason.STOP:
        return
    usage = response.usage_metadata
    logger.warning(
        "Room agent stopped as %s with a ceiling of %d tokens: thoughts=%s output=%s",
        reason,
        max_output_tokens,
        getattr(usage, "thoughts_token_count", None),
        getattr(usage, "candidates_token_count", None),
    )
