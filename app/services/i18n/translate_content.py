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


def translation_model(settings: Settings) -> str:
    """The model that translates authored content."""
    return settings.gemini_fast_model


TRANSLATION_PROMPT = """\
You are a professional translator specializing in biblical and scholarly content.

Translate ALL human-readable text values in the following JSON from English to {language_name}.

Rules:
- Preserve the JSON structure and all field names/keys exactly as-is.
- Do NOT translate proper nouns (biblical names like Ruth, Naomi, Boaz, Bethlehem, Moab, etc.).
- Do NOT translate technical identifiers, enum values, or field keys.
- Translate descriptive prose, questions, labels, summaries, and explanatory text.
- Keep verse references (e.g., "1:1-5") unchanged.
- Return the translated JSON object.

JSON to translate:
{content}
"""


class TranslationError(Exception):
    pass


async def translate_document_content(
    content: dict,
    target_language: str,
    *,
    settings: Settings | None = None,
) -> dict:
    """Translate a document's content dict from English to target_language using LLM."""
    settings = settings or get_settings()

    language_name = LANGUAGE_NAMES.get(target_language)
    if not language_name:
        raise TranslationError(f"Unsupported language: {target_language}")

    if target_language == "en":
        return content

    prompt = TRANSLATION_PROMPT.format(
        language_name=language_name,
        content=json.dumps(content, ensure_ascii=False, indent=2),
    )

    try:
        client = genai.Client(api_key=settings.google_api_key)
        response = await client.aio.models.generate_content(
            model=translation_model(settings),
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        if not response.text:
            raise TranslationError("LLM returned empty response")
        result: dict = json.loads(response.text)
        return result
    except json.JSONDecodeError as e:
        preview = response.text[:500] if response.text else ""
        logger.error("LLM returned unparseable JSON: %s", preview)
        raise TranslationError(f"LLM returned invalid JSON: {e}") from e
    except TranslationError:
        raise
    except Exception as e:
        raise TranslationError(f"Translation failed: {e}") from e
