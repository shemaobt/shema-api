from __future__ import annotations

import re
from functools import cache, lru_cache
from pathlib import Path

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room.languages import ROOM_LANGUAGES

_PROMPTS_DIR = Path(__file__).parent / "prompts"

_FILES: dict[IRPromptKey, str] = {
    IRPromptKey.GUIDE: "guide_system_prompt.md",
    IRPromptKey.VALIDATOR: "validator_system_prompt.md",
    IRPromptKey.COVERAGE_CLASSIFIER: "classifier_system_prompt.md",
    IRPromptKey.BOOK_PANORAMA: "book_overview_system_prompt.md",
    IRPromptKey.BT_ANALYST: "backtranslation_analysis_system_prompt.md",
    IRPromptKey.BT_VERDICT_SPEAKER: "backtranslation_verdict_system_prompt.md",
}

_META: dict[IRPromptKey, str] = {
    IRPromptKey.GUIDE: "Guide",
    IRPromptKey.VALIDATOR: "Validator",
    IRPromptKey.COVERAGE_CLASSIFIER: "Coverage Classifier",
    IRPromptKey.BOOK_PANORAMA: "Book Panorama",
    IRPromptKey.BT_ANALYST: "BT Analyst",
    IRPromptKey.BT_VERDICT_SPEAKER: "BT Verdict Speaker",
}


_MARKER = re.compile(r"^`?=== (BEGIN|END) SYSTEM PROMPT ===`?\s*$", re.M)


def prompt_body(text: str) -> str:
    """What sits between her standalone marker lines; the notes outside them are for a reader.

    The markers are matched as whole lines, the way her `extractPromptBody` matches them,
    because the notes above the body mention the markers inline.
    """
    begin, end = _MARKER.finditer(text)
    return text[begin.end() : end.start()].strip()


@cache
def load_prompt(key: IRPromptKey) -> str:
    return prompt_body((_PROMPTS_DIR / _FILES[key]).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def fail_safe_utterances() -> str:
    """App-side strings, not a model call — kept beside the prompts they replace.

    Her file comes first, byte for byte as she froze it. Our own supplements, one per language,
    are concatenated after it, kept in files of their own so that a language is added or
    dropped without touching hers. They carry what hers does not: the H and I lines, for
    situations she has not written, and the Portuguese B, C and E she confirmed on 2026-09-21.
    Order matters only in that the reader prefers a language-tagged block, and each section
    has at most one per language.

    **Named off the languages the room claims, never globbed.** A glob made being read the
    default: the Spanish draft sat beside her file marked "nothing here has been approved to
    be spoken to a team" and was spoken anyway, to anyone who asked for the language. Claiming
    a language is the deliberate act, and this follows it — a draft for a language the room
    does not offer reaches no mouth.
    """
    parts = [(_PROMPTS_DIR / "fail_safe_utterances.md").read_text(encoding="utf-8")]
    for language_code in ROOM_LANGUAGES:
        supplement = _PROMPTS_DIR / f"_fail_safe_{language_code}_supplement.md"
        if supplement.exists():
            parts.append(supplement.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def default_prompt(key: IRPromptKey) -> dict[str, str]:
    return {"name": _META[key], "prompt": load_prompt(key)}
