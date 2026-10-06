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
from pathlib import Path

from app.services.internalization_room.canon.elements import scene_code

_MAPS = Path(__file__).parent / "canon" / "vendor" / "meaning-map"

#: The head of every link the vendored maps carry — the code before its slug. It is read off
#: the canon at import, so a pin that moves takes the guard with it; a hand-typed list would
#: keep removing yesterday's codes and miss tomorrow's.
_HEADS = frozenset(
    head
    for page in _MAPS.glob("*.md")
    for head in re.findall(r"\[\[([A-Z]+[0-9_][A-Z0-9_]*)[-|\]]", page.read_text(encoding="utf-8"))
)


def _prefixes(shape: str) -> str:
    letters = {re.split(r"[^A-Z]", head)[0] for head in _HEADS if re.match(shape, head)}
    return "|".join(sorted(letters, key=lambda prefix: (-len(prefix), prefix)))


#: A code is a prefix the canon really uses, then a number (`B3`, `CB_0008`, `PL5_BOAZ_PORTION`)
#: or, for the families that carry none, an underscore and capitals (`PL_ISRAEL`, `TM_EVENING`).
#: The generic shape — capitals joined to a number — is what `MP3`, `CO2` and `F1` also have,
#: and they are words the team says.
_NUMBERED = _prefixes(r"[A-Z]+_?[0-9]")
_NAMED = _prefixes(r"[A-Z]+_[A-Z]")
if not (_NUMBERED and _NAMED):
    raise RuntimeError(
        f"the maps in {_MAPS} carry no code of one shape: an empty prefix list would make the "
        "pattern read every number, or every capitalised word, as a code"
    )
_SCENE = re.split(r"[^A-Z]", scene_code(1))[0]
_CODE = rf"(?:(?:{_NUMBERED}|{_SCENE})_?[0-9]|(?:{_NAMED})_[A-Z])[A-Z0-9_]*"

#: A link that begins with a code goes whole, slug included; so does a bare code with the slug
#: hyphen-attached or a second code joined to it by a slash. `(?<!\w)` and `(?!\w)` keep the
#: match off the middle of a word.
_CANON_CODE = re.compile(
    rf"\[\[{_CODE}(?:[-|][^\]]*)?\]\]|(?<!\w){_CODE}(?:-\w+|/{_CODE})*(?!\w)",
)

_SPACE = r"[ \t\u00a0]"

#: What a removal can leave behind, and the order `_mend` applies it in: brackets and quotes that
#: held only the code, then the dash pairs that framed it, then a chain of marks cut down to one
#: (a weak mark before a strong one goes, then a weak mark after `!` or `?`),
#: then the spaces, and last a full stop doubled by the abbreviation's own. The order matters: the
#: spaces are collapsed before the stops are, so the earlier steps can leave them for it.
_EMPTY_BRACKETS = re.compile(
    rf"\({_SPACE}*[,;/\u2013—-]*{_SPACE}*\)|\[{_SPACE}*[,;/\u2013—-]*{_SPACE}*\]"
)
_EMPTY_QUOTES = re.compile(
    rf"\"{_SPACE}*\"|\u201c{_SPACE}*\u201d|\u00ab{_SPACE}*\u00bb|\u2018{_SPACE}*\u2019"
)
_DOUBLED_STOP = re.compile(r"(?<!\.)\.{2}(?!\.)")
_DASH = r"(?:[\u2013—]|(?<!\S)-(?!\S))"
_DASH_PAIR = re.compile(rf"{_DASH}\s*{_DASH}")
_DASH_BEFORE_CLOSE = re.compile(rf"{_SPACE}*[\u2013—]{_SPACE}*(?=[.,;:!?]|$)")
_MARKS_BEFORE_COMMA = re.compile(rf"[,;:]{_SPACE}*,")
_MARK_BEFORE_CLOSE = re.compile(rf"[,;:](?={_SPACE}*[.!?])|,(?={_SPACE}*[;:])")
_MARK_AFTER_STRONG = re.compile(rf"(?<=[!?]){_SPACE}*[,;:]")
_SPACE_RUN = re.compile(rf"{_SPACE}{{2,}}")
_SPACE_BEFORE_MARK = re.compile(rf"{_SPACE}+(?=[,.;:!?)\]])")
_EDGE_DEBRIS = re.compile(r"^[ \t\u00a0,;\u2013—]+|[ \t\u00a0,;\u2013—]+$")

_YHWH = re.compile(r"\bYHWH\b")

_SPOKEN_FORM: dict[str, str] = {
    "pt": "Senhor Jeová",
    "en": "the LORD",
}


def _mend(line: str) -> str:
    removed = _CANON_CODE.sub("", line)
    if removed == line:
        return line
    mended = _EMPTY_BRACKETS.sub("", removed)
    mended = _EMPTY_QUOTES.sub("", mended)
    mended = _DASH_PAIR.sub(" ", mended)
    mended = _DASH_BEFORE_CLOSE.sub("", mended)
    mended = _MARKS_BEFORE_COMMA.sub(", ", mended)
    mended = _MARK_BEFORE_CLOSE.sub("", mended)
    mended = _MARK_AFTER_STRONG.sub("", mended)
    mended = _SPACE_RUN.sub(" ", mended)
    mended = _SPACE_BEFORE_MARK.sub("", mended)
    mended = _DOUBLED_STOP.sub(".", mended)
    return _EDGE_DEBRIS.sub("", mended)


def _without_canon_codes(text: str) -> str:
    """Remove every canon code and mend the seam, line by line.

    A line with no code is returned as written, so a line the removal never touched keeps its
    indentation and its spacing, in a text where another line did lose a code.
    """
    return "\n".join(_mend(line) for line in text.split("\n"))


def speakable_text(text: str, language: str) -> str:
    """Remove the canon codes, then replace the tetragrammaton with its spoken form.

    A code is a bracketed link that begins with one, or a bare one with the slug attached to
    it; it goes in every language and is never replaced by a word.

    The divine-name table is Marcia's, not invented here: it exists only where her own rebuilt
    prompts already carry the rule in the same language. A language outside that table keeps
    the text it had, minus the codes, rather than guessing at a form the pilot does not speak.
    """
    text = _without_canon_codes(text)
    form = _SPOKEN_FORM.get(language)
    if form is None:
        return text
    return _YHWH.sub(form, text)
