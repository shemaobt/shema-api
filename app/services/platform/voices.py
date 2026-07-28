"""Language -> platform voice map.

Inline in code on purpose (owner's call): the voice is a product choice, made by ear, not
environment configuration — whoever changes it needs to hear the result and open a PR.

**One NATIVE voice per language**, not a single multilingual one. ElevenLabs warns that a
voice "retains its unique characteristics *and accent*" in any language it speaks: the single
voice (`EXAVITQu4vr4xnSDxMaL`, the one project_health and translation_helper use today) reads
English with a Brazilian accent, and vice versa. In a tool whose whole thesis is sounding
human, that matters.
"""

from app.core.exceptions import ValidationError

PT_BR = "aU2vcrnwi348Gnc2Y1si"
EN_US = "gfRt6Z3Z8aTbpLfexQ7N"

#: BCP-47 locale -> `voice_id`. Accepts the base language as an alias for the main locale.
VOICES: dict[str, str] = {
    "pt-BR": PT_BR,
    "pt": PT_BR,
    "en-US": EN_US,
    "en": EN_US,
}


def resolve_voice(language: str) -> str:
    """The voice for the requested language.

    Fails loudly on a language with no configured voice instead of borrowing another one: a
    pt-BR voice reading Japanese comes out unintelligible, and confusing noise is worse than
    a clear error.
    """
    voice = VOICES.get(language) or VOICES.get(language.split("-")[0])
    if voice is None:
        raise ValidationError(f"No voice configured for language {language!r}")
    return voice


def language_hint(language: str) -> str:
    """The base language (`pt-BR` -> `pt`), as ElevenLabs expects in `language_code`.

    A blank locale is refused here rather than at each caller: this is the one function
    every path funnels through, and a whitespace hint reaches the provider as an empty
    `language_code` — which is not the same request as sending no hint at all, and is how
    a Portuguese answer comes back transcribed as phonetic Spanish.
    """
    hint = language.split("-")[0].strip().lower()
    if not hint:
        raise ValidationError("language must not be empty")
    return hint
