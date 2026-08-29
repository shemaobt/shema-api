from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "pt-BR": "Brazilian Portuguese",
    "es": "Spanish",
    "fr": "French",
}


def back_translation_model(settings: Settings) -> str:
    """The model that back-translates authored content for review."""
    return settings.gemini_fast_model


BACK_TRANSLATION_PROMPT = """\
You are a professional translator specializing in biblical and scholarly content.

Translate ALL human-readable text values in the following JSON
from {source_language_name} to English.

Rules:
- Preserve the JSON structure and all field names/keys exactly as-is.
- Do NOT translate proper nouns (biblical names like Ruth, Naomi, Boaz, Bethlehem, Moab, etc.).
- Do NOT translate technical identifiers, enum values, or field keys.
- Translate descriptive prose, questions, labels, summaries, and explanatory text to English.
- Keep verse references (e.g., "1:1-5") unchanged.
- Return the translated JSON object.

JSON to translate:
{content}
"""


class BackTranslationError(Exception):
    pass


async def back_translate_content(
    content: dict,
    source_language: str,
    *,
    settings: Settings | None = None,
) -> dict:
    """Back-translate a document's content dict from source_language to English using LLM."""
    settings = settings or get_settings()

    if source_language == "en":
        return content

    source_language_name = LANGUAGE_NAMES.get(source_language)
    if not source_language_name:
        raise BackTranslationError(f"Unsupported language: {source_language}")

    prompt = BACK_TRANSLATION_PROMPT.format(
        source_language_name=source_language_name,
        content=json.dumps(content, ensure_ascii=False, indent=2),
    )

    try:
        client = genai.Client(api_key=settings.google_api_key)
        response = await client.aio.models.generate_content(
            model=back_translation_model(settings),
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        if not response.text:
            raise BackTranslationError("LLM returned empty response")
        result: dict = json.loads(response.text)
        return result
    except json.JSONDecodeError as e:
        preview = response.text[:500] if response.text else ""
        logger.error("LLM returned unparseable JSON for back-translation: %s", preview)
        raise BackTranslationError(f"LLM returned invalid JSON: {e}") from e
    except BackTranslationError:
        raise
    except Exception as e:
        raise BackTranslationError(f"Back-translation failed: {e}") from e
