from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import (
    RREvaluation,
    RREvaluationScore,
    RRRequest,
    RRSnapshot,
)
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
    previous one's total (``team_outcome`` and ``get_evaluation`` read the same way).

    **Not a field of ``RequestOut``**, whose docstring keeps ``rr_evaluations`` out of it so the
    team's progress bar can never carry a score (§5.3): the totals are their own read, behind
    ``view_evaluation``, which the team does not hold. The scope is ``list_requests``' own, so
    a total never names a request its caller could not list. Three statements whatever the
    number of requests: the reach, then one select joining the latest snapshot, its evaluation
    and its scores.
    """
    newest = (
        select(RRSnapshot.request_id, func.max(RRSnapshot.created_at).label("created_at"))
        .group_by(RRSnapshot.request_id)
        .subquery()
    )
    stmt = (
        select(RRSnapshot.request_id, RREvaluationScore.score)
        .join(
            newest,
            (newest.c.request_id == RRSnapshot.request_id)
            & (newest.c.created_at == RRSnapshot.created_at),
        )
        .join(RREvaluation, RREvaluation.snapshot_id == RRSnapshot.id)
        .outerjoin(RREvaluationScore, RREvaluationScore.evaluation_id == RREvaluation.id)
        .join(RRRequest, RRRequest.id == RRSnapshot.request_id)
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
