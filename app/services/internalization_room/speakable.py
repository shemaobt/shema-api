"""Validated text, made SPEAKABLE before it ever reaches a voice engine.

Three deterministic last lines of defence, composed in ``speakable_text``: formatting marks
off, a folded question split into its own sentence, and the divine name rendered
pronounceable. The prompts already instruct plain, voice-first, spoken-name text, but
anything that slips through — a corrected draft, a story-so-far quote — must never be read
with a mark, a flattened question, or four spelled-out letters where a name belongs.

The marks-and-questions pair ports Marcia's own transform, `Tripod-Internalization`'s
``src/audio/speakable.ts`` (her ruling of pilot day one, 2026-09-09), case for case,
including the limits she pins rather than fixes. The divine name table is ours, not hers —
her language-fallback chain (``failSafeLang``) is deliberately not ported, so a language
outside the table (Spanish included) still gets its marks stripped and its questions split,
and only the name substitution is skipped. Source and table: ``docs/divine-name-speakable-form.md``.
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
_ITALIC_UNDERSCORE = regex.compile(r"(^|[^\p{L}\p{N}_])_(\S(?:[^_]*?\S)?)_(?=[^\p{L}\p{N}_]|$)")
_STRAY_ASTERISK = regex.compile(r"\*")
_STRAY_HASH = regex.compile(r"(?<![\p{L}\p{N}])#")
_WHITESPACE_RUN = regex.compile(r"\s+")


def _capitalize_first_letter(text: str) -> str:
    match = _FIRST_LETTER.match(text)
    if not match:
        return text
    return str(match.group(1) + match.group(2).upper() + text[match.end() :])


def _as_own_sentence(line: str) -> str:
    trimmed = line.strip()
    if not trimmed:
        return trimmed
    if _TERMINAL_END.search(trimmed):
        return _capitalize_first_letter(trimmed)
    return f"{_capitalize_first_letter(trimmed)}."


def strip_markdown(text: str) -> str:
    """Formatting marks off; every spoken word stays, in order (Marcia, pilot day 1, 2026-09-09).

    A link is the one deliberate exception: its visible text stays, its target does not —
    ``[Boaz](1)`` reads as "Boaz", never "Boaz 1", since a URL was never meant to be heard.
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
    return str(_WHITESPACE_RUN.sub(" ", " ".join(lines)).strip())


_SENTENCE_END = regex.compile(r"""[.!?…]+["”’')\]»]*(?=\s|$)""")
_ENDS_AS_QUESTION = regex.compile(r"""[!?]*\?[!?]*["”’')\]»]*$""")
_HEAD_TERMINAL = regex.compile(r"""[.!?…]["”’')\]»]*$""")
_LETTER = regex.compile(r"\p{L}")
_DIGIT = regex.compile(r"\p{N}")


class _SpanState:
    """Quote/parenthesis depth carried from one sentence to the next.

    A span that opens in one sentence and closes in the next still has to protect its
    inside, so the scan over each sentence shares one of these instead of starting fresh.
    """

    __slots__ = ("depth", "in_double")

    def __init__(self) -> None:
        self.depth = 0
        self.in_double = False


def _between_digits(s: str, start: int, end: int) -> bool:
    before = s[:start].rstrip()[-1:]
    after = s[end:].lstrip()[:1]
    return bool(_DIGIT.match(before)) and bool(_DIGIT.match(after))


def _last_separator_outside_spans(s: str, state: _SpanState) -> tuple[int, int] | None:
    candidates: list[tuple[int, int, bool]] = []
    for i, c in enumerate(s):
        if c == '"':
            state.in_double = not state.in_double
            continue
        if c in "“«‘(":
            state.depth += 1
            continue
        apostrophe = (
            c == "’"
            and i > 0
            and bool(_LETTER.match(s[i - 1]))
            and i + 1 < len(s)
            and bool(_LETTER.match(s[i + 1]))
        )
        if c in "”»)" or (c == "’" and not apostrophe):
            state.depth = max(0, state.depth - 1)
            continue
        if state.depth > 0 or state.in_double:
            continue
        cand: tuple[int, int, bool] | None = None
        if c in ":;":
            cand = (i, i + 1, False)
        elif c in "—–":
            cand = (i, i + 1, True)
        elif c == "-" and 0 < i < len(s) - 1 and s[i - 1] == " " and s[i + 1] == " ":
            cand = (i - 1, i + 2, True)
        if cand is None or _between_digits(s, cand[0], cand[1]):
            continue
        candidates.append(cand)
    dashes = sum(1 for cand in candidates if cand[2])
    found: tuple[int, int] | None = None
    for cand in candidates:
        if not (cand[2] and dashes >= 2):
            found = (cand[0], cand[1])
    return found


def _split_question(sentence: str, state: _SpanState) -> str:
    """Cut ``sentence`` at its last usable separator when it ends in a question, else return as is.

    The separator scan runs unconditionally, even when the sentence turns out not to end in
    a question: it is what keeps ``state``'s quote/paren depth correct for the sentence that
    comes after, since a span can open in one sentence and close in the next.
    """
    sep = _last_separator_outside_spans(sentence, state)
    if sep is None or not _ENDS_AS_QUESTION.search(sentence):
        return sentence
    start, end = sep
    head = sentence[:start].rstrip()
    tail = sentence[end:].lstrip()
    if not _LETTER.search(head) or not _LETTER.search(tail) or head.endswith(","):
        return sentence
    statement = head if _HEAD_TERMINAL.search(head) else f"{head}."
    return f"{statement} {_capitalize_first_letter(tail)}"


def standalone_questions(text: str) -> str:
    """Every question folded into a statement's tail gets its own sentence (Marcia, 2026-09-09).

    A sentence whose terminal punctuation is a question is cut at the last colon,
    semicolon, dash or spaced hyphen outside any quote or parenthesis, so the question
    stands alone: words never change, only a sentence boundary moves. Two or more dashes
    in one sentence read as a parenthetical pair, so neither cuts; a colon or semicolon
    after the pair still does. A separator between two digits is a time or a verse
    reference, not a separator. An unbalanced double quote suppresses later cuts for the
    rest of the turn, the safe direction; a head that is itself the question is still
    closed with a period rather than left open — changing either is Marcia's call, not
    this port's. KNOWN LIMIT, carried from her source: a closing ``’`` is read as an
    apostrophe only when a letter sits on both sides of it, so a plural possessive
    (``workers’`` followed by a space) closes a span it never opened — a parenthetical
    around it can end early, letting a separator past its far side cut where it should
    not.
    """
    state = _SpanState()
    out: list[str] = []
    cursor = 0
    for match in _SENTENCE_END.finditer(text):
        end = match.end()
        out.append(_split_question(text[cursor:end], state))
        cursor = end
    out.append(_split_question(text[cursor:], state))
    return "".join(out)


def speakable_text(text: str, language: str) -> str:
    """Make validated text SPEAKABLE before it reaches TTS: marks off, questions split, YHWH.

    Three deterministic steps, in this order. First ``strip_markdown``: the Guide sometimes
    writes ``**Noemi**`` or a bullet list, and the voice reads the marks as noise. Second
    ``standalone_questions``: a question folded into the tail of a statement gets no
    question intonation, so the sentence is cut before it. Both run for every language —
    Marcia's own ``failSafeLang`` fallback is not ported here, only her marks-and-questions
    transform is. Third, the tetragrammaton: the table is Marcia's, not invented here, and
    exists only where her own rebuilt prompts already carry the rule in the same language —
    a language outside it (Spanish included) reaches this step and returns from it
    untouched, its marks already stripped and its questions already split.

    All three change only what is VOICED; the persisted (validated) text keeps the Guide's
    own form for the facilitator view and the dossier.
    """
    voiced = standalone_questions(strip_markdown(text))
    form = _SPOKEN_FORM.get(language)
    if form is None:
        return voiced
    return _YHWH.sub(form, voiced)
