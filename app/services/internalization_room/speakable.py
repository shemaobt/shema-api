"""The tetragrammaton, rendered pronounceable before it ever reaches a voice engine.

The maps and the Guide write the divine name as the four consonants "YHWH", which a voice
engine reads letter by letter — a name spelled instead of spoken, in the middle of the turn
the map most depends on. The prompts already instruct the spoken form, but a substitution
here is the deterministic last line of defence: any "YHWH" that slips through a corrected
draft or a story-so-far quote is still voiced as a name, never as four letters. The table and
its source are recorded in ``docs/divine-name-speakable-form.md``.
"""

from __future__ import annotations

import re

import regex

_YHWH = re.compile(r"\bYHWH\b")

_SPOKEN_FORM: dict[str, str] = {
    "pt": "Senhor Jeová",
    "en": "the LORD",
}

_TERMINAL_END = regex.compile(r"""[.!?…:;]["”’')\]»]*$""")
_FIRST_LETTER = regex.compile(r"""^(["“«‘'(\[\s]*)(\p{L})""")
_HORIZONTAL_RULE = regex.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
_HEADING = regex.compile(r"^\s*#{1,6}\s+(.*)$")
_BULLET = regex.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+(.*)$")
_LINK = regex.compile(r"\[([^\]]+)\]\([^)]*\)")
_CODE = regex.compile(r"`([^`]*)`")
_BOLD_STAR = regex.compile(r"\*\*(\S(?:[^*]*?\S)?)\*\*")
_BOLD_UNDERSCORE = regex.compile(r"__(\S(?:[^_]*?\S)?)__")
_ITALIC_STAR = regex.compile(r"\*(\S(?:[^*]*?\S)?)\*")
_ITALIC_UNDERSCORE = regex.compile(
    r"(^|[^\p{L}\p{N}_])_(\S(?:[^_]*?\S)?)_(?=[^\p{L}\p{N}_]|$)"
)
_STRAY_ASTERISK = regex.compile(r"\*")
_STRAY_HASH = regex.compile(r"(?<![\p{L}\p{N}])#")
_WHITESPACE_RUN = regex.compile(r"\s+")


def _capitalize_first_letter(text: str) -> str:
    match = _FIRST_LETTER.match(text)
    if not match:
        return text
    return match.group(1) + match.group(2).upper() + text[match.end() :]


def _as_own_sentence(line: str) -> str:
    trimmed = line.strip()
    if not trimmed:
        return trimmed
    if _TERMINAL_END.search(trimmed):
        return _capitalize_first_letter(trimmed)
    return f"{_capitalize_first_letter(trimmed)}."


def strip_markdown(text: str) -> str:
    """Formatting marks off; every word stays, in its order (Marcia, pilot day 1, 2026-09-09).

    A bullet or heading line is read as its own sentence, capitalized and closed with a
    period when it carries no terminal punctuation of its own. A plain line with no
    terminal punctuation is left exactly as it is: a soft-wrapped sentence split across
    two lines of the same paragraph would otherwise pick up a false stop. Lines are then
    joined with a space, so a paragraph break costs nothing more than the join itself.
    """
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _HORIZONTAL_RULE.match(raw):
            lines.append("")
            continue
        line = raw
        own_sentence = False
        heading = _HEADING.match(line)
        if heading:
            line = heading.group(1)
            own_sentence = True
        bullet = _BULLET.match(line)
        if bullet:
            line = bullet.group(1)
            own_sentence = True
        line = _LINK.sub(r"\1", line)
        line = _CODE.sub(r"\1", line)
        line = _BOLD_STAR.sub(r"\1", line)
        line = _BOLD_UNDERSCORE.sub(r"\1", line)
        line = _ITALIC_STAR.sub(r"\1", line)
        line = _ITALIC_UNDERSCORE.sub(r"\1\2", line)
        line = _STRAY_ASTERISK.sub("", line)
        line = _STRAY_HASH.sub("", line)
        lines.append(_as_own_sentence(line) if own_sentence else line)
    return _WHITESPACE_RUN.sub(" ", " ".join(lines)).strip()


def speakable_text(text: str, language: str) -> str:
    """Replace the tetragrammaton with the customary spoken form for ``language``.

    The table is Marcia's, not invented here: it exists only where her own rebuilt prompts
    already carry the rule in the same language. A language outside that table returns the
    text untouched rather than guessing at a form the pilot does not speak.
    """
    form = _SPOKEN_FORM.get(language)
    if form is None:
        return text
    return _YHWH.sub(form, text)
