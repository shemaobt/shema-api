# ruff: noqa: E501 — ported oral-decision patterns are verbatim reference data;
"""App-owned probe authorization.

A probe is created before the Voice asks its question, persisted with that question, and
is the only authority for checkpoint scope, evidence method, conflict resolution, and
practice scope when the team's next answer arrives. Process purposes authorize zero
semantic evidence; guided purposes authorize exactly one checkpoint; only the free
retelling may gather evidence for several checkpoints from one natural telling.

Ported from the reference prototype's ``src/comprehension/probe.ts``.
"""

from __future__ import annotations

import enum
import re

from pydantic import BaseModel, model_validator

from app.core.exceptions import ValidationError
from app.services.internalization_room.comprehension.evidence import EvidenceMethod
from app.services.internalization_room.oral_decision import (
    OralChoicePattern,
    normalize_oral_decision,
    resolve_oral_choice,
)


class ProbePurpose(enum.StrEnum):
    MOTHER_TONGUE_PRACTICE = "mother_tongue_practice"
    SCENE_OPENING = "scene_opening"
    CARRY_TO_REFINE_CHOICE = "carry_to_refine_choice"
    RECORDING_HANDOFF_CONSENT = "recording_handoff_consent"
    FREE_RETELL = "free_retell"
    INITIAL_CHECK = "initial_check"
    TRIANGULATE = "triangulate"
    CLARIFY_CONFLICT = "clarify_conflict"


PROCESS_ONLY_PURPOSES = frozenset(
    {
        ProbePurpose.MOTHER_TONGUE_PRACTICE,
        ProbePurpose.SCENE_OPENING,
        ProbePurpose.CARRY_TO_REFINE_CHOICE,
        ProbePurpose.RECORDING_HANDOFF_CONSENT,
    }
)

#: The two app-owned purposes whose turn ends on the rehearsal invitation. A scene the
#: Guide opens is rehearsed on the same contract as one the room returns to, so the same
#: answers close it: the telling brought back, the closing word, or confident
#: mother-tongue audio. One set, read by the turn, the practice reader and the contract.
PROBES_THAT_INVITE_A_REHEARSAL = frozenset(
    {ProbePurpose.MOTHER_TONGUE_PRACTICE, ProbePurpose.SCENE_OPENING}
)


class ActiveProbe(BaseModel):
    id: str
    checkpoint_ids: list[str]
    method: EvidenceMethod
    purpose: ProbePurpose
    practice_scene_ids: list[str] = []

    @model_validator(mode="after")
    def _enforce_authorization_invariants(self) -> ActiveProbe:
        if not self.id.strip():
            raise ValidationError("Probe id must not be empty")
        for values, label in (
            (self.checkpoint_ids, "checkpoint"),
            (self.practice_scene_ids, "scene"),
        ):
            if any(not value.strip() for value in values):
                raise ValidationError(f"Probe {label} ids must not be empty")
            if len(set(values)) != len(values):
                raise ValidationError(f"Duplicate probe {label} id")
        purpose = self.purpose
        if purpose in (ProbePurpose.MOTHER_TONGUE_PRACTICE, ProbePurpose.SCENE_OPENING):
            if self.checkpoint_ids:
                raise ValidationError(f"A {purpose.value} probe cannot authorize semantic evidence")
            if not self.practice_scene_ids:
                raise ValidationError(f"A {purpose.value} probe needs an explicit scene scope")
        elif purpose is ProbePurpose.RECORDING_HANDOFF_CONSENT:
            if self.checkpoint_ids or self.practice_scene_ids:
                raise ValidationError(
                    "A recording-handoff consent probe cannot authorize passage evidence or practice"
                )
        elif purpose is ProbePurpose.CARRY_TO_REFINE_CHOICE:
            if self.practice_scene_ids:
                raise ValidationError(
                    "A carry-to-Refine choice cannot authorize mother-tongue practice"
                )
            if not self.checkpoint_ids:
                raise ValidationError("A carry-to-Refine choice needs one checkpoint")
        elif not self.checkpoint_ids:
            raise ValidationError("A comprehension probe needs a checkpoint")

        if (
            purpose
            not in (
                ProbePurpose.MOTHER_TONGUE_PRACTICE,
                ProbePurpose.SCENE_OPENING,
                ProbePurpose.RECORDING_HANDOFF_CONSENT,
                ProbePurpose.FREE_RETELL,
            )
            and len(self.checkpoint_ids) != 1
        ):
            raise ValidationError(f"{purpose.value} probes must authorize exactly one checkpoint")
        if (
            purpose is ProbePurpose.FREE_RETELL
            and self.method is not EvidenceMethod.FREE_BRIDGE_RETELL
        ):
            raise ValidationError("A free-retell probe must use free_bridge_retell")
        if (
            purpose is ProbePurpose.CLARIFY_CONFLICT
            and self.method is EvidenceMethod.FREE_BRIDGE_RETELL
        ):
            raise ValidationError("Conflict clarification must use a focused probe method")
        return self


def is_process_only(probe: ActiveProbe) -> bool:
    return probe.purpose in PROCESS_ONLY_PURPOSES


def process_choice_freezes_bridge_mode(
    probe: ActiveProbe | None, recovery_choice_pending: bool
) -> bool:
    """A process answer belongs to exactly one app-owned parser — "sim" after an STT or
    Refine choice must not also switch the bridge-language method."""
    if recovery_choice_pending:
        return True
    return probe is not None and probe.purpose in PROCESS_ONLY_PURPOSES


def select_probe_after_oral_turn(
    *,
    outcome: str,
    prior_probe: ActiveProbe | None,
    next_probe: ActiveProbe | None,
    target_practice_completed: bool,
    transcript_uncertain: bool,
    transcript_was_mother_tongue: bool,
    transcript_empty: bool,
    preserve_semantic_probe_for_retry: bool,
) -> ActiveProbe | None:
    """Never bind evidence to an unvoiced prompt.

    A transport fail-safe did not voice the newly planned question: the prior probe is
    preserved only when the fixed line asks for the same bridge answer again (mother
    tongue heard, or nothing heard), otherwise it is cleared.
    """
    if outcome != "fail_safe":
        return next_probe
    if target_practice_completed:
        return None
    if transcript_uncertain:
        if prior_probe is not None and is_process_only(prior_probe):
            return prior_probe
        return prior_probe if preserve_semantic_probe_for_retry else None
    if transcript_was_mother_tongue or transcript_empty:
        return prior_probe
    return None


_CARRY_CHOICES = (
    OralChoicePattern(
        value="carry",
        patterns=(
            re.compile(r"\b(?:lev\w*|guard\w*|deix\w*)\b.{0,80}\brefine\b"),
            re.compile(r"\brefine\b.{0,60}\b(?:lev\w*|guard\w*|deix\w*)\b"),
            re.compile(r"\b(?:carry|keep|leave|take)\b.{0,80}\brefine\b"),
            re.compile(r"\brefine\b.{0,60}\b(?:carry|keep|leave|take)\b"),
        ),
    ),
    OralChoicePattern(
        value="retry",
        patterns=(
            re.compile(
                r"\b(?:tentar|perguntar|explicar)\b.{0,48}"
                r"\b(?:de novo|outra vez|outra pergunta|pergunta menor|pergunta curta|menor|curt\w*|diferente)\b"
            ),
            re.compile(r"\b(?:outra|uma)\s+perguntas?\s+(?:menor|curt\w*|diferente)\b"),
            re.compile(
                r"\b(?:try|ask|explain)\b.{0,48}\b(?:again|another question|smaller|shorter|different)\b"
            ),
            re.compile(r"\b(?:another|a)\s+(?:smaller|shorter|different)\s+questions?\b"),
        ),
    ),
)

_NEGATIVE_THEN_EXPLICIT_RETRY = re.compile(
    r"^\s*(?:n[aã]o|no|not\s+yet)\s*,\s*(?:(?:eu|n[oó]s|a\s+gente|i|we)\s+)?"
    r"(?:quero|queremos|vamos|prefiro|preferimos|want|prefer|let'?s)?\b[^.;!?]{0,48}"
    r"\b(?:tentar|perguntar|explicar|try|ask|explain)\b",
    re.IGNORECASE,
)


def resolve_carry_to_refine_decision(
    probe: ActiveProbe | None, previous_guide_utterance: str, team_utterance: str
) -> str:
    """A bare yes/no is a process decision only when it answers the exact app-owned carry
    question. It can never become semantic support.

    Requiring the prior voiced question to name Refine keeps a stale probe or an ordinary
    passage answer from manufacturing a deferral. Returns ``carry``, ``try_again``, or
    ``unclear``.
    """
    if probe is None or probe.purpose is not ProbePurpose.CARRY_TO_REFINE_CHOICE:
        return "unclear"
    if len(probe.checkpoint_ids) != 1:
        return "unclear"
    guide = normalize_oral_decision(previous_guide_utterance)
    team = normalize_oral_decision(team_utterance)
    bound_question = bool(
        re.search(r"\brefine\b", guide)
        and re.search(
            r"\b(ponto|duvida|incerteza|abert\w*|levar|guardar|point|doubt|uncertaint\w*|open|carry|keep)\b",
            guide,
        )
    )
    if not bound_question or not team:
        return "unclear"

    decision = resolve_oral_choice(team_utterance, _CARRY_CHOICES)
    if decision.ambiguous:
        return "unclear"
    if decision.choice == "carry":
        return "carry"
    if decision.choice == "retry":
        return "try_again"
    if _NEGATIVE_THEN_EXPLICIT_RETRY.match(team_utterance):
        return "try_again"
    if "carry" in decision.rejected or re.match(r"^(nao|ainda nao|no|not yet)$", team):
        return "try_again"
    bare_affirmative = bool(
        re.match(r"^(sim|claro|isso|isso mesmo|pode|vamos|yes|yeah|sure|okay|ok)$", team)
    )
    yes_means_carry = bool(
        re.search(
            r"\b(?:sim\s+significa|dizer\s+sim\s+significa|se\s+(?:disserem|responderem)\s+sim"
            r"|respondam\s+sim\s+para)\b.{0,100}\b(?:lev\w*|guard\w*|deix\w*)\b",
            guide,
        )
        or re.search(
            r"\b(?:yes\s+means|saying\s+yes\s+means|if\s+you\s+say\s+yes|answer\s+yes\s+to)\b"
            r".{0,100}\b(?:carry|keep|leave|take)\b",
            guide,
        )
    )
    if bare_affirmative and yes_means_carry:
        return "carry"
    return "unclear"
