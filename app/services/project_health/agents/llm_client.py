from __future__ import annotations

import json
import logging
from typing import Any, TypeVar, cast

from google import genai
from google.genai import types

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

FAST_MODEL = "gemini-3-flash-preview"
QUALITY_MODEL = "gemini-3-flash-preview"

T = TypeVar("T")


def _warn_if_truncated(response: types.GenerateContentResponse, *, model: str, cap: int) -> None:
    """Say so when the model was cut off, instead of returning the stub in silence.

    A truncated answer reaches the caller as an unparseable fragment, and every JSON agent
    here answers a parse failure with its fallback — an empty context, no evidence, an
    approving guardrail. The report still renders, so nothing looks wrong. The first real
    interview ever run through this service produced nineteen of these and the only trace
    was a parse warning holding a single `{`.

    `thoughts_token_count` is the number that explains it: on a thinking model the thinking
    is spent from the same budget as the answer, so a cap that looks generous can leave
    almost nothing for the JSON. It is logged here so the caps can be tuned from evidence.
    """
    candidates = response.candidates or []
    if not candidates or candidates[0].finish_reason != types.FinishReason.MAX_TOKENS:
        return
    usage = response.usage_metadata
    logger.warning(
        "project_health agent truncated: model=%s cap=%s answer_tokens=%s thinking_tokens=%s",
        model,
        cap,
        getattr(usage, "candidates_token_count", None),
        getattr(usage, "thoughts_token_count", None),
    )


async def call_agent(
    *,
    system_prompt: str,
    user_content: str,
    model: str = FAST_MODEL,
    temperature: float = 0.4,
    max_output_tokens: int = 2000,
    expects_json: bool = False,
    settings: Settings | None = None,
) -> str:
    """One turn with an agent, returning its raw text.

    `expects_json` puts the model in JSON mode. Every caller that parses the answer should
    set it: without it the model is free to wrap the object in a fence or introduce it in
    prose, and `safe_parse_json` then falls back and the agent silently contributes nothing.
    """
    settings = settings or get_settings()
    client = genai.Client(api_key=settings.google_api_key)
    response = await client.aio.models.generate_content(
        model=model,
        contents=[{"role": "user", "parts": [{"text": user_content}]}],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json" if expects_json else None,
        ),
    )
    _warn_if_truncated(response, model=model, cap=max_output_tokens)
    return response.text or ""


async def call_chat(
    *,
    system_prompt: str,
    contents: list[dict],
    model: str = QUALITY_MODEL,
    temperature: float = 0.6,
    max_output_tokens: int = 500,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    client = genai.Client(api_key=settings.google_api_key)
    response = await client.aio.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
    )
    return response.text or ""


def safe_parse_json(text: str, fallback: T) -> T:
    if not text:
        return fallback
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.lstrip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        parsed: Any = json.loads(cleaned)
        return cast(T, parsed)
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("project_health agent JSON parse failed: %s", text[:200])
        return fallback
