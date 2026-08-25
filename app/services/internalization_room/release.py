"""The handoff artifact a finished internalization session sends to OBT Refine.

The artifact carries not just the audio, but the history of how the team reached it and
which limits still need people who understand the mother tongue: the bridge mode, the
scenes practiced, the semantic evidence events and their open points, the telling-back
with its findings and playback report, and every superseded attempt clearly marked.

The release fails closed. A blocker means the session is not ready to travel — never a
partial artifact — because a package missing its calibration, consent, evidence, or
telling-back would look downstream exactly like a finished one. The output is always
labeled ``first_team_rehearsal`` / ``ready_for_refine``: the system never claims to have
understood or approved the mother-tongue recording itself.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.internalization_room import IRQuestion, IRSession, IRTake, IRTakeKind
from app.services.internalization_room.back_translation import played_ranges_cover_clip
from app.services.internalization_room.calibration import BridgeMode
from app.services.internalization_room.canon.book_material import vendor_pin
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.session_readiness import (
    evaluate_session_comprehension,
)
from app.services.internalization_room.coverage import floor_met
from app.services.internalization_room.sessions import (
    back_translation_of,
    comprehension_of,
    is_panorama,
)
from app.services.internalization_room.takes import takes_of

SCHEMA_VERSION = "tripod.internalization-release.v0.1"


class InternalizationReleaseBlocked(ConflictError):
    def __init__(self, blockers: list[str]) -> None:
        self.blockers = blockers
        super().__init__("internalization release blocked: " + ", ".join(blockers))


def _package_sha256(artifact: dict[str, Any]) -> str:
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _take_view(take: IRTake) -> dict[str, Any]:
    return {
        "take_id": take.id,
        "kind": take.kind.value,
        "scope": take.scope,
        "pass_number": take.pass_number,
        "chunk_index": take.chunk_index,
        "sha256": take.sha256,
        "size_bytes": take.size_bytes,
        "content_type": take.content_type,
        "verified": take.verified_at is not None,
        "recorded_at": take.created_at.isoformat() if take.created_at else None,
    }


async def build_internalization_release(db: AsyncSession, session: IRSession) -> dict[str, Any]:
    """Build the closed-world release for one session, or refuse with typed blockers.

    A telling-back has to exist; it does not have to have come out clean. ``checked`` is
    written as ``finding is None and evidence_sufficient``, so any question the team chose
    not to resolve made it false — and blocking on it denied the one outcome the room is
    meant to be able to reach, taking the questions to Refine. The rehearsal, the coverage,
    the ledger and the telling-back stayed on the tablet with no way out, for a team that
    had done every piece of the work.

    What the package says instead of refusing: ``checked`` false, ``evidence_sufficient``
    as the analyst left it, and every open finding in ``findings``. Judging the quality of
    a telling-back is not this artifact's job — carrying it honestly is.

    That honesty is why an unread telling-back is still refused. A team that captured the
    stretches and never asked for the verdict leaves no findings and ``evidence_sufficient``
    at its default, which is the same package a clean check produces — and no report of
    playback either, since none is read as a legacy client and passes. Carrying the
    questions is the point; carrying silence as if it were clean is not.
    """
    blockers: list[str] = []
    if is_panorama(session.pericope):
        raise InternalizationReleaseBlocked(["panorama_sessions_never_release"])

    comprehension = comprehension_of(session)
    telling_back = back_translation_of(session)
    checkpoints = list(checkpoints_for(session.pericope))
    scene_ids = scene_ids_for(session.pericope)
    readiness = evaluate_session_comprehension(
        checkpoints=checkpoints,
        scene_ids=scene_ids,
        ledger=comprehension.ledger,
        practiced_scene_ids=comprehension.practiced_scene_ids,
    )
    takes = await takes_of(db, session.id)
    ensaio_takes = [take for take in takes if take.kind is IRTakeKind.ENSAIO]
    retro_takes = [take for take in takes if take.kind is IRTakeKind.RETRO]

    if session.bridge_mode == BridgeMode.CALIBRATION_PENDING.value:
        blockers.append("bridge_language_never_calibrated")
    if readiness.evaluation.outcome.value == "needs_more_work":
        blockers.append("comprehension_needs_more_work")
    if not comprehension.recording_consent_given:
        blockers.append("recording_consent_never_given")
    if not floor_met(session.coverage_state or {}, session.pericope):
        blockers.append("coverage_floor_not_met")
    if not ensaio_takes:
        blockers.append("no_rehearsal_audio")
    if not telling_back.chunks:
        blockers.append("no_telling_back")
    elif telling_back.never_analysed:
        blockers.append("telling_back_never_analysed")
    if not played_ranges_cover_clip(telling_back.played_ranges, telling_back.clip_duration_ms):
        blockers.append("playback_did_not_cover_the_clip")
    if blockers:
        raise InternalizationReleaseBlocked(blockers)

    by_id = {checkpoint.id: checkpoint for checkpoint in checkpoints}
    open_points = []
    for point in readiness.evaluation.open_points:
        checkpoint = by_id.get(point.unit_id)
        open_points.append(
            {
                "unit_id": point.unit_id,
                "reason": point.reason,
                "checkpoint_kind": checkpoint.kind if checkpoint else None,
                "scene_id": checkpoint.scene_id if checkpoint else None,
                "source_id": checkpoint.source_id if checkpoint else None,
                "canonical": checkpoint.canonical if checkpoint else None,
            }
        )

    questions = (
        (
            await db.execute(
                select(IRQuestion)
                .where(IRQuestion.session_id == session.id)
                .order_by(IRQuestion.created_at)
            )
        )
        .scalars()
        .all()
    )

    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "handoff_type": "internalization_release",
        "purpose": "first_team_rehearsal",
        "readiness": "ready_for_refine",
        "created_at": datetime.now(UTC).isoformat(),
        "session_id": session.id,
        "pericope": session.pericope,
        "book": load_map(session.pericope).book,
        "canon_vendor_pin": vendor_pin(),
        "bridge_mode": session.bridge_mode,
        "comprehension": {
            "outcome": readiness.evaluation.outcome.value,
            "supported_unit_ids": readiness.evaluation.supported_unit_ids,
            "total_units": len(checkpoints),
            "practiced_scene_ids": comprehension.practiced_scene_ids,
            "events": [event.model_dump(mode="json") for event in comprehension.ledger],
            "open_points": open_points,
        },
        "audio": {
            "recording_grain": "whole",
            "rehearsal_takes": [_take_view(take) for take in ensaio_takes],
        },
        "back_translation": {
            "scope": telling_back.scope,
            "checked": telling_back.checked,
            "evidence_sufficient": telling_back.evidence_sufficient,
            "retells": telling_back.retells,
            "chunks": [chunk.model_dump(mode="json") for chunk in telling_back.chunks],
            "findings": [finding.model_dump(mode="json") for finding in telling_back.findings],
            "played_ranges": telling_back.played_ranges,
            "clip_duration_ms": telling_back.clip_duration_ms,
            "superseded_attempts": [
                attempt.model_dump(mode="json") for attempt in telling_back.superseded
            ],
            "retro_takes": [_take_view(take) for take in retro_takes],
        },
        "raised_questions": [
            {
                "question_id": question.id,
                "status": question.status.value,
                "asked_at": question.created_at.isoformat() if question.created_at else None,
            }
            for question in questions
        ],
        "open_questions": len(open_points)
        + sum(1 for question in questions if question.status.value != "resolved"),
    }
    artifact["package_sha256"] = _package_sha256(artifact)
    return artifact
