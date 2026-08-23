# ruff: noqa: RUF001 — ported oral-decision patterns are verbatim reference data;
"""Shared, conservative interpretation helpers for spoken workflow choices.

These helpers do not understand passage content. They only keep a negative clause from
being promoted into the workflow action it rejects. A later, independently affirmative
clause may reverse an earlier rejection ("não quero tentar de novo; pode levar ao
Refine"). Ambiguity is deliberately returned to the Voice instead of guessed.

Ported from the reference prototype's ``src/oral/decision.ts`` (branch
``codex/fix-internalization-reliability`` @ cfb5b306); the behaviour is part of the
methodology contract, so changes here should track that source.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def normalize_oral_decision(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    lowered = stripped.casefold().replace("’", "'").replace("‘", "'")
    cleaned = re.sub(r"[^\w'\s-]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


@dataclass(frozen=True)
class OralDecisionClause:
    raw: str
    text: str
    interrogative: bool


_CONTRAST_MARKERS = re.compile(
    r"\s+\b(?:mas|porem|porém|contudo|but|however|instead)\b\s+", re.IGNORECASE
)
_CLAUSE_CHUNK = re.compile(r"[^;.!?\n]+[;.!?\n]*")


def oral_decision_clause_details(value: str) -> list[OralDecisionClause]:
    """Split only at strong oral boundaries.

    A contrast word begins a fresh decision clause; this preserves long-distance negatives
    such as "não deveríamos, de modo algum, levar..." while allowing an explicit later
    reversal.
    """
    marked = _CONTRAST_MARKERS.sub(";", value)
    clauses: list[OralDecisionClause] = []
    for raw in _CLAUSE_CHUNK.findall(marked):
        text = normalize_oral_decision(raw)
        if text:
            clauses.append(
                OralDecisionClause(
                    raw=raw, text=text, interrogative=oral_clause_is_interrogative(raw)
                )
            )
    return clauses


def oral_decision_clauses(value: str) -> list[str]:
    return [clause.text for clause in oral_decision_clause_details(value)]


_NEGATION_WORD = re.compile(
    r"\b(?:nao|nunca|jamais|ninguem|nenhum|nenhuma|nada|sem|not|never|nobody|none|neither"
    r"|without|dont|cannot|cant|wont|wouldnt|shouldnt|couldnt|isnt|arent|didnt)\b"
)
_NEGATION_PHRASE = re.compile(
    r"\b(?:de\s+jeito\s+nenhum|de\s+maneira\s+alguma|de\s+modo\s+algum"
    r"|em\s+hipotese\s+(?:alguma|nenhuma)|sob\s+nenhuma\s+circunstancia|nem\s+pensar"
    r"|under\s+no\s+circumstances|by\s+no\s+means|not\s+at\s+all|no\s+way)\b"
)


def oral_clause_has_negation(clause: str) -> bool:
    text = normalize_oral_decision(clause)
    return bool(
        _NEGATION_WORD.search(text)
        or _NEGATION_PHRASE.search(text)
        or re.match(r"^(?:no|not)\b", text)
    )


_SPOKEN_QUESTION_OPENING = re.compile(
    r"^(?:o\s+que\s+(?:acontece|aconteceria)\s+se|e\s+se|sera\s+que|devemos|deveriamos"
    r"|eu\s+devo|nos\s+devemos|what\s+happens\s+if|what\s+if|should\s+(?:i|we)"
    r"|shall\s+(?:i|we)|could\s+(?:i|we)|can\s+(?:i|we)|would\s+(?:i|we|it)"
    r"|do\s+(?:i|we|you|they)|did\s+(?:i|we|you|they)|have\s+(?:i|we|you|they)"
    r"|are\s+(?:i|we|you|they)|is\s+(?:it|this|that|there))\b"
)


def oral_clause_is_interrogative(clause: str) -> bool:
    """Preserve questions even when STT omits punctuation for a common question opening."""
    return (
        "?" in clause
        or "？" in clause
        or bool(_SPOKEN_QUESTION_OPENING.match(normalize_oral_decision(clause)))
    )


def oral_utterance_is_interrogative(value: str) -> bool:
    return any(clause.interrogative for clause in oral_decision_clause_details(value))


_HEDGE = re.compile(
    r"\b(?:talvez|quem\s+sabe|acho\s+que|achamos\s+que|penso\s+que|pensamos\s+que"
    r"|suponho\s+que|parece\s+que|pode\s+ser(?:\s+que)?|poderia|poderiamos|possivelmente"
    r"|provavelmente|nao\s+(?:esta|ficou)\s+claro"
    r"|(?:e|esta)\s+dificil\s+(?:dizer|saber|confirmar)"
    r"|nao\s+(?:sei|sabemos|lembro|lembramos)\s+(?:se|como|quando)?"
    r"|nao\s+(?:consigo|conseguimos|da)\s+(?:dizer|saber|confirmar|lembrar)"
    r"|nao\s+(?:tenho|temos)\s+certeza"
    r"|maybe|perhaps|possibly|probably|might|(?:i|we)\s+could|i\s+think|we\s+think"
    r"|i\s+guess|we\s+guess|it\s+seems|it\s+may\s+be|not\s+sure|unclear"
    r"|hard\s+to\s+(?:say|tell|know)|difficult\s+to\s+(?:say|tell|know)"
    r"|(?:i|we)\s+(?:can't|cant|cannot|couldn't|couldnt|do\s+not|don't|dont)"
    r"\s+(?:tell|say|know|remember|confirm))\b"
)
_REPORTED_SPEECH = re.compile(
    r"\b(?:(?:voce|voces|a\s+voz|o\s+aplicativo)\s+(?:disse|disseram|falou|falaram"
    r"|perguntou|perguntaram|mandou|mandaram|esta\s+dizendo|estao\s+dizendo"
    r"|esta\s+perguntando|estao\s+perguntando)"
    r"|(?:you|the\s+voice|the\s+app)\s+(?:said|asked|told\s+us|are\s+saying|is\s+saying"
    r"|are\s+asking\s+us|is\s+asking\s+us|are\s+telling\s+us|is\s+telling\s+us))\b"
)


def oral_clause_is_non_committal(clause: str) -> bool:
    """A mentioned action is not a committed choice when hedged, hypothetical, questioned,
    or merely repeating what the Voice said.

    Intentionally conservative for workflow gates: the Voice can ask once more, while an
    accidental advance may hide evidence or open recording.
    """
    if oral_clause_is_interrogative(clause):
        return True
    text = normalize_oral_decision(clause)
    conditional = bool(re.search(r"\b(?:se|if)\b", text))
    return bool(_HEDGE.search(text) or conditional or _REPORTED_SPEECH.search(text))


def oral_utterance_is_non_committal(value: str) -> bool:
    return any(
        oral_clause_is_non_committal(clause.raw) for clause in oral_decision_clause_details(value)
    )


def matches_oral_patterns(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


@dataclass(frozen=True)
class OralChoicePattern:
    value: str
    patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class OralChoiceResolution:
    choice: str | None = None
    rejected: tuple[str, ...] = ()
    ambiguous: bool = False
    mentioned: bool = False


@dataclass
class _Mention:
    value: str
    clause: int = field(default=0)


def resolve_oral_choice(value: str, choices: tuple[OralChoicePattern, ...]) -> OralChoiceResolution:
    """Resolve the last independently affirmative choice. Two choices in one clause are
    ambiguous."""
    rejected: list[str] = []
    rejected_mentions: list[_Mention] = []
    affirmative: list[_Mention] = []
    mentioned = False
    ambiguous_clauses: list[int] = []

    for clause_index, clause in enumerate(oral_decision_clause_details(value)):
        hits = [
            choice.value
            for choice in choices
            if matches_oral_patterns(clause.text, choice.patterns)
        ]
        if not hits:
            continue
        mentioned = True
        distinct = list(dict.fromkeys(hits))
        if oral_clause_is_non_committal(clause.raw):
            ambiguous_clauses.append(clause_index)
            continue
        if oral_clause_has_negation(clause.text):
            for hit in distinct:
                if hit not in rejected:
                    rejected.append(hit)
                rejected_mentions.append(_Mention(value=hit, clause=clause_index))
            continue
        if len(distinct) != 1:
            ambiguous_clauses.append(clause_index)
            continue
        affirmative.append(_Mention(value=distinct[0], clause=clause_index))

    viable = [
        item
        for item in affirmative
        if not any(
            rejection.value == item.value and rejection.clause > item.clause
            for rejection in rejected_mentions
        )
    ]
    last_affirmative = viable[-1].clause if viable else -1
    last_ambiguous = ambiguous_clauses[-1] if ambiguous_clauses else -1
    if last_ambiguous > last_affirmative:
        return OralChoiceResolution(rejected=tuple(rejected), ambiguous=True, mentioned=mentioned)
    if not viable:
        return OralChoiceResolution(
            rejected=tuple(rejected), ambiguous=bool(ambiguous_clauses), mentioned=mentioned
        )
    last_clause = viable[-1].clause
    final_values = list(dict.fromkeys(item.value for item in viable if item.clause == last_clause))
    if len(final_values) == 1:
        return OralChoiceResolution(
            choice=final_values[0], rejected=tuple(rejected), mentioned=mentioned
        )
    return OralChoiceResolution(rejected=tuple(rejected), ambiguous=True, mentioned=mentioned)
