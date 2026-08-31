# ruff: noqa: RUF001 — ported oral-decision patterns are verbatim reference data;
"""The exact recording-consent handoff.

The generated Guide may prepare the team for the handoff, but only this exact, validated
cue advances the durable session action. Coverage completion alone is never consent or
readiness. Ported from the reference prototype's ``src/turn/rehearsalReadiness.ts``.
"""

from __future__ import annotations

import re
import unicodedata

from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.languages import FLOOR
from app.services.internalization_room.oral_decision import (
    oral_clause_is_non_committal,
    oral_utterance_is_interrogative,
)

_READINESS_CUE = {
    "pt": "Agora o aplicativo vai mostrar onde gravar o primeiro ensaio na língua de vocês.",
    "en": "The app will now show you where to record the first rehearsal in your own language.",
}
_CONSENT_QUESTION = {
    "pt": (
        "Vocês querem seguir agora para gravar o primeiro ensaio na língua de vocês? "
        "Digam sim ou não."
    ),
    "en": (
        "Would you like to go on now and record the first rehearsal in your own language? "
        "Say yes or no."
    ),
}
_CONSENT_DECLINED = {
    "pt": (
        "Tudo bem. Podemos continuar conversando e ensaiando. "
        "Vocês decidem quando estiverem prontos."
    ),
    "en": ("That is fine. We can keep talking and rehearsing. You decide when you are ready."),
}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()


def rehearsal_readiness_cue(language: str = FLOOR) -> str:
    return _READINESS_CUE.get(language, _READINESS_CUE[FLOOR])


def rehearsal_consent_question(language: str = FLOOR) -> str:
    return _CONSENT_QUESTION.get(language, _CONSENT_QUESTION[FLOOR])


def rehearsal_consent_declined_line(language: str = FLOOR) -> str:
    return _CONSENT_DECLINED.get(language, _CONSENT_DECLINED[FLOOR])


def is_exact_rehearsal_consent_question(text: str) -> bool:
    """Whether a line the room already said was the consent question, in any language.

    Any language's and not this session's, because the text being matched was written on an
    earlier turn: matching only the current language would make the room stop recognising a
    question it had itself just asked.
    """
    return _normalize(text) in {_normalize(said) for said in _CONSENT_QUESTION.values()}


def is_exact_rehearsal_readiness_cue(text: str) -> bool:
    return _normalize(text) in {_normalize(said) for said in _READINESS_CUE.values()}


def _normalize_decision(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    lowered = stripped.casefold().replace("’", "").replace("'", "")
    cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


_EXPLICIT_RECORD_REQUESTS = frozenset(
    {
        "agora estamos prontos para gravar",
        "agora estamos prontas para gravar",
        "estamos prontos para gravar",
        "estamos prontas para gravar",
        "queremos gravar agora",
        "podemos gravar agora",
        "vamos para a gravacao",
    }
)


RECORDING_HANDOFF_REOFFER_AFTER_TURNS = 3


def explicitly_requests_recording_handoff(team_utterance: str) -> bool:
    """Re-arm a previously declined handoff only from a narrow, explicit request to
    record now."""
    if oral_utterance_is_interrogative(team_utterance) or oral_clause_is_non_committal(
        team_utterance
    ):
        return False
    return _normalize_decision(team_utterance) in _EXPLICIT_RECORD_REQUESTS


def should_offer_recording_consent(
    *,
    eligible: bool,
    paused: bool,
    paused_turns: int,
    explicit_resume_requested: bool,
    prior_decision: str,
    reliable_bridge_speech: bool,
) -> bool:
    """A pause is the team deferring the handoff, never ending it.

    The app owns the question, so only the app can bring it back: the Guide is told not to
    raise recording again, which left the seven explicit phrases as a password nobody was
    ever given. After ``RECORDING_HANDOFF_REOFFER_AFTER_TURNS`` turns the room actually
    heard, it asks once more.
    """
    return (
        eligible
        and reliable_bridge_speech
        and prior_decision not in ("accepted", "declined")
        and (
            not paused
            or explicit_resume_requested
            or paused_turns >= RECORDING_HANDOFF_REOFFER_AFTER_TURNS
        )
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
