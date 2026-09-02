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

    **A *conditional* decision does not reopen a draft, and after 28/aug/2026 that has to
    be written here.** The client's answer about revision — *"caso tenha a necessidade de
    revisão a equipe recebe um aviso"* — names *revisar* and *condicional* in one breath, so
    whoever arrives at this function carrying it expects both to reopen. They do not do the
    same thing: *revisar* sends the document back to be rewritten, and *condicional* approves
    with a condition attached and leaves the document exactly as it was evaluated. The
    **notice** covers both and is BE-13's; the **new row** is *revisar*'s alone. Widening the
    check to ``RRDecision.CONDITIONAL`` would let a team edit a request the mesa has already
    approved, and ``test_only_a_revise_decision_opens_a_revision`` is parametrized over that
    decision precisely so the widening fails a test rather than passing review.

    **Asking for exactly one evaluation is safe, and it was not always.** Review of PR #269
    caught this reading a schema where the uniqueness was *one per snapshot per evaluator* —
    and two NULL evaluators are never equal in SQL, so a snapshot could carry any number of
    unauthored rows and this query would answer 500 instead of a revision. BE-02 has since
    tightened the constraint to ``uq_rr_evaluations_snapshot``, which is GATE-02 D5's
    *one evaluation per mesa* becoming a column rule, so the second row can no longer exist.
    The defensive ordering that stood here went with it: carrying a tie-break for a state the
    database refuses would be describing a hazard that is gone.

    The new draft copies the content rather than pointing at it, because from here it is the
    team's to change and the old one must not move.

    **The Líder's line does not carry over** — neither the act (``endorsed_by``/
    ``endorsed_at`` stay at their defaults on the new row) nor the display pair born from
    it (BE-16): a signature given to a frozen version does not follow a text that is about
    to change, and a revision goes back to its base's leader like any other new document.
    ``tpp_name``/``tpp_date`` do carry — typed content of the team's, not a server act.
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
            select(RREvaluation.decision).where(RREvaluation.snapshot_id == snapshot.id)
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
