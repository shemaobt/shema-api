# ruff: noqa: E501 — ported oral-decision patterns are verbatim reference data;
"""Deterministic, session-local bridge-language calibration.

The team answers an oral choice about the WORKING METHOD, not a proficiency test. This
parser deliberately recognizes only clear task-shaped preferences. The pure parser can
report a pending result, but the one-shot application boundary converts that uncertainty
to the adaptive fallback: the Voice never turns an unclear first answer into a repeated
menu. After the choice, the mode changes only on an explicit, spontaneous team request —
"sim", story speech, a question, or a bad transcript can never switch it.

Ported from the reference prototype's ``src/comprehension/calibration.ts``.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass

from app.services.internalization_room.languages import FLOOR
from app.services.internalization_room.oral_decision import (
    normalize_oral_decision,
    oral_clause_has_negation,
    oral_clause_is_non_committal,
    oral_decision_clauses,
    oral_utterance_is_interrogative,
)


class BridgeMode(enum.StrEnum):
    CALIBRATION_PENDING = "calibration_pending"
    FULL_RETELL = "full_retell"
    GUIDED_MICROCHECKS = "guided_microchecks"
    ADAPTIVE = "adaptive"


SELECTED_MODES = frozenset(
    {BridgeMode.FULL_RETELL, BridgeMode.GUIDED_MICROCHECKS, BridgeMode.ADAPTIVE}
)


def is_selected_bridge_mode(value: object) -> bool:
    """Accept only a real, non-pending bridge mode at a session-intake boundary."""
    return isinstance(value, str) and value in {mode.value for mode in SELECTED_MODES}


@dataclass(frozen=True)
class CalibrationResolution:
    mode: BridgeMode
    explicit: bool


def _compiled(patterns: list[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern) for pattern in patterns)


_SHORT_QUESTION = _compiled(
    [
        r"\b(pergunta|perguntas)\s+(curta|curtas|pequena|pequenas|simples)\b",
        r"\b(uma|1)\s+(pergunta|coisa)\s+(por vez|de cada vez)\b",
        r"\b(poucas?|algumas?)\s+palavras?\b",
        r"\b(short|small|simple)\s+questions?\b",
        r"\b(one|1)\s+(question|thing)\s+at\s+a\s+time\b",
        r"\bguided(?:\s+microchecks?)?\b",
        r"\b(a\s+)?segunda\s+(opcao|forma|maneira)\b",
        r"\b(the\s+)?second\s+(option|way)\b",
        r"^(a\s+)?segunda$",
        r"^(the\s+)?second$",
    ]
)

_FULL_RETELL = _compiled(
    [
        r"^(vamos\s+)?(contar|recontar|narrar)\s+(tudo|inteir[oa]|a\s+historia|a\s+passagem)(\s+em\s+portugues)?$",
        r"\b(historia|passagem|reconto)\s+(inteir[oa]|complet[oa])\b",
        r"\b(reconto|contagem|narrativa)\s+livre\b",
        r"^(let'?s\s+)?(tell|retell|narrate)\s+(it\s+)?(all|the\s+whole|the\s+story|the\s+passage)$",
        r"\b(full|free)\s+retell(?:ing)?\b",
        r"\b(conseguimos?|posso|podemos|quero|queremos|prefiro|preferimos)\s+(contar|recontar|narrar)\b",
        r"\b(we\s+can|i\s+can|we\s+want\s+to|i\s+want\s+to|we\s+prefer\s+to|i\s+prefer\s+to)\s+(tell|retell|narrate)\b",
        r"\b(a\s+)?primeira\s+(opcao|forma|maneira)\b",
        r"\b(the\s+)?first\s+(option|way)\b",
        r"^(a\s+)?primeira$",
        r"^(the\s+)?first$",
    ]
)

_ADAPTIVE = _compiled(
    [
        r"\bnao\s+sabemos?\b.{0,32}\b(vamos|podemos)\s+tentar\b",
        r"\b(nao\s+sei|nao\s+temos?\s+certeza|vamos\s+tentar|podemos\s+tentar|experimentar|tanto\s+faz)\b",
        r"\b(unsure|not\s+sure|let(?:'s|\s+us)\s+try|we\s+can\s+try|either\s+way)\b",
        r"\b(tentar|experimentar)\s+(a\s+)?primeira\s+cena\b.{0,24}\b(decidir|escolher)\b",
        r"\btry\s+the\s+first\s+scene\b.{0,24}\b(decide|choose)\b",
        r"\b(a\s+)?terceira\s+(opcao|forma|maneira)\b",
        r"\b(the\s+)?third\s+(option|way)\b",
        r"^(a\s+)?terceira$",
        r"^(the\s+)?third$",
        r"\badaptiv[oe]\b",
    ]
)

_REJECT_ADAPTIVE = _compiled(
    [
        r"\b(?:nao|nunca|jamais)\s+(?:(?:vamos|podemos|queremos|quero|prefiro|preferimos|iremos|pretendemos)\s+)?(?:tentar|experimentar)\b",
        r"\b(?:de\s+jeito\s+nenhum|de\s+maneira\s+alguma|de\s+modo\s+algum|em\s+hipotese\s+(?:alguma|nenhuma)|sob\s+nenhuma\s+circunstancia)\b.{0,48}\b(?:tentar|experimentar|terceira\s+(?:opcao|forma|maneira))\b",
        r"\b(?:nao|nunca|jamais)\b.{0,28}\b(?:a\s+)?terceira\s+(?:opcao|forma|maneira)\b",
        r"\b(?:do\s+not|don't|dont|will\s+not|won't|wont|cannot|can't|cant|never)\s+(?:(?:want|plan|choose)\s+to\s+)?try\b.{0,32}\bfirst\s+scene\b",
        r"\b(?:do\s+not|don't|dont|will\s+not|won't|wont|cannot|can't|cant|never)\b.{0,24}\b(?:want|choose|prefer)?\b.{0,16}\bthird\s+(?:option|way)\b",
        r"\b(?:under\s+no\s+circumstances|by\s+no\s+means|no\s+way)\b.{0,48}\b(?:try|third\s+(?:option|way))\b",
    ]
)

_EXPLICIT_UNCERTAINTY_THEN_TRIAL = _compiled(
    [
        r"\bnao\s+sabemos?(?:\s+ainda)?(?:\s+mas)?\s+(?:vamos|podemos)\s+tentar\b",
        r"\bnao\s+temos?\s+certeza(?:\s+ainda)?(?:\s+mas)?\s+(?:vamos|podemos)\s+tentar\b",
        r"\b(?:we\s+are\s+)?not\s+sure(?:\s+yet)?(?:\s+but)?\s+(?:let'?s|let\s+us|we\s+can|we\s+will)\s+try\b",
    ]
)

_REJECT_FULL_RETELL = _compiled(
    [
        r"\b(nao|nunca|jamais)\b.{0,24}\b(consigo|conseguimos|quero|queremos|posso|podemos)\b.{0,12}\b(contar|recontar|narrar)\b.{0,24}\b(tudo|a\s+historia|a\s+passagem|inteir[oa])\b",
        r"\b(cannot|can't|cant|do\s+not|don't|dont|not\s+able\s+to)\b.{0,32}\b(tell|retell|narrate)\b.{0,24}\b(all|whole|story|passage)\b",
    ]
)

_REJECT_GUIDED = _compiled(
    [
        r"\b(nao|nunca|jamais)\b.{0,24}\b(quero|queremos|prefiro|preferimos|gostaria|gostariamos)\b.{0,20}\b(uma\s+)?perguntas?\s+(curtas?|pequenas?|simples)\b",
        r"\b(do\s+not|don't|dont|would\s+not|wouldn't|wouldnt)\b.{0,24}\b(want|prefer|like)\b.{0,20}\b(one\s+)?(short|small|simple)\s+questions?\b",
    ]
)

_SWITCH_TO_GUIDED = _compiled(
    [
        r"\b(mudar|trocar)\b.{0,28}\b(para\s+)?(uma\s+)?perguntas?\s+(curtas?|pequenas?|simples)\b",
        r"\b(prefiro|preferimos|quero|queremos|podemos|gostaria|gostariamos)\b.{0,28}\b(uma\s+)?perguntas?\s+(curtas?|pequenas?|simples)\b",
        r"^(por favor\s+)?(uma\s+)?perguntas?\s+(curtas?|pequenas?|simples)(\s+por favor)?$",
        r"\b(switch|change)\b.{0,28}\b(to\s+)?(one\s+)?(short|small|simple)\s+questions?\b",
        r"\b(i|we)\s+(prefer|want|would like)\b.{0,28}\b(one\s+)?(short|small|simple)\s+questions?\b",
        r"^(please\s+)?(one\s+)?(short|small|simple)\s+questions?(\s+please)?$",
        r"^(a\s+)?segunda\s+(opcao|forma|maneira)$",
        r"^(the\s+)?second\s+(option|way)$",
        r"\b(?:quero|queremos|prefiro|preferimos|escolho|escolhemos)\b.{0,20}\b(?:a\s+)?segunda\s+(?:opcao|forma|maneira)\b",
        r"\b(?:i|we)\s+(?:want|prefer|choose)(?:\s+to\s+choose)?\b.{0,20}\b(?:the\s+)?second\s+(?:option|way)\b",
        r"^(a\s+)?segunda$",
        r"^(the\s+)?second$",
    ]
)

_SWITCH_TO_FULL = _compiled(
    [
        r"\b(mudar|trocar)\b.{0,28}\b(para\s+)?(um\s+)?(reconto|contagem|narrativa)\s+livre\b",
        r"\b(prefiro|preferimos|quero|queremos|podemos|gostaria|gostariamos)\b.{0,36}\b(voltar\s+a\s+)?(contar|recontar|narrar)\b.{0,24}\b(a\s+)?(historia|passagem)\s+inteir[oa]\b",
        r"\b(prefiro|preferimos|quero|queremos|podemos|gostaria|gostariamos)\b.{0,28}\b(contar|recontar|narrar)\s+(tudo|livremente|naturalmente)\b",
        r"^(por favor\s+)?(reconto|contagem|narrativa)\s+livre(\s+por favor)?$",
        r"\b(switch|change)\b.{0,28}\b(to\s+)?(a\s+)?(free|full)\s+retell(?:ing)?\b",
        r"\b(i|we)\s+(prefer|want|would like)\b.{0,36}\b(return\s+to\s+)?(a\s+)?(free|full)\s+retell(?:ing)?\b",
        r"\b(i|we)\s+(prefer|want|would like)\s+to\b.{0,28}\b(tell|retell|narrate)\s+(it\s+)?(all|freely|naturally)\b",
        r"^(please\s+)?(a\s+)?(free|full)\s+retell(?:ing)?(\s+please)?$",
        r"^(continuar\s+)?(contando|recontando)\s+(livremente|naturalmente)$",
        r"^(continue\s+)?(telling|retelling)\s+(freely|naturally)$",
        r"^(?:quero|queremos|prefiro|preferimos|vamos)\s+(?:continuar\s+)?(?:contar|recontar)\s+em\s+portugues$",
        r"^(?:i|we)\s+(?:want|prefer|would like)\s+to\s+(?:continue\s+)?(?:tell|retell)\s+in\s+english$",
        r"^(a\s+)?primeira\s+(opcao|forma|maneira)$",
        r"^(the\s+)?first\s+(option|way)$",
        r"\b(?:quero|queremos|prefiro|preferimos|escolho|escolhemos)\b.{0,20}\b(?:a\s+)?primeira\s+(?:opcao|forma|maneira)\b",
        r"\b(?:i|we)\s+(?:want|prefer|choose)(?:\s+to\s+choose)?\b.{0,20}\b(?:the\s+)?first\s+(?:option|way)\b",
        r"^(a\s+)?primeira$",
        r"^(the\s+)?first$",
    ]
)


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    if oral_clause_has_negation(text) or oral_clause_is_non_committal(text):
        return False
    return any(pattern.search(text) for pattern in patterns)


def _matches_raw(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def resolve_initial_calibration(transcript: str) -> CalibrationResolution:
    """Resolve the team's first task-shaped oral choice. Never infer a proficiency level."""
    text = normalize_oral_decision(transcript)
    if not text or oral_utterance_is_interrogative(transcript):
        return CalibrationResolution(mode=BridgeMode.CALIBRATION_PENDING, explicit=False)

    clauses = oral_decision_clauses(transcript)
    guided = any(
        not _matches_raw(clause, _REJECT_GUIDED) and _matches_any(clause, _SHORT_QUESTION)
        for clause in clauses
    )
    full = any(
        not _matches_raw(clause, _REJECT_FULL_RETELL) and _matches_any(clause, _FULL_RETELL)
        for clause in clauses
    )
    if guided and full:
        return CalibrationResolution(mode=BridgeMode.ADAPTIVE, explicit=True)
    if guided:
        return CalibrationResolution(mode=BridgeMode.GUIDED_MICROCHECKS, explicit=True)
    if full:
        return CalibrationResolution(mode=BridgeMode.FULL_RETELL, explicit=True)
    adaptive = any(
        not _matches_raw(clause, _REJECT_ADAPTIVE)
        and _matches_raw(clause, _ADAPTIVE)
        and (
            not oral_clause_is_non_committal(clause)
            or _matches_raw(clause, _EXPLICIT_UNCERTAINTY_THEN_TRIAL)
        )
        for clause in clauses
    )
    if adaptive:
        return CalibrationResolution(mode=BridgeMode.ADAPTIVE, explicit=True)
    return CalibrationResolution(mode=BridgeMode.CALIBRATION_PENDING, explicit=False)


def resolve_one_shot_calibration(transcript: str) -> CalibrationResolution:
    """Resolve the sole opening choice.

    An unclear, silent, or mixed answer selects the modest adaptive fallback immediately;
    it never authorizes the Voice to offer the method menu a second time.
    """
    resolved = resolve_initial_calibration(transcript)
    if resolved.mode is BridgeMode.CALIBRATION_PENDING:
        return CalibrationResolution(mode=BridgeMode.ADAPTIVE, explicit=False)
    return resolved


def resolve_bridge_mode_for_turn(
    current_mode: BridgeMode, transcript: str
) -> CalibrationResolution:
    """Honor only an explicit request to change an already selected track.

    Silence, STT uncertainty, grammar, brevity, and apparent fluency never change the
    mode. Adaptive remains team-chosen; it is not silently inferred here.
    """
    if current_mode is BridgeMode.CALIBRATION_PENDING:
        initial = resolve_initial_calibration(transcript)
        if initial.mode is not BridgeMode.CALIBRATION_PENDING:
            return initial

    text = normalize_oral_decision(transcript)
    if not text or oral_utterance_is_interrogative(transcript):
        return CalibrationResolution(mode=current_mode, explicit=False)

    clauses = oral_decision_clauses(transcript)
    guided = any(
        not _matches_raw(clause, _REJECT_GUIDED) and _matches_any(clause, _SWITCH_TO_GUIDED)
        for clause in clauses
    )
    full = any(
        not _matches_raw(clause, _REJECT_FULL_RETELL) and _matches_any(clause, _SWITCH_TO_FULL)
        for clause in clauses
    )
    if guided and not full:
        return CalibrationResolution(mode=BridgeMode.GUIDED_MICROCHECKS, explicit=True)
    if full and not guided:
        return CalibrationResolution(mode=BridgeMode.FULL_RETELL, explicit=True)
    return CalibrationResolution(mode=current_mode, explicit=False)


def bridge_mode_status_line(mode: BridgeMode) -> str:
    return f"BRIDGE MODE: {mode.value}"


def bridge_mode_validator_context(mode: BridgeMode) -> str:
    return f"[APP-OWNED SESSION STATE — not team speech]\n{bridge_mode_status_line(mode)}"


_CALIBRATION_QUESTION = {
    "pt": (
        "Quando trabalharmos as passagens, qual jeito fica melhor para vocês: "
        "contar naturalmente em português ou receber uma pergunta curta de cada vez?"
    ),
    "en": (
        "When we work through the passages, which suits you better: "
        "telling it back in your own words, or one short question at a time?"
    ),
    "es": (
        "Cuando trabajemos los pasajes, ¿qué les queda mejor: "
        "contarlo con sus propias palabras, o recibir una pregunta corta a la vez?"
    ),
}

_CALIBRATION_ACKNOWLEDGEMENT: dict[str, dict[BridgeMode, str]] = {
    "pt": {
        BridgeMode.FULL_RETELL: (
            "Certo. Nas passagens, vocês poderão contar naturalmente em português. "
            "Agora vamos ao panorama do livro."
        ),
        BridgeMode.GUIDED_MICROCHECKS: (
            "Certo. Nas passagens, vou fazer uma pergunta curta de cada vez. "
            "Agora vamos ao panorama do livro."
        ),
        BridgeMode.ADAPTIVE: (
            "Certo. Vamos começar de um jeito simples e ajustar o tamanho das perguntas "
            "quando for preciso. Agora vamos ao panorama do livro."
        ),
    },
    "en": {
        BridgeMode.FULL_RETELL: (
            "Good. In the passages you can tell it back in your own words. "
            "Now let us look at the book as a whole."
        ),
        BridgeMode.GUIDED_MICROCHECKS: (
            "Good. In the passages I will ask one short question at a time. "
            "Now let us look at the book as a whole."
        ),
        BridgeMode.ADAPTIVE: (
            "Good. We will start simply and adjust how long the questions are as we go. "
            "Now let us look at the book as a whole."
        ),
    },
    "es": {
        BridgeMode.FULL_RETELL: (
            "Bien. En los pasajes van a poder contarlo con sus propias palabras. "
            "Ahora vamos al panorama del libro."
        ),
        BridgeMode.GUIDED_MICROCHECKS: (
            "Bien. En los pasajes voy a hacer una pregunta corta a la vez. "
            "Ahora vamos al panorama del libro."
        ),
        BridgeMode.ADAPTIVE: (
            "Bien. Vamos a empezar de un modo sencillo y ajustamos el tamaño de las "
            "preguntas cuando haga falta. Ahora vamos al panorama del libro."
        ),
    },
}


def bridge_calibration_question(language: str = FLOOR) -> str:
    """The one method-choice question, in the language this session is being run in."""
    return _CALIBRATION_QUESTION.get(language, _CALIBRATION_QUESTION[FLOOR])


def is_bridge_calibration_question(text: str) -> bool:
    """Whether a line the room already said was the method-choice question.

    Any language's, not this session's. The text being matched was written on an earlier
    turn and is compared as an exact string, so a room whose language moved between deploys
    would otherwise stop recognising its own question and ask it again.
    """
    return text.strip() in {said.strip() for said in _CALIBRATION_QUESTION.values()}


def bridge_calibration_acknowledgement(mode: BridgeMode, language: str = FLOOR) -> str:
    """Fast app-owned acknowledgement for the panorama's one and only method-choice
    answer. It never travels through the Guide-Validator cycle."""
    said = _CALIBRATION_ACKNOWLEDGEMENT.get(language, _CALIBRATION_ACKNOWLEDGEMENT[FLOOR])
    return said.get(mode, said[BridgeMode.ADAPTIVE])
