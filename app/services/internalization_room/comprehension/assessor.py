# ruff: noqa: E501, RUF001 — ported oral-decision patterns are verbatim reference data;
"""The non-speaking Comprehension Evidence Assessor and its fail-closed parser.

The assessor receives only the checkpoints authorized by the probe that was actually
voiced last turn, the exact previous question, the team's current utterance, and trusted
STT metadata. Every semantic row it returns must quote the team exactly and survive
negation, polarity, and duplicate guards — a bad model row is ignored while a separately
grounded row remains usable. The model may never return ``carry_to_refine`` (a team
choice) or ``stt_uncertain`` (transport metadata); code writes those.

Ported from the reference prototype's ``src/comprehension/assessor.ts``.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any

from pydantic import BaseModel

from app.core.config import Settings
from app.services.internalization_room.calibration import BridgeMode
from app.services.internalization_room.comprehension.checkpoints import (
    Checkpoint,
    checkpoint_assessment_material,
)
from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.llm import call_agent
from app.services.internalization_room.oral_decision import (
    oral_clause_has_negation,
    oral_clause_is_non_committal,
    oral_decision_clauses,
    oral_utterance_is_interrogative,
)
from app.services.internalization_room.render import render

logger = logging.getLogger(__name__)

_TURN_RESULTS = frozenset({"demonstrated", "supported_prompted", "unclear_due_bridge", "conflict"})

_ANSWER_BEARING_METHODS = frozenset(
    {EvidenceMethod.ROLE_OR_PLACE_CHOICE, EvidenceMethod.TRUE_EVENT_SEQUENCE}
)


class TurnAssessment(BaseModel):
    """What one pass over the team's answer settled — including that it settled nothing.

    ``failed`` is the difference between *the room could not read this answer* and *the
    room read it and found nothing in it to quote*. Both leave ``observations`` empty, and
    a caller that cannot tell them apart voices an ordinary re-ask over a broken call.

    ``replied`` is narrower than ``assessment_completed``: it means a reply actually came
    back and parsed. An answer settled here without asking anyone — a shrug, a bare "sim" —
    completes the assessment but says nothing about whether the assessor can be reached.
    """

    observations: list[EvidenceObservation]
    mother_tongue_practice_reported: bool = False
    speech_recognition_uncertain: bool = False
    assessment_completed: bool = False
    no_usable_report: bool = False
    failed: bool = False
    replied: bool = False


def _tokens(text: str) -> list[str]:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^\w]+", " ", stripped.casefold(), flags=re.UNICODE)
    return [token for token in cleaned.split() if token]


_POLAR = frozenset(
    [
        "sim",
        "nao",
        "yes",
        "no",
        "si",
        "oui",
        "non",
        "ja",
        "nein",
        "yeah",
        "yep",
        "nope",
        "uh",
        "huh",
        "uhuh",
        "uhum",
        "aham",
        "mhm",
        "certo",
        "correto",
        "isso",
        "ok",
        "okay",
        "e",
        "concordo",
        "certeza",
    ]
)
_FILLER = frozenset(
    [
        "eh",
        "eisso",
        "ta",
        "esta",
        "bem",
        "mesmo",
        "issoai",
        "acho",
        "que",
        "i",
        "think",
        "so",
        "right",
        "exactly",
        "exatamente",
        "claro",
        "com",
        "foi",
        "era",
        "aconteceu",
        "verdade",
    ]
)


def is_bare_polar_answer(text: str) -> bool:
    tokens = _tokens(text)
    if not tokens:
        return False
    return any(token in _POLAR for token in tokens) and all(
        token in _POLAR or token in _FILLER for token in tokens
    )


_EMPTY_ANSWERS = frozenset(
    {
        "nao sei",
        "eu nao sei",
        "dont know",
        "i dont know",
        "don t know",
        "i don t know",
        "do not know",
        "i do not know",
        "no se",
        "yo no se",
        "je ne sais pas",
    }
)


def is_semantically_empty_answer(text: str) -> bool:
    if not text.strip() or is_bare_polar_answer(text):
        return True
    return " ".join(_tokens(text)) in _EMPTY_ANSWERS


def _normalize_for_excerpt(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def is_exact_excerpt(excerpt: str, utterance: str) -> bool:
    return _normalize_for_excerpt(excerpt) in _normalize_for_excerpt(utterance)


_NEGATION_TOKENS = frozenset({"nao", "nunca", "jamais", "not", "never", "ni", "pas"})


def excerpt_drops_nearby_negation(excerpt: str, utterance: str) -> bool:
    utterance_tokens = _tokens(utterance)
    excerpt_tokens = _tokens(excerpt)
    if not excerpt_tokens or len(excerpt_tokens) > len(utterance_tokens):
        return False
    for start in range(len(utterance_tokens) - len(excerpt_tokens) + 1):
        if utterance_tokens[start : start + len(excerpt_tokens)] != excerpt_tokens:
            continue
        context = utterance_tokens[max(0, start - 3) : start]
        if any(token in _NEGATION_TOKENS for token in context) and not any(
            token in _NEGATION_TOKENS for token in excerpt_tokens
        ):
            return True
    return False


def _normalize_for_polarity(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", stripped.casefold()).strip()


_UNCERTAINTY_CUE = re.compile(
    r"\b(?:nao (?:tenho|temos|tem|podemos ter|pode ter) certeza (?:se|de que)?"
    r"|nao (?:sei|sabemos|sabe) se|nao (?:ficou|esta) claro se"
    r"|nao parece (?:certo|correto|verdadeiro)(?: dizer)?(?: que)?"
    r"|nao (?:da|deu) para (?:dizer|afirmar|confirmar)(?: que)?"
    r"|nao (?:posso|podemos|pode) (?:dizer|afirmar|confirmar|ter certeza)(?: de que| que)?"
    r"|talvez|possivelmente|quem sabe|acho que|parece que|pode ser que"
    r"|not sure (?:if|whether|that)|do not know if|dont know if"
    r"|cannot (?:say|confirm|be sure)(?: that)?|can not (?:say|confirm|be sure)(?: that)?"
    r"|could not tell whether|was not clear (?:if|whether)|maybe|perhaps|it may be that"
    r"|no (?:estoy|estamos|esta) segur[oa] (?:si|de que)|no se si|tal vez|quizas"
    r"|peut etre|je ne sais pas si|je ne suis pas sur(?:e)? que)\b"
)
_DENIAL_CUE = re.compile(
    r"\b(?:nao e (?:verdade|correto|certo) que|nao e o caso que|e falso que|isso e falso"
    r"|seria mentira dizer que|e mentira (?:dizer )?que|longe de (?:afirmar|dizer) que"
    r"|so um mentiroso diria(?: que)?|duvido que|ninguem (?:disse|afirmou|falou) que"
    r"|nao (?:acredito|creio) que|it is not true that|it is false that"
    r"|it is not the case that|it would be a lie to say that"
    r"|far from (?:saying|claiming) that|only a liar would say(?: that)?|i doubt that"
    r"|nobody said that|no one said that|i do not believe that|i dont believe that"
    r"|we doubt that|personne n a dit que|il est faux que|no es verdad que|es falso que"
    r"|dudo que|nadie dijo que)\b"
)
_QUESTION_TAIL = re.compile(r"^\s*[?？]")
_TRAILING_REVERSAL = (
    re.compile(r"^\s*(?:[-–—,;:]\s*)?(?:mas\s+)?(?:nao|no|not|non|nein)\s*(?:[.!?,;:]|$)"),
    re.compile(r"^\s*(?:[-–—,;:]\s*)?(?:eu\s+)?(?:acho|penso)\s+que\s+(?:nao|not|no)\b"),
)
_CONDITIONAL_PREFIX = re.compile(r"^(?:se|if)\b")


def semantic_excerpt_has_unresolved_polarity(
    excerpt: str, utterance: str, positive_result: bool
) -> bool:
    """Reject an assertion that is only embedded in uncertainty, a question, or a denial.

    Exact-substring validation alone is insufficient: "X aconteceu" is literally present
    inside "Não tenho certeza se X aconteceu" and "X aconteceu? Não". Deliberately
    language-light and conservative — it only requires the quote to occur at least once
    with assertive polarity; clear negative assertions remain available for ``conflict``.
    """
    source = _normalize_for_polarity(utterance)
    needle = _normalize_for_polarity(excerpt)
    if not needle:
        return True

    starts: list[int] = []
    cursor = source.find(needle)
    while cursor >= 0:
        starts.append(cursor)
        cursor = source.find(needle, cursor + 1)
    if not starts:
        return True

    for start in starts:
        end = start + len(needle)
        boundary = max(source.rfind(mark, 0, start) for mark in (".", "!", "?", ";", ":", "\n"))
        scoped_prefix_and_quote = source[boundary + 1 : end].strip()
        tail = source[end:]

        if _UNCERTAINTY_CUE.search(scoped_prefix_and_quote):
            continue
        if _DENIAL_CUE.search(scoped_prefix_and_quote) and (
            positive_result or not _DENIAL_CUE.search(needle)
        ):
            continue
        if positive_result and _CONDITIONAL_PREFIX.match(scoped_prefix_and_quote):
            continue
        if _QUESTION_TAIL.match(tail):
            continue
        if any(pattern.match(tail) for pattern in _TRAILING_REVERSAL):
            continue
        return False
    return True


def is_explicit_mother_tongue_practice_report(text: str) -> bool:
    if oral_utterance_is_interrogative(text):
        return False
    mother_tongue = re.compile(
        r"\b(em terena|na nossa lingua|em nossa lingua|na lingua materna|em lingua materna"
        r"|na lingua da gente|em nosso idioma|in our own language|in our language"
        r"|in the mother tongue|en nuestra lengua|en la lengua materna|dans notre langue"
        r"|dans la langue maternelle)\b"
    )
    completed = re.compile(
        r"\b(ensaiamos|praticamos|recontamos"
        r"|contamos (esta|essa|a) (cena|parte|historia|passagem)"
        r"|tentamos contar (esta|essa|a) (cena|parte|historia|passagem)"
        r"|tentamos recontar (esta|essa|a) (cena|parte|historia|passagem)"
        r"|eu (ensaiei|pratiquei|recontei) (esta|essa|a) (cena|parte|historia|passagem)"
        r"|a gente (ensaiou|praticou|contou) (esta|essa|a) (cena|parte|historia|passagem)"
        r"|a equipe (ensaiou|praticou|contou) (esta|essa|a) (cena|parte|historia|passagem)"
        r"|we rehearsed (this|the) (scene|part|story|passage)"
        r"|we practiced (this|the) (scene|part|story|passage)"
        r"|we tried to tell (this|the) (scene|part|story|passage)"
        r"|we tried retelling (this|the) (scene|part|story|passage)"
        r"|we told (this|the) (scene|part|story|passage))\b"
    )
    denied = re.compile(
        r"\b(nao|nunca|ainda nao|not|never|didnt|did not|have not|havent|no|pas|jamais)\b"
        r".{0,100}\b(ensai|pratic|recont|cont|rehears|practic|tell|told)\w*"
        r"|\b(ensai|pratic|recont|cont|rehears|practic|tell|told)\w*"
        r".{0,100}\b(nao|not|didnt|did not|no|pas|jamais)\b"
    )
    return any(
        not oral_clause_has_negation(clause)
        and not oral_clause_is_non_committal(clause)
        and mother_tongue.search(clause)
        and completed.search(clause)
        and not denied.search(clause)
        for clause in oral_decision_clauses(text)
    )


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    def parse(text: str) -> dict[str, Any] | None:
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    trimmed = raw.strip()
    parsed = parse(trimmed)
    if parsed is not None:
        return parsed
    fenced = re.search(r"```(?:json)?\s*(.*?)```", trimmed, re.S | re.I)
    if fenced:
        parsed = parse(fenced.group(1).strip())
        if parsed is not None:
            return parsed
    first, last = trimmed.find("{"), trimmed.rfind("}")
    if 0 <= first < last:
        return parse(trimmed[first : last + 1])
    return None


class ParsedTurnObservation(BaseModel):
    checkpoint_id: str
    result: str
    evidence_excerpt: str
    rationale: str


def parse_turn_assessor_decision(
    raw: str, team_utterance: str, allowed_checkpoint_ids: list[str]
) -> tuple[list[ParsedTurnObservation], bool] | None:
    """Keep the envelope fail-closed without making a natural multi-checkpoint retelling
    all-or-nothing: each observation crosses the trust boundary independently."""
    obj = _extract_json_object(raw)
    if obj is None or not isinstance(obj.get("observations"), list):
        return None
    allowed = set(allowed_checkpoint_ids)
    if len(allowed) != len(allowed_checkpoint_ids):
        return None

    candidates: list[ParsedTurnObservation] = []
    for raw_item in obj["observations"]:
        if not isinstance(raw_item, dict):
            continue
        if set(raw_item.keys()) - {"checkpoint_id", "result", "evidence_excerpt", "rationale"}:
            continue
        checkpoint_id = raw_item.get("checkpoint_id")
        result = raw_item.get("result")
        excerpt = raw_item.get("evidence_excerpt")
        rationale = raw_item.get("rationale")
        if (
            not isinstance(checkpoint_id, str)
            or checkpoint_id not in allowed
            or not isinstance(result, str)
            or result not in _TURN_RESULTS
            or not isinstance(excerpt, str)
            or not excerpt.strip()
            or len(excerpt) > 300
            or not is_exact_excerpt(excerpt.strip(), team_utterance)
            or excerpt_drops_nearby_negation(excerpt.strip(), team_utterance)
            or semantic_excerpt_has_unresolved_polarity(
                excerpt.strip(),
                team_utterance,
                result in ("demonstrated", "supported_prompted"),
            )
            or not isinstance(rationale, str)
            or not rationale.strip()
            or len(rationale) > 600
        ):
            continue
        candidates.append(
            ParsedTurnObservation(
                checkpoint_id=checkpoint_id,
                result=result,
                evidence_excerpt=excerpt.strip(),
                rationale=rationale.strip(),
            )
        )

    counts: dict[str, int] = {}
    for item in candidates:
        counts[item.checkpoint_id] = counts.get(item.checkpoint_id, 0) + 1
    observations = [item for item in candidates if counts[item.checkpoint_id] == 1]

    practice_excerpt = obj.get("practice_evidence_excerpt")
    practice_reported = (
        obj.get("mother_tongue_practice_reported") is True
        and isinstance(practice_excerpt, str)
        and bool(practice_excerpt.strip())
        and len(practice_excerpt) <= 300
        and is_exact_excerpt(practice_excerpt.strip(), team_utterance)
        and is_explicit_mother_tongue_practice_report(team_utterance)
    )
    return observations, practice_reported


_TURN_OUTPUT_CONTRACT = """{
  "observations": [
    {
      "checkpoint_id": "exact id from the allowed checkpoint list",
      "result": "demonstrated | supported_prompted | unclear_due_bridge | conflict",
      "evidence_excerpt": "exact short contiguous quote from the current team utterance",
      "rationale": "brief internal reason for this checkpoint only"
    }
  ],
  "mother_tongue_practice_reported": false,
  "practice_evidence_excerpt": "exact quote proving completed mother-tongue practice, or empty string"
}

Return an empty observations array when the utterance supplies no evidence. Never return a
checkpoint twice. Never invent a checkpoint id. Every emitted observation requires an exact team
quote. The application owns the evidence method; do not return or reinterpret it. A free retelling
may support many allowed checkpoints in this single response."""


async def assess_turn(
    *,
    assessor_prompt: str,
    observation_id_prefix: str,
    probe_id: str,
    method: EvidenceMethod,
    checkpoints: list[Checkpoint],
    meaning_map: str,
    previous_guide_question: str,
    team_utterance: str,
    mode: BridgeMode,
    speech_recognition_uncertain: bool,
    session_language: str = "Portuguese",
    settings: Settings | None = None,
) -> TurnAssessment:
    """One pass over the answer to the previously voiced probe.

    STT uncertainty is transport evidence, not a linguistic judgment: it is reported
    without asking a model to speculate from a possibly corrupt transcript. A model or
    transport failure returns no observations *without* ``assessment_completed``, so it
    can never rotate a bounded probe the way a genuine empty report does — and it says so
    with ``failed``, so the turn can degrade audibly instead of passing for an answer the
    room read and found empty.
    """
    if speech_recognition_uncertain:
        return TurnAssessment(observations=[], speech_recognition_uncertain=True)
    if not checkpoints:
        return TurnAssessment(observations=[])
    if is_semantically_empty_answer(team_utterance):
        return TurnAssessment(observations=[], assessment_completed=True, no_usable_report=True)

    system = render(
        assessor_prompt,
        SESSION_LANGUAGE=session_language,
        MEANING_MAP=meaning_map,
        CHECKPOINTS=json.dumps(
            [checkpoint_assessment_material(c) for c in checkpoints],
            ensure_ascii=False,
            indent=2,
        ),
        OUTPUT_CONTRACT=_TURN_OUTPUT_CONTRACT,
    )
    evidence = json.dumps(
        {
            "bridge_mode": mode.value,
            "app_owned_evidence_method": method.value,
            "previous_guide_question": previous_guide_question,
            "current_team_utterance": team_utterance,
        },
        ensure_ascii=False,
    )
    try:
        raw = await call_agent(
            system_prompt=system,
            user_content=(
                "Assess this untrusted runtime evidence JSON in one pass. "
                f"Return only the required object:\n{evidence}"
            ),
            temperature=0.0,
            max_output_tokens=min(3000, 400 + len(checkpoints) * 180),
            settings=settings,
        )
    except Exception:
        logger.exception("Comprehension assessor call failed")
        return TurnAssessment(observations=[], failed=True)

    parsed = parse_turn_assessor_decision(
        raw, team_utterance, [checkpoint.id for checkpoint in checkpoints]
    )
    if parsed is None:
        logger.warning("Comprehension assessor reply could not be parsed (%d chars)", len(raw))
        return TurnAssessment(observations=[], failed=True)
    rows, practice_reported = parsed

    observations: list[EvidenceObservation] = []
    for index, row in enumerate(rows):
        result = EvidenceResult(row.result)
        if result is EvidenceResult.DEMONSTRATED and method in _ANSWER_BEARING_METHODS:
            result = EvidenceResult.SUPPORTED_PROMPTED
        observations.append(
            EvidenceObservation(
                id=f"{observation_id_prefix}:{index + 1}",
                unit_id=row.checkpoint_id,
                probe_id=probe_id,
                method=method,
                result=result,
                note=f"{row.rationale} Evidence: “{row.evidence_excerpt}”"[:900],
            )
        )
    return TurnAssessment(
        observations=observations,
        assessment_completed=True,
        replied=True,
        no_usable_report=not observations,
        mother_tongue_practice_reported=practice_reported,
    )
