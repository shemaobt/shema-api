from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import (
    RREvaluation,
    RREvaluationScore,
    RRRequest,
    RRSnapshot,
)
from app.services.resource_request._evaluation import LATEST_FIRST
from app.services.resource_request._membership import member_project_ids
from app.services.resource_request._scope import reach
from app.utils.resource_request_totals import sum_score


async def list_evaluation_totals(db: AsyncSession, user: User, app_key: str) -> dict[str, int]:
    """The /30 of every evaluated request this caller reaches, by request id — the board's badge.

    The Painel drew each card's ``kc-score`` from one ``GET /requests/{id}/evaluation`` per
    card, so opening the board asked once per request and every request the mesa had not
    started answered 404 — 41 of them on the 29/out bench (OBT-665, RRF-MESA-084). This is
    the same number in one read: the total of the evaluation of each request's **latest**
    snapshot, by ``sum_score``, exactly as :class:`~app.models.resource_request.EvaluationOut`
    derives it. A request with no evaluation of its latest snapshot is simply absent, which is
    the board's *not evaluated yet*; a newer snapshot nobody scored does not fall back to the
    previous one's total, and two snapshots stamped in the same instant are told apart by id —
    ``LATEST_FIRST``, the order ``get_evaluation`` and ``team_outcome`` read by too.

    **Not a field of ``RequestOut``**, whose docstring keeps ``rr_evaluations`` out of it so the
    team's progress bar can never carry a score (§5.3): the totals are their own read, behind
    ``view_evaluation``, which the team does not hold. The scope is ``list_requests``' own, so
    a total never names a request its caller could not list. One select whatever the number
    of requests — the latest snapshot, its evaluation and its scores joined — after the
    caller's reach.
    """
    ranked = select(
        RRSnapshot.id,
        RRSnapshot.request_id,
        func.row_number()
        .over(partition_by=RRSnapshot.request_id, order_by=LATEST_FIRST)
        .label("rank"),
    ).subquery()
    stmt = (
        select(ranked.c.request_id, RREvaluationScore.score)
        .where(ranked.c.rank == 1)
        .join(RREvaluation, RREvaluation.snapshot_id == ranked.c.id)
        .outerjoin(RREvaluationScore, RREvaluationScore.evaluation_id == RREvaluation.id)
        .join(RRRequest, RRRequest.id == ranked.c.request_id)
        .where(RRRequest.cancelled_at.is_(None))
    )
    if not (await reach(db, user, app_key)).every:
        stmt = stmt.where(
            (RRRequest.created_by == user.id)
            | RRRequest.shema_project_id.in_(member_project_ids(user.id))
        )

    scores: dict[str, list[int | None]] = {}
    for request_id, score in (await db.execute(stmt)).all():
        scores.setdefault(request_id, []).append(score)
    return {request_id: sum_score(rows) for request_id, rows in scores.items()}
