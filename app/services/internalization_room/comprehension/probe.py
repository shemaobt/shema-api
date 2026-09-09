"""The one probe the app still raises: its own recording-handoff consent question.

A probe used to be an authorization — checkpoint scope, evidence method, practice scope,
and a purpose that told the Guide what it was allowed to say next. None of that exists
any more. What is left is a marker that the app has voiced its fixed yes/no question and
owes the next answer to its own parser, so an ordinary passage answer cannot be read as
consent and consent cannot be read as anything else.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, model_validator

from app.core.exceptions import ValidationError


class ProbePurpose(enum.StrEnum):
    RECORDING_HANDOFF_CONSENT = "recording_handoff_consent"


class ActiveProbe(BaseModel):
    id: str
    purpose: ProbePurpose

    @model_validator(mode="after")
    def _enforce_authorization_invariants(self) -> ActiveProbe:
        if not self.id.strip():
            raise ValidationError("Probe id must not be empty")
        return self


def process_choice_freezes_bridge_mode(probe: ActiveProbe | None) -> bool:
    """A process answer belongs to exactly one app-owned parser — "sim" after the consent
    question must not also switch the bridge-language method."""
    return probe is not None


def select_probe_after_oral_turn(
    *,
    outcome: str,
    prior_probe: ActiveProbe | None,
    next_probe: ActiveProbe | None,
    transcript_uncertain: bool,
    transcript_was_mother_tongue: bool,
    transcript_empty: bool,
) -> ActiveProbe | None:
    """Never bind an answer to an unvoiced question.

    A transport fail-safe did not voice the newly planned question: the prior probe is
    preserved only when the fixed line asks for the same bridge answer again (mother
    tongue heard, nothing heard, or nothing the room could make out), otherwise it is
    cleared.
    """
    if outcome != "fail_safe":
        return next_probe
    if transcript_uncertain or transcript_was_mother_tongue or transcript_empty:
        return prior_probe
    return None
