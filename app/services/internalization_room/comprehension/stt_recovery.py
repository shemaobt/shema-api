# ruff: noqa: RUF001 — ported oral-decision patterns are verbatim reference data;
"""App-owned recovery for uncertain speech recognition during comprehension checks.

The recovery is scoped to the exact persisted semantic probe. It never creates semantic
evidence and never treats provider uncertainty as a team error. One uncertain transcript
may retry that probe once; a second uncertainty clears the semantic authorization and
moves to a process-only choice — a smaller question, or an explicitly open point for
Refine. Ported from ``src/comprehension/sttRecovery.ts``.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel

from app.core.exceptions import ValidationError
from app.services.internalization_room.comprehension.evidence import EvidenceMethod
from app.services.internalization_room.oral_decision import (
    OralChoicePattern,
    resolve_oral_choice,
)


class SttRecoveryState(BaseModel):
    probe_id: str
    checkpoint_ids: list[str]
    method: EvidenceMethod
    stage: Literal["retry_requested", "recovery_choice_pending"]


class SttRecoveryDecision(BaseModel):
    action: Literal["none", "retry_same_probe", "reduce_burden"]
    next_state: SttRecoveryState | None
    preserve_semantic_probe: bool


STT_RECOVERY_REDUCE_BURDEN_LINE = (
    "Ficou difícil de ouvir. Vocês preferem tentar com uma pergunta curta, "
    "ou deixar este ponto guardado para o Refine?"
)


def plan_stt_recovery(
    *,
    prior: SttRecoveryState | None,
    probe_id: str | None,
    checkpoint_ids: list[str],
    method: EvidenceMethod | None,
    transcript_uncertain: bool,
) -> SttRecoveryDecision:
    if not transcript_uncertain:
        return SttRecoveryDecision(action="none", next_state=None, preserve_semantic_probe=False)

    if not probe_id or not checkpoint_ids or method is None:
        kept = prior if prior is not None and prior.stage == "recovery_choice_pending" else None
        return SttRecoveryDecision(action="none", next_state=kept, preserve_semantic_probe=False)

    if any(not checkpoint_id.strip() for checkpoint_id in checkpoint_ids):
        raise ValidationError("STT recovery needs an explicit semantic checkpoint scope")
    scoped_ids = list(dict.fromkeys(checkpoint_ids))
    if prior is not None and prior.probe_id == probe_id and prior.stage == "retry_requested":
        return SttRecoveryDecision(
            action="reduce_burden",
            next_state=SttRecoveryState(
                stage="recovery_choice_pending",
                probe_id=probe_id,
                checkpoint_ids=scoped_ids,
                method=method,
            ),
            preserve_semantic_probe=False,
        )
    return SttRecoveryDecision(
        action="retry_same_probe",
        next_state=SttRecoveryState(
            stage="retry_requested",
            probe_id=probe_id,
            checkpoint_ids=scoped_ids,
            method=method,
        ),
        preserve_semantic_probe=True,
    )


def _normalize_choice_speech(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    lowered = stripped.lower().replace("’", "").replace("'", "")
    cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


_RECOVERY_CHOICES = (
    OralChoicePattern(
        value="smaller",
        patterns=(
            re.compile(r"\b(?:uma\s+)?perguntas?\s+curtas?\b"),
            re.compile(r"\bpergunta\s+(?:por\s+pergunta|de\s+cada\s+vez)\b"),
            re.compile(r"\b(?:one\s+)?short\s+questions?\b"),
            re.compile(r"\bquestions?\s+(?:one\s+at\s+a\s+time|by\s+question)\b"),
            re.compile(r"\b(?:primeira|primeiro)(?:\s+opcao)?\b"),
            re.compile(r"\b(?:opcao\s+(?:um|1)|first(?:\s+option)?|option\s+one)\b"),
        ),
    ),
    OralChoicePattern(
        value="carry",
        patterns=(
            re.compile(r"\b(?:deix\w*|lev\w*|guard\w*)\b.{0,80}\brefine\b"),
            re.compile(r"\brefine\b.{0,60}\b(?:deix\w*|lev\w*|guard\w*)\b"),
            re.compile(r"\b(?:leave|carry|keep|take)\b.{0,80}\brefine\b"),
            re.compile(r"\brefine\b.{0,60}\b(?:leave|carry|keep|take)\b"),
            re.compile(r"\b(?:segunda|segundo)(?:\s+opcao)?\b"),
            re.compile(r"\b(?:opcao\s+(?:dois|2)|second(?:\s+option)?|option\s+two)\b"),
        ),
    ),
)


def resolve_stt_recovery_choice(state: SttRecoveryState | None, team_utterance: str) -> str:
    """Accept only an explicit method/open-point choice; the two-option recovery question
    names both branches, so a polar answer cannot safely select one. Returns
    ``smaller_question``, ``carry_to_refine``, or ``unclear``."""
    if state is None or state.stage != "recovery_choice_pending":
        return "unclear"
    text = _normalize_choice_speech(team_utterance)
    if not text or re.match(r"^(sim|nao|pode|vamos|yes|no|yeah|okay|ok|sure)$", text):
        return "unclear"
    decision = resolve_oral_choice(team_utterance, _RECOVERY_CHOICES)
    if decision.ambiguous or decision.choice is None:
        return "unclear"
    if decision.choice == "smaller" and re.search(r"\brefine\b", text):
        return "unclear"
    return "smaller_question" if decision.choice == "smaller" else "carry_to_refine"
