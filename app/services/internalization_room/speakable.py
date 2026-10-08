"""What the team hears, made speakable before it ever reaches a voice engine.

Four rewrites, in this order, and only of what is voiced: the stored turn keeps the Guide's own
form. Formatting marks come off and every word stays (Marcia, pilot day 1, 2026-09-09). The
canon codes the maps carry — `B3`, `FIG_0013`, `PL_ISRAEL`, `[[B3-Naomi]]` — are removed, in
every language, because a voice engine spells them out as letters and numbers no one on the
team has a use for. A question folded after a colon, a semicolon or a dash is cut so it stands
alone and is voiced with its tune (the same ruling). And the tetragrammaton is rendered
pronounceable: the maps write "YHWH", which a voice engine reads letter by letter.

The prompts already ask for plain, voice-first text; these rewrites are the deterministic last
line of defence for anything that slips through a corrected draft or a story-so-far quote. Each
is idempotent and never drops, reorders or invents a word. The order and the rulings are
recorded in ``docs/divine-name-speakable-form.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
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
_SPACE = r"[ \t\u00a0]"

#: A code is one of those, or an all-caps name of two or more words joined by underscores
#: (`THE_LAND_AFFLICTED_BY_FAMINE`, `OBJECT_KIND`) — never a lone all-caps word like `LORD`.
_CODE = (
    rf"(?:(?:(?:{_NUMBERED}|{_SCENE})_?[0-9]|(?:{_NAMED})_[A-Z])[A-Z0-9_]*"
    r"|[A-Z]{2,}(?:_[A-Z0-9]+)+)"
)

#: A figure or a cultural background is named only by its slug, so its link is voiced as the
#: slug's words; nothing in the maps follows it with a name of its own.
_NAMED_BY_ITS_SLUG = re.compile(r"\[\[(?:FIG|CB)_[0-9]+-([^\]]+)\]\]")

#: A link that begins with a code goes whole, slug and spaces inside the brackets included, and
#: takes the colon that introduced its name; so does a bare code with the slug hyphen-attached
#: or a second code joined to it by a slash. A list of codes goes with its commas and its "e".
#: `(?<!\w)` and `(?!\w)` keep the match off the middle of a word.
_ONE_CODE = (
    rf"\[\[{_SPACE}*{_CODE}{_SPACE}*(?:[-|][^\]]*)?\]\](?:{_SPACE}*:)?"
    rf"|(?<!\w){_CODE}(?:-\w+|/{_CODE})*(?!\w)"
)
_CANON_CODE = re.compile(rf"(?:{_ONE_CODE})(?:(?:,{_SPACE}*|{_SPACE}+e{_SPACE}+)(?:{_ONE_CODE}))*")

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
_EDGE_DEBRIS = re.compile(r"^[ \t\u00a0,.;:\u2013—]+|[ \t\u00a0,;\u2013—]+$")

_YHWH = re.compile(r"\bYHWH\b")

_LETTER = re.compile(r"[^\W\d_]")
_CLOSE = r"[\"\u201d\u2019')\]\u00bb]"
_FIRST_LETTER = re.compile(r"^([\"\u201c\u00ab\u2018'(\[\s]*)([^\W\d_])")
_TERMINAL_END = re.compile(rf"[.!?\u2026:;]{_CLOSE}*\Z")
_LINE_END = re.compile(r"\r\n?")
_WHITESPACE = re.compile(r"\s+")
_RULE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*\Z")
_HEADING = re.compile(r"^\s*#{1,6}\s+(.*)\Z")
_BULLET = re.compile(r"^\s*(?:[-*\u2022]|[0-9]{1,2}[.)])\s+(.*)\Z")
_MARKS = (
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"\*\*(\S(?:[^*]*?\S)?)\*\*"), r"\1"),
    (re.compile(r"__(\S(?:[^_]*?\S)?)__"), r"\1"),
    (re.compile(r"\*(\S(?:[^*]*?\S)?)\*"), r"\1"),
    (re.compile(r"(^|\W)_(\S(?:[^_]*?\S)?)_(?=\W|\Z)"), r"\1\2"),
    (re.compile(r"\*"), ""),
    (re.compile(r"(?<![^\W_])#"), ""),
)
_SENTENCE_END = re.compile(rf"[.!?\u2026]+{_CLOSE}*(?=\s|\Z)")
_ENDS_AS_QUESTION = re.compile(rf"[!?]*\?[!?]*{_CLOSE}*\Z")
_HEAD_TERMINAL = re.compile(rf"[.!?\u2026]{_CLOSE}*\Z")

_SPOKEN_FORM: dict[str, str] = {
    "pt": "Senhor Jeová",
    "en": "the LORD",
}


def _mend(text: str) -> str:
    named = _NAMED_BY_ITS_SLUG.sub(lambda link: link[1].replace("-", " "), text)
    removed = _CANON_CODE.sub("", named)
    if removed == text:
        return text
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


def speakable_text(text: str, language: str) -> str:
    """Make the text speakable: her three rewrites in her order, with our guard after the first.

    The marks come off first, so a code inside bold is bare when the guard looks for it; the
    codes go next, so the seam they leave is mended before the question split reads it; the
    divine name is rewritten last.

    The divine-name table is Marcia's, not invented here: it exists only where her own rebuilt
    prompts already carry the rule in the same language. A language outside that table keeps
    the bare letters rather than guessing at a form the pilot does not speak.
    """
    text = standalone_questions(_mend(strip_markdown(text)))
    form = _SPOKEN_FORM.get(language)
    if form is None:
        return text
    return _YHWH.sub(form, text)


@dataclass
class _Spans:
    depth: int = 0
    in_double: bool = False


def _capitalized(text: str) -> str:
    return _FIRST_LETTER.sub(lambda m: m[1] + m[2].upper(), text, count=1)


def _between_digits(sentence: str, start: int, end: int) -> bool:
    before = sentence[:start].rstrip()[-1:]
    after = sentence[end:].lstrip()[:1]
    return before.isnumeric() and after.isnumeric()


def _last_separator(sentence: str, spans: _Spans) -> tuple[int, int] | None:
    """The last cut outside quotes and parentheses, advancing `spans` over the whole sentence.

    Two or more dashes in one sentence are a parenthetical pair, so no dash cuts it; a colon or
    a semicolon after the pair still does.
    """
    candidates: list[tuple[int, int, bool]] = []
    for i, char in enumerate(sentence):
        previous, following = sentence[i - 1 : i], sentence[i + 1 : i + 2]
        if char == '"':
            spans.in_double = not spans.in_double
            continue
        if char in "\u201c\u00ab\u2018(":
            spans.depth += 1
            continue
        apostrophe = char == "\u2019" and previous.isalpha() and following.isalpha()
        if char in "\u201d\u00bb)" or (char == "\u2019" and not apostrophe):
            spans.depth = max(0, spans.depth - 1)
            continue
        if spans.depth or spans.in_double:
            continue
        if char in ":;":
            cut = (i, i + 1, False)
        elif char in "\u2014\u2013":
            cut = (i, i + 1, True)
        elif char == "-" and previous == " " and following == " ":
            cut = (i - 1, i + 2, True)
        else:
            continue
        if not _between_digits(sentence, cut[0], cut[1]):
            candidates.append(cut)
    dashes = sum(dash for _, _, dash in candidates)
    usable = [(start, end) for start, end, dash in candidates if not (dash and dashes >= 2)]
    return usable[-1] if usable else None


def _split_question(sentence: str, spans: _Spans) -> str:
    cut = _last_separator(sentence, spans)
    if cut is None or not _ENDS_AS_QUESTION.search(sentence):
        return sentence
    head = sentence[: cut[0]].rstrip()
    tail = sentence[cut[1] :].lstrip()
    if not _LETTER.search(head) or not _LETTER.search(tail) or head.endswith(","):
        return sentence
    statement = head if _HEAD_TERMINAL.search(head) else f"{head}."
    return f"{statement} {_capitalized(tail)}"


def standalone_questions(text: str) -> str:
    """Cut a sentence that ends as a question at its last separator, so the question stands alone.

    The span state — inside a quote or parentheses — runs across sentences, so a span that
    opens in one sentence still protects the next. Words never change; only a boundary moves.
    """
    spans = _Spans()
    sentences: list[str] = []
    cursor = 0
    for end in _SENTENCE_END.finditer(text):
        sentences.append(_split_question(text[cursor : end.end()], spans))
        cursor = end.end()
    sentences.append(_split_question(text[cursor:], spans))
    return "".join(sentences)


def _as_own_sentence(line: str) -> str:
    sentence = _capitalized(line.strip())
    if not sentence or _TERMINAL_END.search(sentence):
        return sentence
    return f"{sentence}."


def _unmarked(line: str) -> str:
    if _RULE.match(line):
        return ""
    own = False
    if heading := _HEADING.match(line):
        line, own = heading[1], True
    if bullet := _BULLET.match(line):
        line, own = bullet[1], True
    for mark, kept in _MARKS:
        line = mark.sub(kept, line)
    return _as_own_sentence(line) if own else line


def strip_markdown(text: str) -> str:
    """Take the formatting marks off and keep every word, in its order.

    A heading or a bullet is read as a sentence of its own; the lines are then joined with a
    space, since a voice hears no line break. Tables, block quotes, HTML and strike-through are
    left as they are, as in her rule.
    """
    lines = _LINE_END.sub("\n", text).split("\n")
    joined = " ".join(_unmarked(line) for line in lines)
    return _WHITESPACE.sub(" ", joined).strip()
