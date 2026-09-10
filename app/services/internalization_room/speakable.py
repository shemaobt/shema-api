"""The tetragrammaton, rendered pronounceable before it ever reaches a voice engine.

The maps and the Guide write the divine name as the four consonants "YHWH", which a voice
engine reads letter by letter — a name spelled instead of spoken, in the middle of the turn
the map most depends on. The prompts already instruct the spoken form, but a substitution
here is the deterministic last line of defence: any "YHWH" that slips through a corrected
draft or a story-so-far quote is still voiced as a name, never as four letters.
"""

from __future__ import annotations

import re

_YHWH = re.compile(r"\bYHWH\b")

_SPOKEN_FORM: dict[str, str] = {
    "pt": "Senhor Jeová",
    "en": "the LORD",
}


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
