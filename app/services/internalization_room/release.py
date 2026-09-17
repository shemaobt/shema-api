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
from app.db.models.internalization_room import (
    IRQuestion,
    IRSegment,
    IRSession,
    IRTake,
    IRTakeKind,
)
from app.services.internalization_room.back_translation import playback_confirms_rehearsal
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
from app.services.internalization_room.coverage import engaged_scene_ids, floor_met
from app.services.internalization_room.segments import (
    divided_segments,
    final_segments,
    retired_segments,
    told_back,
)
from app.services.internalization_room.sessions import (
    back_translation_of,
    comprehension_of,
    is_panorama,
)
from app.services.internalization_room.takes import takes_of

#: Bumped from v0.1 with the telling-back's ``chunks`` array: a stretch is addressed rather
#: than counted now, so the entries carry an id and the recording they are a slice of, and the
#: key says ``segments`` because that is what they are.
SCHEMA_VERSION = "tripod.internalization-release.v0.2"


class InternalizationReleaseBlocked(ConflictError):
    def __init__(self, blockers: list[str]) -> None:
        self.blockers = blockers
        super().__init__("internalization release blocked: " + ", ".join(blockers))


def _package_sha256(artifact: dict[str, Any]) -> str:
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _segment_view(segment: IRSegment) -> dict[str, Any]:
    """One stretch, with the address a reviewer needs to go and hear it.

    ``take_id`` with ``starts_ms``/``ends_ms`` is the slice **inside that file**, never a
    position over the concatenated passage — which is what lets a stretch be told back again
    without touching the ones after it.

    Re-recording the mother tongue is the one correction that does move them, because it
    rebuilds the file they are all slices of: they are re-pointed at the rebuilt passage
    together, in one place, and a reader of this packet resolves every stretch against the
    recording named here and needs to do nothing else.
    """
    return {
        "segment_id": segment.id,
        "take_id": segment.take_id,
        "starts_ms": segment.starts_ms,
        "ends_ms": segment.ends_ms,
        "pass_number": segment.pass_number,
        "parent_segment_id": segment.parent_id,
        "text": segment.transcript,
    }


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

    ``superseded_segments`` carries the stretches that stopped counting, replaced or
    abandoned, each still naming the recording it was a slice of. They used to be copied into
    ``superseded_attempts`` as text; they are rows now, and dropping them here would quietly
    take the team's own history out of the handoff.

    ``divided_segments`` carries the same debt for the other way a stretch leaves the reading.
    A stretch the team divided is current and is not a leaf, so it fell between both lists
    above — and what they had said about the whole stretch, before they heard two ideas in it,
    left the artifact in silence. Hearing it again and finding two ideas is the team working,
    not the team erring, so what they said the first time is kept rather than the division
    being refused.

    What the package says instead of refusing: ``checked`` false, ``evidence_sufficient``
    as the analyst left it, and every open finding in ``findings``. Judging the quality of
    a telling-back is not this artifact's job — carrying it honestly is.

    That honesty is why an unread telling-back is still refused. A team that captured the
    stretches and never asked for the verdict leaves no findings and ``evidence_sufficient``
    at its default, which is the same package a clean check produces. Carrying the
    questions is the point; carrying silence as if it were clean is not.

    The report of playback is held to the same line, and it is why the gate names a rehearsal
    rather than only measuring one. Silence used to pass it — an absent report satisfied the
    coverage arithmetic the way an unread telling-back satisfied ``checked`` — and so did a
    report the team had since made untrue by recording the passage again. Both said the team
    heard themselves when nobody knows whether they did. The package is refused unless the
    report names the recording this package ships and reaches the end of it.

    What the report has to name is asked of the stretches, which say which recording each is a
    slice of and were checked on the way in. Not of the takes table: ``created_at`` there is
    when the upload landed, the tablet's outbox drains whenever the link comes back, and the
    newest-arriving rehearsal is sometimes the one the team abandoned.

    Sessions already in flight when this shipped carry a report with no such name, and are
    refused until the team plays their rehearsal through again. That is the correct reading of
    them: a report we cannot tie to a recording is not evidence about any recording.

    A session with nothing told back is not asked. ``no_telling_back`` already says what is
    wrong there, and a second blocker about playback would only repeat it in other words.

    ``untold_stretch`` is the same argument about words instead of audio. A stretch whose mother
    tongue was just re-recorded, and each half of one the team divided, is a current unit carrying
    nothing they said — legitimate inside the room, where the tablet shows it and asks for it, and
    unreadable outside: null text does not arrive downstream as unfinished, it arrives as a team
    who stood in front of that passage and said nothing.

    Unlike the line above, it silences nothing. A re-record that was never told back and never
    played leaves the team two errands, and naming one of them would send them back a second time.

    It is its own blocker rather than a widening of the two beside it, and neither could have
    been widened honestly. ``no_telling_back`` asks whether the list is empty, and a list with a
    wordless stretch in it is not empty; ``telling_back_never_analysed`` asks whether the analyst
    ever ran, which stays true from the first verdict onwards — including after the team divides
    a stretch the analyst blessed. Both are green in exactly the state this refuses. Overloading
    either would also send the facilitator the wrong errand: told that nothing was told back
    when plainly something was, they go looking for the wrong thing. The name is the room's own
    word for the state, the one ``FailSafe.UNTOLD_STRETCH`` already speaks aloud on the tablet.

    Once rather than once per stretch: a blocker is an errand, and the errand is the same one.

    The guarantee is about ``segments`` and stops there. ``superseded_segments`` and
    ``divided_segments`` are history and carry null text on purpose — a stretch the team replaced
    before telling it back is exactly a stretch they replaced before telling it back, and refusing
    a release over what a session used to look like would hold the team to a state they already
    left. A reader of those two lists is reading a record, not a claim about the passage.

    Wordless is ``transcript is None`` and nothing subtler, because that is the only shape the
    room can write — both routes that store a stretch's words refuse a transcription that is
    blank or whitespace before they get here. The rule is read off ``told_back`` rather than
    restated, so what counts as words stays one sentence in one place: the analyst is numbered
    off that same list, and the two must not drift.
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
        engaged_scene_ids=engaged_scene_ids(session.coverage_state or {}, session.pericope),
    )
    stretches = await final_segments(db, session.id)
    told = told_back(stretches)
    replaced = await retired_segments(db, session.id)
    divided = await divided_segments(db, session.id)
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
    if not stretches:
        blockers.append("no_telling_back")
    elif telling_back.never_analysed:
        blockers.append("telling_back_never_analysed")
    if told != stretches:
        blockers.append("untold_stretch")
    rehearsed = sorted({segment.take_id for segment in stretches})
    if rehearsed and not playback_confirms_rehearsal(telling_back, rehearsed):
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
            "segments": [_segment_view(segment) for segment in told],
            "findings": [finding.model_dump(mode="json") for finding in telling_back.findings],
            "played_ranges": telling_back.played_ranges,
            "clip_duration_ms": telling_back.clip_duration_ms,
            "superseded_attempts": [
                attempt.model_dump(mode="json") for attempt in telling_back.superseded
            ],
            "superseded_segments": [_segment_view(segment) for segment in replaced],
            "divided_segments": [_segment_view(segment) for segment in divided],
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
