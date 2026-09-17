"""Bounded process handling for a reliable but semantically empty bridge-language answer.

"Não sei" is not misunderstanding and is not STT failure. The first occurrence rotates
the app-owned operation; a second independent occurrence — a different method, same
checkpoint — opens an honest bridge/reporting limit (``unclear_due_bridge``), which
records a reporting limit, never a lack of understanding.
"""

from __future__ import annotations

from app.services.internalization_room.comprehension.assessor import is_semantically_empty_answer
from app.services.internalization_room.comprehension.evidence import (
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.probe import ActiveProbe, is_process_only
from app.services.internalization_room.comprehension.probe_plan import NoUsableReportAttempt


def resolve_no_usable_report(
    *,
    probe: ActiveProbe | None,
    prior_attempts: list[NoUsableReportAttempt],
    transcript: str,
    reliable_bridge_speech: bool,
    assessor_found_no_evidence: bool,
    observation_id: str,
) -> tuple[list[NoUsableReportAttempt], EvidenceObservation | None]:
    if (
        probe is None
        or is_process_only(probe)
        or not reliable_bridge_speech
        or not transcript.strip()
        or not (is_semantically_empty_answer(transcript) or assessor_found_no_evidence)
    ):
        return [], None

    attempt = NoUsableReportAttempt(
        probe_id=probe.id,
        checkpoint_ids=list(probe.checkpoint_ids),
        method=probe.method,
    )
    if len(probe.checkpoint_ids) != 1:
        return [attempt], None

    unit_id = probe.checkpoint_ids[0]
    prior_methods = {item.method for item in prior_attempts if unit_id in item.checkpoint_ids}
    if not prior_methods or probe.method in prior_methods:
        return [attempt], None
    observation = EvidenceObservation(
        id=observation_id,
        unit_id=unit_id,
        probe_id=probe.id,
        method=probe.method,
        result=EvidenceResult.UNCLEAR_DUE_BRIDGE,
        note=(
            "Two different app-owned operations received no usable bridge-language "
            "semantic report; this records a reporting limit, not lack of understanding."
        ),
    )
    return [attempt], observation
