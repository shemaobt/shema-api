"""Mother-tongue practice as an app-owned process fact.

A scene is marked practiced only after an app-authored invitation bound to that scene,
confirmed by a completed-practice report, a bound completion word, or substantial audio
confidently recognized as not being the bridge language. The system never turns language
detection into a claim that it understood the content — it does not understand the team's
mother tongue at all. Ported from ``src/comprehension/practice.ts``.
"""

from __future__ import annotations

import re
import unicodedata

from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.oral_decision import (
    oral_clause_has_negation,
    oral_clause_is_non_committal,
    oral_decision_clauses,
    oral_utterance_is_interrogative,
)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^\w]+", " ", stripped.casefold(), flags=re.UNICODE).strip()


_AFFIRMATIVE = re.compile(
    r"^(sim|claro|isso|isso mesmo|ja|ja fizemos|fizemos|pronto|terminamos|acabamos"
    r"|yes|yeah|we did|already did|done|finished|ready|sure)$"
)
_PRACTICE = re.compile(r"\b(ensai|pratic|recont|tent\w*\s+cont|rehears|practic|retell)\w*")
_MOTHER_TONGUE = re.compile(
    r"\b(lingua de voces|lingua materna|lingua da equipe|terena|own language|mother tongue"
    r"|team language)\b"
)
_CONFIRMATION = re.compile(
    r"\b(ja|conseguiram|termin\w*|acabar\w*|fizeram|tentaram|did you|have you"
    r"|were you able|finish\w*)\b"
)
_COMPLETION_TOKEN_INVITATION = re.compile(
    r"\b(?:pronto|pronta|prontos|prontas|digam\s+pronto|avisem|quando\s+conclu\w*"
    r"|quando\s+estiver\w*\s+pront\w*|ready|say\s+ready|done|when\s+you\s+are\s+done"
    r"|let\s+me\s+know)\b"
)
_COMPLETION_TOKEN = re.compile(
    r"^(?:pronto|pronta|prontos|prontas|terminamos|acabamos|concluimos|ready|done"
    r"|finished|we\s+are\s+done|we\s+finished)$"
)
_SEGMENT_BOUNDARY = re.compile(r"[,;.!?\n]+")
_COMPLETED_REPORT = (
    re.compile(
        r"\b(ja|acabamos\s+de|terminamos\s+de)\b.{0,40}\b(ensai|pratic|recont|tent\w*\s+cont)\w*"
    ),
    re.compile(
        r"\b(we\s+already|we\s+did|we\s+have|we\s+finished)\b.{0,40}"
        r"\b(rehears|practic|retell|tried\s+\w*\s*tell)\w*"
    ),
)
_FUTURE_REPORT = (
    re.compile(
        r"\b(vamos|iremos|queremos|pretendemos|podemos)\b.{0,32}\b(ensai|pratic|recont|tent\w*\s+cont)\w*"
    ),
    re.compile(
        r"\b(we\s+will|we'll|we\s+are\s+going\s+to|we\s+want\s+to|we\s+plan\s+to|we\s+can)\b"
        r".{0,32}\b(rehears|practic|retell|try\s+\w*\s*tell)\w*"
    ),
)


def guide_invited_mother_tongue_practice(guide_utterance: str) -> bool:
    text = _normalize(guide_utterance)
    return bool(_PRACTICE.search(text) and _MOTHER_TONGUE.search(text))


def _oral_segments(utterance: str) -> list[str]:
    """Split a spoken confirmation at the boundaries a listener hears.

    Commas count alongside the strong stops: a team that answers "pronto, terminamos"
    said the completion word, and matching only the whole utterance would lose it.
    """
    return [
        segment
        for segment in (_normalize(part) for part in _SEGMENT_BOUNDARY.split(utterance))
        if segment
    ]


def _explicit_completed_practice_report(team_utterance: str) -> bool:
    """The team reports its own finished practice in plain speech.

    Naming the language is the Guide's job, not the team's — the invitation already bound
    the scene and the language, so the report is read for a completed practice alone.
    """
    whole = _normalize(team_utterance)
    if not _PRACTICE.search(whole):
        return False
    if oral_utterance_is_interrogative(team_utterance):
        return False
    return any(
        not oral_clause_has_negation(clause)
        and not oral_clause_is_non_committal(clause)
        and not any(pattern.search(clause) for pattern in _FUTURE_REPORT)
        and any(pattern.search(clause) for pattern in _COMPLETED_REPORT)
        for clause in oral_decision_clauses(team_utterance)
    )


def confirms_completed_mother_tongue_practice(
    previous_guide_utterance: str, team_utterance: str
) -> bool:
    """A bare yes can establish a process fact only when bound to a direct, validated
    question about already completed mother-tongue practice. It never becomes semantic
    passage evidence.

    The team's answer is read segment by segment, so a confirmation spoken as part of a
    longer sentence still counts. Reading by segment costs the anchoring that used to
    refuse a negative on its own, so a question, a hedge or any negation anywhere in the
    answer refuses it explicitly instead: "sim, mas ainda não" is not a finished practice.
    """
    guide = _normalize(previous_guide_utterance)
    if oral_utterance_is_interrogative(team_utterance) or oral_clause_is_non_committal(
        team_utterance
    ):
        return False
    scoped_practice = bool(_PRACTICE.search(guide) and _MOTHER_TONGUE.search(guide))
    direct_confirmation = scoped_practice and bool(_CONFIRMATION.search(guide))
    completion_token = scoped_practice and bool(_COMPLETION_TOKEN_INVITATION.search(guide))
    if not direct_confirmation and not completion_token:
        return False
    if _explicit_completed_practice_report(team_utterance):
        return True
    segments = _oral_segments(team_utterance)
    if any(oral_clause_has_negation(segment) for segment in segments):
        return False
    if completion_token and any(_COMPLETION_TOKEN.match(segment) for segment in segments):
        return True
    return direct_confirmation and any(_AFFIRMATIVE.match(segment) for segment in segments)


MOTHER_TONGUE_PRACTICE_PROMPT = (
    "Agora ensaiem juntos esta cena na língua de vocês. Quando terminarem, digam somente: pronto."
)


def is_exact_mother_tongue_practice_prompt(text: str) -> bool:
    return _normalize(text) == _normalize(MOTHER_TONGUE_PRACTICE_PROMPT)


def confident_non_bridge_audio_completes_scoped_practice(
    probe: ActiveProbe | None, confidently_non_bridge: bool
) -> bool:
    """A confident non-bridge-language recording is process evidence only when it answers
    the exact app-authored practice probe. It can mark that scoped practice happened, but
    can never become semantic evidence or mark an unknown/all-scenes scope."""
    return confidently_non_bridge and (
        probe is not None and probe.purpose is ProbePurpose.MOTHER_TONGUE_PRACTICE
    )


def practiced_scenes_authorized_by_probe(probe: ActiveProbe, practice_reported: bool) -> list[str]:
    return list(probe.practice_scene_ids) if practice_reported else []
