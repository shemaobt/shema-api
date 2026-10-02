from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError
from app.db.models.resource_request import (
    RRBudgetLine,
    RRDecision,
    RREvaluation,
    RRRequest,
    RRRequestSections,
    RRSnapshot,
    RRStage,
)
from app.services.resource_request._editing import require_reviser
from app.services.resource_request._instance import flush_the_instance, refuse_a_second_open
from app.services.resource_request._link_actor import LinkActor
from app.services.resource_request._writer import Writer
from app.services.resource_request.read_as import request_for


async def _require_reviser(
    db: AsyncSession, request: RRRequest, writer: Writer, app_key: str
) -> None:
    """``require_reviser`` for a person; for a request link, the link that started the request.

    A link's holder has no account and no board to stand on, so the only link that reopens a
    request is the one in ``started_by_link_id`` — the pen of the original, as a person's is
    ``started_by``. Another link never reaches the request at all (404 from ``request_for``).
    """
    if isinstance(writer, LinkActor):
        if request.started_by_link_id != writer.link.id:
            raise AuthorizationError("Only the link that started this request opens its revision.")
        return
    await require_reviser(db, request, writer, app_key)


async def open_revision(
    db: AsyncSession, request_id: str, writer: Writer, app_key: str
) -> RRRequest:
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

    **The revision is the project's new instance, and it is born under the instance's rules**
    (BE-25, OBT-534): the pen goes to whoever held the old one (``started_by`` is copied, like
    ``created_by``), and a project that meanwhile opened another draft refuses the revision
    with 409, because two open instances in one project is the one state GATE-04 D6 forbids.
    Who may *open* it is ``require_reviser`` — the starter or the board — and not
    ``require_editor``: reopening a frozen request is not typing into a draft.

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
    ``tpp_name``/``tpp_date`` do carry — typed content of the team's, not a server act — and
    so does ``leader_email`` (BE-23, OBT-535): the revision goes back to the same base leader
    unless the team changes the address, which is exactly what a revision is for. Its new
    link is issued when the revision is submitted, like any other.

    **A request entered by the Admin's link revises under that link** (FE-55, OBT-542). Its
    holder reopens it — the link that started it, never another — and the revision inherits
    ``request_link_id`` and ``started_by_link_id``, so the pen stays with the link and the new
    draft is still that link's one open instance: ``refuse_a_second_open`` reads the link when
    there is no project. Copied for whoever opens it — the board reopening a link's request
    leaves it the link's, as its reopening a project's leaves it the project's.

    **The board also reopens a request it sent back to *Revisar* itself** (FE-47, OBT-515).
    Karina, via Daniel, 1/out/2026: when the Gestor needs to change a request the mesa already
    evaluated, *"Gestor abre revisão em nome da equipe"*. The Gestor cannot decide — he
    *"só não aprova"* (GATE-02 D3) — but he moves the board, so the path is two acts he already
    has: move the card to *Revisar*, which takes an approval's money back by the board's own
    golden rule (BE-08), then open the revision here. So a board member — never the team, which
    still needs the mesa's *revisar* — opens one whenever the card **is** in *Revisar*, whatever
    the evaluation said or whether there is one. Only on that path does the pen go to whoever
    opened it: the revision is still the team's (``created_by`` and the project carry over, so
    it stays in the team's list and the instance lock still holds), but the Gestor is the one
    who changes it and sends it back to the mesa. After a *revisar* decision nothing moves:
    the team rewrites, as before. Reading the card's column rather than a decision, and handing
    the pen to the board, are ours and not the client's.
    """
    loaded = await request_for(db, request_id, writer, app_key)
    await _require_reviser(db, loaded.request, writer, app_key)

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
    original = loaded.request
    board_opener = None if isinstance(writer, LinkActor) else writer.id
    by_the_board = (
        decision is not RRDecision.REVISE
        and board_opener is not None
        and original.started_by != board_opener
        and original.stage is RRStage.REVISAR
    )
    if decision is not RRDecision.REVISE and not by_the_board:
        raise ConflictError(
            "A revision opens only after the mesa asks for one, or once the board has moved the "
            "card to Revisar. "
            f"This request's decision is {decision.value if decision else 'not recorded yet'}."
        )

    revision = RRRequest(
        request_type=original.request_type,
        reg_name=original.reg_name,
        currency=original.currency,
        amount_requested=original.amount_requested,
        declaration=original.declaration,
        tpp_name=original.tpp_name,
        tpp_date=original.tpp_date,
        leader_email=original.leader_email,
        created_by=original.created_by,
        started_by=board_opener if by_the_board else original.started_by,
        shema_project_id=original.shema_project_id,
        request_link_id=original.request_link_id,
        started_by_link_id=None if by_the_board else original.started_by_link_id,
        revision_of_id=snapshot.id,
    )
    await refuse_a_second_open(db, original.shema_project_id, link_id=original.request_link_id)
    db.add(revision)
    await flush_the_instance(db)

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
