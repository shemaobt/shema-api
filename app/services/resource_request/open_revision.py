from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.auth import User
from app.db.models.resource_request import (
    RRBudgetLine,
    RRDecision,
    RREvaluation,
    RRRequest,
    RRRequestSections,
    RRSnapshot,
)
from app.services.resource_request.get_request import get_request


async def open_revision(db: AsyncSession, request_id: str, user: User, app_key: str) -> RRRequest:
    """Reopen an evaluated request as a new draft, linked back to what was evaluated.

    A revision is a **new row**, never an edit. The mesa's comments reference section
    numbers, and those have to keep pointing at the text they meant — so the snapshot the
    mesa read stays exactly as it was and the team gets a fresh document that remembers
    where it came from. ``rr_requests.revision_of_id`` points at the **snapshot** rather
    than at the request for the same reason: what was evaluated is a frozen document, not a
    row that has moved on since.

    **Only a *revisar* decision opens one**, which is the whole of what the flow means. A
    team cannot reopen a request the mesa approved or declined, and a request nobody has
    evaluated has nothing to revise. Reading ``rr_evaluations.decision`` is this rule; the
    evaluation itself is BE-06's and nothing here writes one.

    **A snapshot can carry more than one evaluation**, so the newest one decides rather than
    the query demanding there be exactly one. ``uq_rr_evaluations_snapshot_evaluator`` is
    *one per snapshot per evaluator*, and two NULL evaluators are never equal in SQL — the
    model says so in its own words: *"a snapshot may carry any number of evaluations with no
    principal — which is every row the seed writes"*. Asking for one row would answer 500
    instead of a revision the moment a second exists. Found in review of PR #269.

    **Ordered by ``evaluated_at``, because that is when the mesa decided**, and GATE-02 D5
    answered *one evaluation per mesa*, so in the product there is one stamped row to find.
    ``created_at`` and then ``id`` follow it only to make the answer deterministic among
    rows BE-06 never stamped — a fixture-only state, where insertion order is the closest
    thing to a meaning available and an arbitrary-but-stable id is better than an answer
    that changes between two reads of the same data.

    The new draft copies the content rather than pointing at it, because from here it is the
    team's to change and the old one must not move.
    """
    loaded = await get_request(db, request_id, user, app_key)

    snapshot = (
        await db.execute(
            select(RRSnapshot)
            .where(RRSnapshot.request_id == request_id)
            .order_by(RRSnapshot.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if snapshot is None:
        raise ConflictError("This request has not been submitted, so there is nothing to revise.")

    decision = (
        await db.execute(
            select(RREvaluation.decision)
            .where(RREvaluation.snapshot_id == snapshot.id)
            .order_by(
                RREvaluation.evaluated_at.desc().nullslast(),
                RREvaluation.created_at.desc(),
                RREvaluation.id.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if decision is not RRDecision.REVISE:
        raise ConflictError(
            "A revision opens only after the mesa asks for one. "
            f"This request's decision is {decision.value if decision else 'not recorded yet'}."
        )

    original = loaded.request
    revision = RRRequest(
        request_type=original.request_type,
        reg_name=original.reg_name,
        currency=original.currency,
        amount_requested=original.amount_requested,
        declaration=original.declaration,
        tpp_name=original.tpp_name,
        tpp_date=original.tpp_date,
        leader_name=original.leader_name,
        leader_date=original.leader_date,
        created_by=original.created_by,
        revision_of_id=snapshot.id,
    )
    db.add(revision)
    await db.flush()

    content = dict(loaded.sections.content) if loaded.sections is not None else {}
    db.add(RRRequestSections(request_id=revision.id, content=content))
    for line in loaded.budget:
        db.add(
            RRBudgetLine(
                request_id=revision.id,
                category_key=line.category_key,
                description=line.description,
                quantity=line.quantity,
                amount=line.amount,
            )
        )

    await db.commit()
    await db.refresh(revision)
    return revision
