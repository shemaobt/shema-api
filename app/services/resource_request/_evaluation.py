"""Reading an evaluation: whole for the mesa, two columns for the team.

The evaluation row, its six score rows and its ata are one aggregate stored in three
tables — the ``_loading.py`` reasoning one aggregate over. Every caller that *serves an
evaluation* serves all three, so the load is written once, together with the snapshot
lookup both the readers and the writer start from.

``team_outcome`` is the one caller that does not, and it is here rather than beside its
service so that the columns a team may read stay next to the ones it may not.

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
    RRDecision,
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


class TeamOutcome(NamedTuple):
    decision: RRDecision | None
    team_note: str | None


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


async def team_outcome(db: AsyncSession, request_id: str) -> TeamOutcome:
    """The two fields of the evaluation a team may read — two columns, one statement.

    ``request_status`` is the route a team refreshes on its own request, and it consumes
    exactly these two. Reaching them through ``latest_snapshot`` and ``load_evaluation``
    cost four statements, and the first of the four selected the snapshot row whole to use
    its ``id`` — dragging the frozen ``document``, the entire submitted request, across the
    wire to be discarded.

    The outer join keeps the semantics ``latest_snapshot`` gives, and that is the reason it
    is an outer one: the answer belongs to the **latest** snapshot, so a newer snapshot
    nobody has evaluated answers *no decision yet* rather than falling back to what the
    mesa decided about the previous one. No snapshot at all answers the same pair, because
    to a team *not submitted* and *not decided* are the same sentence — the stage is what
    tells them apart, and ``request_status`` reads that from the spine.
    """
    row = (
        await db.execute(
            select(RREvaluation.decision, RREvaluation.team_note)
            .select_from(RRSnapshot)
            .outerjoin(RREvaluation, RREvaluation.snapshot_id == RRSnapshot.id)
            .where(RRSnapshot.request_id == request_id)
            .order_by(RRSnapshot.created_at.desc())
            .limit(1)
        )
    ).first()
    return TeamOutcome(None, None) if row is None else TeamOutcome(row.decision, row.team_note)
