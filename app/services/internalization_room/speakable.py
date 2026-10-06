"""What the team hears, made speakable before it ever reaches a voice engine.

Two things happen to the text on the way to the voice. The canon codes the maps carry — `B3`,
`FIG_0013`, `PL_ISRAEL`, `[[B3-Naomi]]` — are removed, in every language, because a voice engine
spells them out as letters and numbers no one on the team has a use for; the name that follows
a link in the map prose already says what it stood for, so nothing is replaced. And the
tetragrammaton is rendered pronounceable.

The maps and the Guide write the divine name as the four consonants "YHWH", which a voice
engine reads letter by letter — a name spelled instead of spoken, in the middle of the turn
the map most depends on. The prompts already instruct the spoken form, but a substitution
here is the deterministic last line of defence: any "YHWH" that slips through a corrected
draft or a story-so-far quote is still voiced as a name, never as four letters. The table and
its source are recorded in ``docs/divine-name-speakable-form.md``.
"""

from __future__ import annotations

import re

_YHWH = re.compile(r"\bYHWH\b")

_CODE = r"(?:[A-Z]+(?:_[A-Z0-9]+)+|[A-Z]+[0-9]+(?:_[A-Z0-9]+)*)"
_CANON_CODE = re.compile(
    rf"\[\[{_CODE}(?:[-|][^\]]*)?\]\]|(?<!\w){_CODE}(?:-\w+)*(?!\w)",
)
_EMPTY_BRACKETS = re.compile(r"\([\s,;/\u2013—-]*\)|\[[\s,;/\u2013—-]*\]")
_DASH_PAIR = re.compile(r"[\u2013—]\s*[\u2013—]")
_DASH_BEFORE_CLOSE = re.compile(r"\s*[\u2013—]\s*(?=[.,;:!?]|$)")
_COMMAS = re.compile(r"[ \t]*,(?:[ \t]*,)+")
_COMMA_BEFORE_CLOSE = re.compile(r",(?=[ \t]*[.;:!?])")
_SPACE_RUN = re.compile(r"[ \t]{2,}")
_SPACE_BEFORE_MARK = re.compile(r"[ \t]+(?=[,.;:!?])")
_EDGE_DEBRIS = re.compile(r"^[\s,;\u2013—]+|[\s,;\u2013—]+$")

_SPOKEN_FORM: dict[str, str] = {
    "pt": "Senhor Jeová",
    "en": "the LORD",
}


def _without_canon_codes(text: str) -> str:
    removed = _CANON_CODE.sub("", text)
    if removed == text:
        return text
    mended = _EMPTY_BRACKETS.sub("", removed)
    mended = _DASH_PAIR.sub(" ", mended)
    mended = _DASH_BEFORE_CLOSE.sub("", mended)
    mended = _COMMAS.sub(",", mended)
    mended = _COMMA_BEFORE_CLOSE.sub("", mended)
    mended = _SPACE_RUN.sub(" ", mended)
    mended = _SPACE_BEFORE_MARK.sub("", mended)
    return _EDGE_DEBRIS.sub("", mended)


def speakable_text(text: str, language: str) -> str:
    """Remove the canon codes, then replace the tetragrammaton with its spoken form.

    A code is a bracketed link that begins with one, or a bare one with the slug attached to
    it; it goes in every language and is never replaced by a word. A line with no code is
    returned as written, so the seam is mended only where something was removed.

    The divine-name table is Marcia's, not invented here: it exists only where her own rebuilt
    prompts already carry the rule in the same language. A language outside that table keeps
    the text it had, minus the codes, rather than guessing at a form the pilot does not speak.
    """
    text = _without_canon_codes(text)
    form = _SPOKEN_FORM.get(language)
    if form is None:
        return text
    return _YHWH.sub(form, text)
