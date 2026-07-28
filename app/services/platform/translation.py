"""Platform translation to English, behind one callable.

The provider is deliberately swappable (the issue's "provider TBD"): today it is the same
Gemini client `services/i18n/translate_content.py` already uses, so nothing new is
installed and nothing new has to be paid for.

What comes out is a DRAFT. It is never merged into an artifact server-side — a bilingual
human confirms it in the SPA first (PRD v2 §1.1, §12).
"""

from __future__ import annotations

import logging
from typing import Protocol

from google import genai

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.services.platform.voices import language_hint

logger = logging.getLogger(__name__)

TRANSLATION_MODEL = "gemini-3-flash-preview"

#: Spoken-answer languages we can name for the model. An unlisted code is passed through as
#: itself rather than refused — naming the language is a prompt nicety, not a gate.
LANGUAGE_NAMES: dict[str, str] = {"pt": "Brazilian Portuguese", "en": "English"}

TRANSLATION_PROMPT = """\
Translate the following {language_name} text into English.

It is a transcript of a person speaking, so it may be informal, hesitant or unfinished.
Translate what is there — do not summarize it, do not complete it, do not explain it, and
do not add anything that was not said. Return the translation only, with no commentary.

Text:
{text}
"""


_DEFAULT_CLIENT: genai.Client | None = None
_DEFAULT_CLIENT_KEY: str | None = None


def _default_client(api_key: str) -> genai.Client:
    """One client for the process, like the HTTP client in `stt.py`.

    A job translates every answer of a session in a row; a client per answer would open and
    throw away a connection pool each time, and nothing ever closes them.

    Kept per key, for the same reason the TTS cache key carries the output format: the key
    is baked into the client, so a cache that ignores it would serve a client built from a
    rotated-out credential for the life of the process.
    """
    global _DEFAULT_CLIENT, _DEFAULT_CLIENT_KEY
    if _DEFAULT_CLIENT is None or api_key != _DEFAULT_CLIENT_KEY:
        _DEFAULT_CLIENT = genai.Client(api_key=api_key)
        _DEFAULT_CLIENT_KEY = api_key
    return _DEFAULT_CLIENT


class Translator(Protocol):
    """The provider seam: swapping the model out is one callable."""

    async def __call__(self, text: str, *, source_language: str) -> str: ...


async def translate_to_english(
    text: str,
    *,
    source_language: str,
    settings: Settings | None = None,
    client: genai.Client | None = None,
) -> str:
    """Translate `text` from `source_language` (BCP-47 locale) into English.

    Already-English text and empty text come straight back: every call is billed, and the
    cheapest translation is the one that never leaves.

    An empty reply from the model is an upstream failure, not an empty draft: on screen the
    two are the same thing, and the second would be confirmed as a silent recording.

    `client` is typed as the real provider client rather than as a structural stand-in: the
    call reaches through `.aio.models`, so a Protocol would take three nested declarations
    to say what the concrete type already says. Tests pass a double, which type checking
    does not see and does not need to.
    """
    base = language_hint(source_language)
    if base == "en" or not text.strip():
        return text.strip()

    cfg = settings or get_settings()
    if not cfg.google_api_key:
        raise ValidationError("GOOGLE_API_KEY is not configured")

    prompt = TRANSLATION_PROMPT.format(
        language_name=LANGUAGE_NAMES.get(base, source_language), text=text
    )
    provider = client or _default_client(cfg.google_api_key)
    try:
        response = await provider.aio.models.generate_content(
            model=TRANSLATION_MODEL, contents=prompt
        )
    except Exception as exc:
        logger.warning("Gemini translation failed: %s", exc)
        raise UpstreamServiceError(f"Translation failed: {exc}") from exc

    translation = str(response.text or "").strip()
    if not translation:
        raise UpstreamServiceError("Translation returned empty text")

    logger.info(
        "platform translation: model=%s source=%s chars_in=%d chars_out=%d",
        TRANSLATION_MODEL,
        source_language,
        len(text),
        len(translation),
    )
    return translation
