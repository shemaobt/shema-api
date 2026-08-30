from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnknownReferenceError, ValidationError
from app.db.models.auth import User
from app.db.models.resource_request import (
    RREvaluation,
    RREvaluationAttendee,
    RREvaluationScore,
)
from app.models.resource_request import EvaluationWriteIn
from app.services.resource_request._decision_stage import DECISION_STAGE
from app.services.resource_request._evaluation import (
    EvaluationRecord,
    latest_snapshot,
    load_evaluation,
)
from app.services.resource_request._transition import guard_stage_entry, transition_stage
from app.services.resource_request.get_request import get_request


async def save_evaluation(
    db: AsyncSession, request_id: str, payload: EvaluationWriteIn, user: User, app_key: str
) -> EvaluationRecord:
    """Write the mesa's evaluation — and, when it carries the decision, everything D6 chains
    to it, in one transaction.

    **One evaluation per snapshot** (GATE-02 D5): the write is an upsert against the latest
    snapshot's row, which ``uq_rr_evaluations_snapshot`` backs in the schema. There is
    nothing to evaluate before submission — an evaluation scores a frozen document, never a
    draft still moving.

    **Evaluator and instant come from the session, never the payload.** Every save stamps
    ``evaluator_id`` from the bearer token — whoever last signed, on behalf of the mesa —
    and recording the decision stamps ``evaluated_at`` from the server clock. The payload
    cannot carry either: ``extra="forbid"`` refuses the attempt as a 422.

    **The write order of a decision is the contract BE-08 follows** (documented in
    ``docs/resource_requests.md`` §4.5): (1) the decision on the evaluation row, (2) the
    ledger movement when the decision is ``approved`` — ``append_movement`` takes the fund
    row's lock and flushes, never commits — (3) the stage event naming that movement, (4)
    the request's stage, and one commit under all four. The ledger precedes the stage event
    because ``rr_board_transitions.movement_id`` names the movement, so the FK decides the
    order the issue's prose could not. Since BE-08 (OBT-457) steps 2-4 are
    ``transition_stage``, the same path a hand's drag takes — which is what keeps a
    decision landing on a card the mesa already dragged into its column from deducting
    twice or writing a second event: the transition is a no-op there, and only the
    decision itself is recorded. The transition carries ``evaluation_id``, so the trail
    tells a decision's move from a drag.

    **A recorded decision is not rewritten here.** Scores, comments, the ata and the
    ``team_note`` stay editable afterwards — D7 audits exactly those edits, through BE-15 —
    and a save carrying the same decision again re-fires nothing: the card moved when the
    decision was recorded, and it may legitimately have been dragged since (the implication
    runs one way). A save carrying a *different* decision is refused: undoing an
    ``approved`` is a compensating movement plus a board move, which is BE-08's transaction
    and must not be half-built here.

    **Approving with no fund fails, decidably** — GATE-01 D4's invariant (BE-11's rule,
    bitten on this write path): the mesa assigns the fund at triage, and a request does not
    enter ``aprovado`` with ``fund_id IS NULL``. Refused before anything is written.

    **The ata refuses a member with no account, decidably.** ``rr_evaluation_attendees``
    holds real FKs, so existence is checked here and answered as a 422 naming the ids
    rather than as an IntegrityError's 500. The check reads *existence* on ``users`` and no
    grant — the guards stay the only interface to access control (design §2.2); requiring
    the ``mesa`` role of an attendee is deliberately not done, because the ata states who
    was in the room, which is a fact and not a permission. Every check runs before any
    write, so a refusal leaves nothing half-saved.
    """
    loaded = await get_request(db, request_id, user, app_key)
    request = loaded.request

    snapshot = await latest_snapshot(db, request_id)
    if snapshot is None:
        raise ConflictError("This request has not been submitted, so there is nothing to evaluate.")

    if payload.request_type is not request.request_type:
        raise ValidationError(
            f"The evaluation says {payload.request_type.value} "
            f"and the request is {request.request_type.value}."
        )

    if payload.attendees:
        found = set(
            (await db.execute(select(User.id).where(User.id.in_(payload.attendees)))).scalars()
        )
        missing = sorted(set(payload.attendees) - found)
        if missing:
            raise UnknownReferenceError(
                f"Not recordable in the ata, no account: {', '.join(missing)}"
            )

    evaluation = (
        await db.execute(select(RREvaluation).where(RREvaluation.snapshot_id == snapshot.id))
    ).scalar_one_or_none()

    recorded = evaluation.decision if evaluation is not None else None
    if recorded is not None and payload.decision is not recorded:
        raise ConflictError(
            f"The decision is recorded as {recorded.value} and is not rewritten here: "
            "moving out of a decided column is the board's transaction, "
            "with its compensating movement."
        )
    deciding = payload.decision if recorded is None else None

    if deciding is not None:
        guard_stage_entry(request, DECISION_STAGE[deciding])

    if evaluation is None:
        evaluation = RREvaluation(snapshot_id=snapshot.id)
        db.add(evaluation)
    evaluation.evaluator_id = user.id
    evaluation.comments = payload.comments
    evaluation.team_note = payload.team_note
    await db.flush()

    await db.execute(
        delete(RREvaluationScore).where(RREvaluationScore.evaluation_id == evaluation.id)
    )
    for score in payload.scores:
        db.add(
            RREvaluationScore(
                evaluation_id=evaluation.id,
                criterion_key=score.criterion_key,
                score=score.score,
            )
        )

    await db.execute(
        delete(RREvaluationAttendee).where(RREvaluationAttendee.evaluation_id == evaluation.id)
    )
    for attendee in payload.attendees:
        db.add(RREvaluationAttendee(evaluation_id=evaluation.id, user_id=attendee))

    if deciding is not None:
        evaluation.decision = deciding
        evaluation.evaluated_at = datetime.now(UTC)

        await transition_stage(
            db,
            request=request,
            to_stage=DECISION_STAGE[deciding],
            moved_by=user.id,
            reason=f"Mesa decision: {deciding.value}",
            evaluation_id=evaluation.id,
        )

    await db.commit()

    record = await load_evaluation(db, snapshot.id, request.request_type.value)
    assert record is not None
    return record
