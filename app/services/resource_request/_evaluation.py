"""Reading an evaluation whole, because nothing useful reads a piece of it.

The evaluation row, its six score rows and its ata are one aggregate stored in three
tables — the ``_loading.py`` reasoning one aggregate over. Every caller that serves an
evaluation serves all three, so the load is written once, together with the snapshot
lookup both the readers and the writer start from.

Scores come back in the criterion order of the request's own type, read from the vendored
emission — the order the mesa sees them in Parte C — with a key the current list does not
carry sorting last rather than raising: a retired key on an old evaluation is history to
display, not an error to refuse (the versioning rule in ``docs/resource_requests.md``
§4.5). Attendees come back sorted, so two reads of one evaluation are the same bytes.
"""

from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import (
    RREvaluation,
    RREvaluationAttendee,
    RREvaluationScore,
    RRSnapshot,
)
from app.utils.resource_request_vocabularies import CRITERION_KEYS


class EvaluationRecord(NamedTuple):
    evaluation: RREvaluation
    scores: list[RREvaluationScore]
    attendees: list[str]


async def latest_snapshot(db: AsyncSession, request_id: str) -> RRSnapshot | None:
    """The snapshot an evaluation hangs from — the most recent freeze of this request."""
    return (
        await db.execute(
            select(RRSnapshot)
            .where(RRSnapshot.request_id == request_id)
            .order_by(RRSnapshot.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def load_evaluation(
    db: AsyncSession, snapshot_id: str, request_type: str
) -> EvaluationRecord | None:
    """The whole aggregate for one snapshot, or ``None`` when the mesa has not started."""
    evaluation = (
        await db.execute(select(RREvaluation).where(RREvaluation.snapshot_id == snapshot_id))
    ).scalar_one_or_none()
    if evaluation is None:
        return None

    scores = list(
        (
            await db.execute(
                select(RREvaluationScore).where(RREvaluationScore.evaluation_id == evaluation.id)
            )
        )
        .scalars()
        .all()
    )
    canonical = {key: index for index, key in enumerate(CRITERION_KEYS[request_type])}
    scores.sort(
        key=lambda row: (canonical.get(row.criterion_key, len(canonical)), row.criterion_key)
    )

    attendees = sorted(
        (
            await db.execute(
                select(RREvaluationAttendee.user_id).where(
                    RREvaluationAttendee.evaluation_id == evaluation.id
                )
            )
        )
        .scalars()
        .all()
    )

    return EvaluationRecord(evaluation=evaluation, scores=scores, attendees=attendees)
