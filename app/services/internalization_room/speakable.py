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
recorded in ``docs/what-the-voice-says.md``.
"""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from functools import partial
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
_CLOSE = r"[\"\u201d\u2019')\]\u00bb]"

#: A code is one of those, or an all-caps name of two or more words joined by underscores
#: (`THE_LAND_AFFLICTED_BY_FAMINE`, `OBJECT_KIND`) — never a lone all-caps word like `LORD`.
_CODE = (
    rf"(?:(?:(?:{_NUMBERED}|{_SCENE})_?[0-9]|(?:{_NAMED})_[A-Z])[A-Z0-9_]*"
    r"|[A-Z]{2,}(?:_[A-Z0-9]+)+)"
)

#: A figure or a cultural background is named only by its slug, so its link is voiced as the
#: slug's words; nothing in the maps follows it with a name of its own.
_NAMED_BY_ITS_SLUG = re.compile(rf"\[\[{_SPACE}*(?:FIG|CB)_[0-9]+-([^\]]+?){_SPACE}*\]\]")

#: A link that begins with a code goes whole, slug and spaces inside the brackets included; so
#: does a bare code with the slug hyphen-attached or a second code joined to it by a slash.
#: `(?<!\w)` and `(?!\w)` keep the match off the middle of a word.
_ONE_CODE = (
    rf"\[\[{_SPACE}*{_CODE}{_SPACE}*(?:[-|][^\]]*)?\]\]"
    rf"|(?<!\w){_CODE}(?:-\w+|/{_CODE})*(?!\w)"
)

#: Between two codes, and only there, the joiner goes with them: the commas of a list and its
#: "e" or "and" (a serial comma included), and the "a", "to", dash or spaced hyphen of a range.
#: A joiner between a code and a word is the word's, and stays.
_JOINER = (
    rf"(?:,{_SPACE}*(?:e|and){_SPACE}+|,{_SPACE}*|{_SPACE}+(?:e|and|a|to){_SPACE}+|{_SPACE}*[\u2013—]{_SPACE}*"
    rf"|{_SPACE}+-{_SPACE}+)"
)
_CANON_CODE = re.compile(rf"(?:{_ONE_CODE})(?:{_JOINER}(?:{_ONE_CODE}))*")

#: Where a code was removed. No text the room voices carries it, so every mend below is anchored
#: to it and reaches only the seam a code left: a mark with no seam beside it is never touched.
_SEAM = "\x00"
_SEAMS_IN_A_ROW = re.compile(rf"{_SEAM}(?:{_SPACE}*{_SEAM})+")

_DASH = r"(?:[\u2013—]|(?<!\S)-(?!\S))"
_WEAK_MARK = r"[,;:]"
_WORD_JOINER = rf"(?:e|and)(?={_SPACE})"

#: What a removal can leave beside its seam, in the order `_mend` reads it. Brackets and quotes
#: that held only the code go with it. Two dashes around it go too when they framed it, but when
#: the first one closes a pair the sentence already opened, only the code's own second dash goes;
#: whether a dash opens or closes a pair is read as her question split reads it, outside quotes
#: and parentheses and never between digits. A comma left between the code and a dash goes.
#: Between a mark and a joiner, the survivors keep the joiner: a comma after the code goes when
#: a mark stands before it, a colon included, and a mark before the code goes when an "e" or an
#: "and" follows it. Where the code opened a sentence — at the text's edge or past a sentence
#: end — any mark it left goes, a full stop included but never an ellipsis; where it opened a
#: clause — after a colon, a dash, an opening quote or bracket — the weak marks it left go, and
#: so does a code right behind it with its own marks; a word is never taken. Last, a weak mark
#: before a strong one or a closer goes, a weak mark after `!` or `?` goes, a dash before a
#: closing mark goes, and a full stop doubled across the seam is read once.
_ENCLOSED = re.compile(
    rf"[(\[]{_SPACE}*[,;/\u2013—-]*{_SPACE}*{_SEAM}{_SPACE}*[,;/\u2013—-]*{_SPACE}*[)\]]"
    rf"|\"{_SPACE}*{_SEAM}{_SPACE}*\"|\u201c{_SPACE}*{_SEAM}{_SPACE}*\u201d"
    rf"|\u00ab{_SPACE}*{_SEAM}{_SPACE}*\u00bb|\u2018{_SPACE}*{_SEAM}{_SPACE}*\u2019"
)
_FRAMED = re.compile(rf"({_DASH}){_SPACE}*{_SEAM}{_SPACE}*{_DASH}")
_COMMA_BEFORE_A_DASH = re.compile(rf",{_SPACE}*{_SEAM}(?={_SPACE}*{_DASH})")
_BETWEEN_JOINERS = re.compile(
    rf"(?P<left>,|[;:]){_SPACE}*{_SEAM}{_SPACE}*(?P<right>,|{_WORD_JOINER})"
)
_SENTENCE_OPENING = re.compile(
    rf"(?:^|(?<=[.!?\u2026])|(?<=[.!?\u2026]{_SPACE})|(?<=[.!?\u2026]{_CLOSE}{_SPACE})){_SEAM}"
    rf"(?:{_SPACE}*(?:[,;:!?\u2013—]|\.(?![.\w])|-(?!\S)|{_SEAM}))+"
)
_CLAUSE_OPENING = re.compile(
    rf"(?:(?<=[(\[\u201c\u00ab\u2018\"])|(?<=[:;\u2013—]{_SPACE})|(?<=\s-{_SPACE})){_SEAM}"
    rf"(?:{_SPACE}*(?:{_WEAK_MARK}|-(?!\S)|{_SEAM}))+"
)
_WEAK_BEFORE_STRONG = re.compile(
    rf"{_WEAK_MARK}{_SPACE}*{_SEAM}(?={_SPACE}*(?:[.!?]|{_CLOSE}))|,{_SPACE}*{_SEAM}(?={_SPACE}*[;:])"
)
_WEAK_AFTER_STRONG = re.compile(rf"{_SEAM}({_SPACE}*[!?]){_SPACE}*{_WEAK_MARK}")
_DASH_BEFORE_CLOSE = re.compile(rf"{_DASH}{_SPACE}*{_SEAM}(?={_SPACE}*(?:[.,;:!?]|$))")
_DOUBLED_STOP = re.compile(rf"(?<=\.){_SPACE}*{_SEAM}{_SPACE}*\.(?!\.)")
_SEAM_AT_AN_EDGE = re.compile(
    rf"^{_SPACE}*{_SEAM}{_SPACE}*|{_SPACE}*{_SEAM}{_SPACE}*$"
    rf"|(?<=[(\[\u201c\u00ab\u2018\"]){_SPACE}*{_SEAM}{_SPACE}*"
)
_SEAM_BEFORE_A_MARK = re.compile(
    rf"(?P<before>.?){_SPACE}*{_SEAM}{_SPACE}*(?=[,.;:!?)\]\u201d\u00bb\"\u2019])"
)
_SEAM_BETWEEN_WORDS = re.compile(rf"{_SPACE}*{_SEAM}{_SPACE}*")

_YHWH = re.compile(r"\bYHWH\b")

#: A letter in any script: a word character that is neither a digit nor an underscore.
_LETTER_CLASS = r"[^\W\d_]"
_LETTER = re.compile(_LETTER_CLASS)
_OPENERS = "\u201c\u00ab\u2018("
_CLOSERS = "\u201d\u00bb)"
_APOSTROPHE = "\u2019"
_FIRST_LETTER = re.compile(rf"^([\"\u201c\u00ab\u2018'(\[\s]*)({_LETTER_CLASS})")

_TERMINAL_END = re.compile(rf"[.!?\u2026:;]{_CLOSE}*\Z")
_LINE_END = re.compile(r"\r\n?")
_WHITESPACE = re.compile(r"\s+")
_HORIZONTAL_RULE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*\Z")
_HEADING = re.compile(r"^\s*#{1,6}\s+(.*)\Z")
_BULLET = re.compile(r"^\s*(?:[-*\u2022]|[0-9]{1,2}[.)])\s+(.*)\Z")

#: The formatting marks, in the order they come off. A link keeps its text and drops its url,
#: and a code span keeps its content, before any asterisk or underscore is read.
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_CODE_SPAN = re.compile(r"`([^`]*)`")
#: Bold before italic, so `**word**` is never read as an italic pair around `*word*`.
_BOLD = re.compile(r"\*\*(\S(?:[^*]*?\S)?)\*\*")
_BOLD_UNDERSCORES = re.compile(r"__(\S(?:[^_]*?\S)?)__")
_ITALIC = re.compile(r"\*(\S(?:[^*]*?\S)?)\*")
#: An underscore pair only when it wraps a word or a phrase, never inside `snake_case`.
_ITALIC_UNDERSCORES = re.compile(r"(^|\W)_(\S(?:[^_]*?\S)?)_(?=\W|\Z)")
#: Last, every asterisk the pairs left (an asterisk is never part of a word), and a `#` unless
#: it is glued to a letter or a digit (`C#` stays).
_STRAY_ASTERISK = re.compile(r"\*")
_STRAY_HASH = re.compile(r"(?<![^\W_])#")
_MARKS = (
    (_LINK, r"\1"),
    (_CODE_SPAN, r"\1"),
    (_BOLD, r"\1"),
    (_BOLD_UNDERSCORES, r"\1"),
    (_ITALIC, r"\1"),
    (_ITALIC_UNDERSCORES, r"\1\2"),
    (_STRAY_ASTERISK, ""),
    (_STRAY_HASH, ""),
)
_SENTENCE_END = re.compile(rf"[.!?\u2026]+{_CLOSE}*(?=\s|\Z)")
_ENDS_AS_QUESTION = re.compile(rf"[!?]*\?[!?]*{_CLOSE}*\Z")
_HEAD_TERMINAL = re.compile(rf"[.!?\u2026]{_CLOSE}*\Z")

_SPOKEN_FORM: dict[str, str] = {
    "pt": "Senhor Jeová",
    "en": "the LORD",
}


def _pairing_dashes(text: str) -> tuple[list[int], list[int]]:
    spans = _Spans()
    starts: list[int] = []
    dashes: list[int] = []
    for start, sentence in _sentences(text):
        starts.append(start)
        dashes.extend(
            start + cut + (sentence[cut] == " ")
            for cut, _, dash in _separators(sentence, spans)
            if dash
        )
    return starts, dashes


def _unframed(starts: list[int], dashes: list[int], seam: re.Match[str]) -> str:
    dash_at = seam.start(1)
    sentence_start = starts[bisect_right(starts, dash_at) - 1]
    before = bisect_left(dashes, dash_at) - bisect_left(dashes, sentence_start)
    if before % 2 == 0:
        return f" {_SEAM} "
    return f"{seam[1]} {_SEAM}"


def _one_joiner(seam: re.Match[str]) -> str:
    if seam["right"] == ",":
        return f"{seam['left']}{_SEAM}"
    return f"{_SEAM}{seam['right']}"


def _closed_up(seam: re.Match[str]) -> str:
    before = seam["before"]
    return f"{before} " if before and before in ".!?\u2026" else before


def _mend(text: str) -> str:
    named = _NAMED_BY_ITS_SLUG.sub(lambda link: link[1].replace("-", " "), text)
    marked = _SEAMS_IN_A_ROW.sub(_SEAM, _CANON_CODE.sub(_SEAM, named))
    if _SEAM not in marked:
        return named
    mended = _ENCLOSED.sub(_SEAM, marked)
    mended = _FRAMED.sub(partial(_unframed, *_pairing_dashes(mended)), mended)
    mended = _COMMA_BEFORE_A_DASH.sub(_SEAM, mended)
    mended = _BETWEEN_JOINERS.sub(_one_joiner, mended)
    mended = _SENTENCE_OPENING.sub(_SEAM, mended)
    mended = _CLAUSE_OPENING.sub(_SEAM, mended)
    mended = _WEAK_BEFORE_STRONG.sub(_SEAM, mended)
    mended = _WEAK_AFTER_STRONG.sub(rf"{_SEAM}\1", mended)
    mended = _DASH_BEFORE_CLOSE.sub(_SEAM, mended)
    mended = _DOUBLED_STOP.sub(_SEAM, mended)
    mended = _SEAM_AT_AN_EDGE.sub("", mended)
    mended = _SEAM_BEFORE_A_MARK.sub(_closed_up, mended)
    return _SEAM_BETWEEN_WORDS.sub(" ", mended)


def speakable_text(text: str, language: str) -> str:
    """Make the text speakable: her three rewrites in her order, with our guard after the first.

    The marks come off first, so a code inside bold is bare when the guard looks for it; the
    codes go next, so the seam they leave is mended before the question split reads it; the
    divine name is rewritten last.

    The divine-name table is Marcia's, not invented here: it exists only where her own rebuilt
    prompts already carry the rule in the same language. A language outside that table keeps
    the bare letters rather than guessing at a form the pilot does not speak.
    """
    text = standalone_questions(_mend(strip_markdown(text.replace(_SEAM, ""))))
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


def _separators(sentence: str, spans: _Spans) -> list[tuple[int, int, bool]]:
    """Every colon, semicolon or dash outside quotes and parentheses, advancing `spans`.

    A separator between two digits is a time, a verse or a range, never a separator.
    """
    candidates: list[tuple[int, int, bool]] = []
    for i, char in enumerate(sentence):
        previous, following = sentence[i - 1 : i], sentence[i + 1 : i + 2]
        if char == '"':
            spans.in_double = not spans.in_double
            continue
        if char in _OPENERS:
            spans.depth += 1
            continue
        apostrophe = (
            char == _APOSTROPHE
            and _LETTER.fullmatch(previous) is not None
            and _LETTER.fullmatch(following) is not None
        )
        if char in _CLOSERS or (char == _APOSTROPHE and not apostrophe):
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
    return candidates


def _last_separator(sentence: str, spans: _Spans) -> tuple[int, int] | None:
    """The last cut of a sentence, advancing `spans` over the whole of it.

    Two or more dashes in one sentence are a parenthetical pair, so no dash cuts it; a colon or
    a semicolon after the pair still does.
    """
    candidates = _separators(sentence, spans)
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
    return "".join(_split_question(sentence, spans) for _, sentence in _sentences(text))


def _sentences(text: str) -> Iterator[tuple[int, str]]:
    cursor = 0
    for end in _SENTENCE_END.finditer(text):
        yield cursor, text[cursor : end.end()]
        cursor = end.end()
    yield cursor, text[cursor:]


def _as_own_sentence(line: str) -> str:
    sentence = _capitalized(line.strip())
    if not sentence or _TERMINAL_END.search(sentence):
        return sentence
    return f"{sentence}."


def _unmarked(line: str) -> str:
    if _HORIZONTAL_RULE.match(line):
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
