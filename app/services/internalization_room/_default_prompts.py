from __future__ import annotations

import re
from functools import cache, lru_cache
from pathlib import Path

from app.db.models.internalization_room import IRPromptKey

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
    """App-side strings, not a model call — kept beside the prompts they replace."""
    return (_PROMPTS_DIR / "fail_safe_utterances.md").read_text(encoding="utf-8")


def default_prompt(key: IRPromptKey) -> dict[str, str]:
    return {"name": _META[key], "prompt": load_prompt(key)}
