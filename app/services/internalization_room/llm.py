from __future__ import annotations

import logging
from typing import Literal

import anthropic
from anthropic.types import (
    Message,
    MessageParam,
    OutputConfigParam,
    ThinkingConfigAdaptiveParam,
)

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

Effort = Literal["low", "medium", "high", "xhigh", "max"]


def room_model(settings: Settings) -> str:
    """The model behind the room's facilitation."""
    return _ladder(settings.tripod_voice_model)[0]


def _ladder(configured: str) -> list[str]:
    return [rung.strip() for rung in configured.split(",") if rung.strip()]


async def call_agent(
    *,
    system_prompt: str,
    user_content: str,
    model: str | None = None,
    max_output_tokens: int = 2000,
    effort: Effort = "high",
    settings: Settings | None = None,
) -> str:
    """Ask one of the room's models, and hand back the text it spoke.

    Thinking is adaptive on every call rather than a level the caller picks: the ladder's
    rungs disagree about the default — omitting it on `claude-opus-4-8` means not thinking at
    all — so a rung that answered well would answer worse purely by being stepped down onto.
    """
    settings = settings or get_settings()
    model = model or room_model(settings)
    thinking: ThinkingConfigAdaptiveParam = {"type": "adaptive"}
    output_config: OutputConfigParam = {"effort": effort}
    messages: list[MessageParam] = [{"role": "user", "content": user_content}]
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=max_output_tokens,
        thinking=thinking,
        output_config=output_config,
        system=system_prompt,
        messages=messages,
    )
    _report_unfinished(response, max_output_tokens)
    return _spoken_text(response)


def _spoken_text(response: Message) -> str:
    for block in response.content:
        if block.type == "text":
            return block.text
    logger.warning("Room agent returned no content at all")
    return ""


def _report_unfinished(response: Message, max_output_tokens: int) -> None:
    if response.stop_reason in (None, "end_turn"):
        return
    logger.warning(
        "Room agent stopped as %s with a ceiling of %d tokens: output=%s",
        response.stop_reason,
        max_output_tokens,
        response.usage.output_tokens,
    )
