# ruff: noqa: RUF001 — the curly apostrophe is stripped from oral answers on purpose;
"""The exact recording-consent handoff.

The generated Guide may prepare the team for the handoff, but only this exact, validated
cue advances the durable session action. Coverage completion alone is never consent or
readiness. Ported from the reference prototype's ``src/turn/rehearsalReadiness.ts``.
"""

from __future__ import annotations

import re
import unicodedata

from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.oral_decision import (
    oral_clause_is_non_committal,
    oral_utterance_is_interrogative,
)

REHEARSAL_READINESS_CUE = (
    "Agora o aplicativo vai mostrar onde gravar o primeiro ensaio na língua de vocês."
)
REHEARSAL_CONSENT_QUESTION = (
    "Vocês querem seguir agora para gravar o primeiro ensaio na língua de vocês? Digam sim ou não."
)
REHEARSAL_CONSENT_DECLINED_LINE = (
    "Tudo bem. Podemos continuar conversando e ensaiando. Vocês decidem quando estiverem prontos."
)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()


def is_exact_rehearsal_consent_question(text: str) -> bool:
    return _normalize(text) == _normalize(REHEARSAL_CONSENT_QUESTION)


def is_exact_rehearsal_readiness_cue(text: str) -> bool:
    return _normalize(text) == _normalize(REHEARSAL_READINESS_CUE)


def _normalize_decision(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    lowered = stripped.casefold().replace("’", "").replace("'", "")
    cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


def resumes_recording_handoff(team_utterance: str, *, reliable_bridge_speech: bool) -> bool:
    """Whether this turn lifts a handoff the team put on hold.

    A refusal is a postponement, not a door that locks from outside: any ordinary turn the
    room could hear and read in the bridge language lifts it. Nothing narrower may be
    required, because the Guide's probe contract forbids it from asking the team to say
    any particular thing about recording — a key the team is never handed is not a key.

    Speech the room could not use is not the team asking to be asked again: a turn spent in
    the team's own language is ordinary rehearsal, and a take that came back empty is
    nothing anyone said.
    """
    return reliable_bridge_speech and bool(team_utterance.strip())


def should_offer_recording_consent(
    *,
    eligible: bool,
    paused: bool,
    resume_requested: bool,
    prior_decision: str,
    reliable_bridge_speech: bool,
    consent_already_given: bool,
) -> bool:
    """Whether this turn puts the recording question in front of the team.

    Consent already given closes the question for good: asking a team that just agreed to
    record whether it wants to record reads as the room not having heard the answer.
    """
    return (
        eligible
        and reliable_bridge_speech
        and not consent_already_given
        and prior_decision not in ("accepted", "declined")
        and (not paused or resume_requested)
    )


_ACCEPTED = frozenset(
    {
        "sim",
        "estamos prontos",
        "estamos prontas",
        "queremos",
        "pode seguir",
        "podem seguir",
        "vamos gravar",
    }
)
_DECLINED = frozenset(
    {
        "nao",
        "ainda nao",
        "nao estamos prontos",
        "nao estamos prontas",
        "queremos continuar",
        "vamos continuar",
    }
)


def resolve_rehearsal_consent(
    *,
    probe: ActiveProbe | None,
    previous_guide_utterance: str,
    team_utterance: str,
    reliable_bridge_speech: bool,
) -> str:
    """Consent is a narrow, adjacent, app-owned process decision. The Guide cannot
    manufacture it, and a yes/no after any other question is inert. Returns ``accepted``,
    ``declined``, or ``unclear``."""
    if (
        not reliable_bridge_speech
        or probe is None
        or probe.purpose is not ProbePurpose.RECORDING_HANDOFF_CONSENT
        or probe.checkpoint_ids
        or probe.practice_scene_ids
        or not is_exact_rehearsal_consent_question(previous_guide_utterance)
    ):
        return "unclear"
    if oral_utterance_is_interrogative(team_utterance) or oral_clause_is_non_committal(
        team_utterance
    ):
        return "unclear"
    answer = _normalize_decision(team_utterance)
    if answer in _ACCEPTED:
        return "accepted"
    if answer in _DECLINED:
        return "declined"
    return "unclear"
