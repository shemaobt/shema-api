"""The evaluation on the wire: the mesa's read and write, and the team's four-field status.

Mesa-only through the aliases BE-03 built, and through nothing else: ``CanViewEvaluation``
opens the read to mesa and Gestor, ``CanEditEvaluation`` opens the write to the mesa alone
— *"ele nem pontua nem decide, essa função é exclusiva da mesa"* (client, 28/aug/2026), the
cell GATE-02 confirmed rather than moved. There is deliberately no DELETE: an evaluation
that moved a card and wrote the ledger cannot be unwound by disappearing, and D7's *"sim,
sempre mantenha os históricos"* makes corrections edits — audited by BE-15 — never
removals.

The status route is the exception that proves the gate. It answers to ``edit_requests`` —
the capability all three roles hold — with the row scope the request routes already use, so
a team reads its own request's ``stage``, ``submitted_at``, ``decision`` and ``team_note``
and nothing else (GATE-03 D4). It lives in this file because it is the evaluation's
team-facing edge: the file that owns what the evaluation shows is the file that owns what
it hides.

``PUT`` and not ``PATCH``, because GATE-02 D5 made the resource singular — one evaluation
per snapshot — and every save carries the whole of it: the six scores of the type, the
comments, the ata, the note, and the decision when the mesa takes one.
"""

from fastapi import APIRouter

from app.api.resource_requests._deps import (
    APP_KEY,
    CanEditEvaluation,
    CanEditRequests,
    CanViewEvaluation,
    Db,
)
from app.models.resource_request import (
    EvaluationOut,
    EvaluationWriteIn,
    RequestStatusOut,
    ScoreOut,
)
from app.services import resource_request as service
from app.services.resource_request._evaluation import EvaluationRecord
from app.utils.resource_request_totals import sum_score

router = APIRouter(tags=["resource requests"])


def _out(record: EvaluationRecord) -> EvaluationOut:
    evaluation, scores, attendees = record
    return EvaluationOut(
        id=evaluation.id,
        snapshot_id=evaluation.snapshot_id,
        evaluator_id=evaluation.evaluator_id,
        decision=evaluation.decision,
        comments=evaluation.comments,
        team_note=evaluation.team_note,
        scores=[ScoreOut(criterion_key=row.criterion_key, score=row.score) for row in scores],
        total=sum_score(row.score for row in scores),
        attendees=attendees,
        evaluated_at=evaluation.evaluated_at,
        created_at=evaluation.created_at,
        updated_at=evaluation.updated_at,
    )


@router.get("/requests/{request_id}/evaluation")
async def read_evaluation(request_id: str, user: CanViewEvaluation, db: Db) -> EvaluationOut:
    """The whole aggregate, with the /30 derived on this read and stored nowhere."""
    return _out(await service.get_evaluation(db, request_id, user, APP_KEY))


@router.put("/requests/{request_id}/evaluation")
async def save_evaluation(
    request_id: str, payload: EvaluationWriteIn, user: CanEditEvaluation, db: Db
) -> EvaluationOut:
    """Save Parte C — and when it carries the decision, move the card and write the ledger.

    Evaluator and instant come from the session; the payload cannot state either.
    """
    return _out(await service.save_evaluation(db, request_id, payload, user, APP_KEY))


@router.get("/requests/{request_id}/status")
async def read_status(request_id: str, user: CanEditRequests, db: Db) -> RequestStatusOut:
    """Stage, submitted_at, decision and team_note — and nothing else, by contract."""
    status = await service.request_status(db, request_id, user, APP_KEY)
    return RequestStatusOut(**status._asdict())
