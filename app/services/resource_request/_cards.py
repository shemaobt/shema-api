"""The card projection of a request — BE-24 (OBT-536), one shape for two readers.

The PME's project page (OBT-544) and the form's tracking list (FE-46, OBT-514) both draw a
request as a card: which request it is, where it is, whether it was decided, whether the
caller may write it now. ``docs/resource_requests.md`` §10 item 6 named that projection as
unowned; this is its owner, and ``RequestCardOut.of`` is its only constructor.

**The ceiling is GATE-03 D4's — status and nothing else.** Everything here is a column of the
request's own spine except ``decision``, which is the one column of the evaluation a team is
entitled to (``request_status`` reads the same one). Scores, comments, the attendees, the
evaluator and the team note never leave this module, and they are never selected.

**No trip per row.** A card list is read on a field connection (RF-NF-07), so the decisions
of every listed request come from one statement and the starters' names from another, and
``can_edit`` from the caller's roles read once (``_editing.Editing``).
"""

from collections.abc import Sequence
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRDecision, RREvaluation, RRRequest, RRSnapshot
from app.services.resource_request._editing import Editing


class CardFacts(NamedTuple):
    """What a card is built from — the row, plus the three answers the row cannot give."""

    request: RRRequest
    decision: RRDecision | None
    can_edit: bool
    #: Who is filling the instance in, for *"em preenchimento por X"* — only for an open
    #: instance, where the sentence exists. A submitted request is the team's, and naming one
    #: member on it would say more than the card needs.
    started_by_name: str | None


def is_open(request: RRRequest) -> bool:
    return request.submitted_at is None and request.cancelled_at is None


async def _decisions(db: AsyncSession, ids: list[str]) -> dict[str, RRDecision | None]:
    """The decision on each request's **latest** snapshot, as ``team_outcome`` defines it.

    Ordered oldest first, so the last row read for a request is its latest snapshot and the
    dict keeps it — an unevaluated newer snapshot answers ``None`` rather than falling back to
    what the mesa decided about an older one.
    """
    if not ids:
        return {}
    rows = await db.execute(
        select(RRSnapshot.request_id, RREvaluation.decision)
        .outerjoin(RREvaluation, RREvaluation.snapshot_id == RRSnapshot.id)
        .where(RRSnapshot.request_id.in_(ids))
        .order_by(RRSnapshot.created_at)
    )
    return dict(rows.tuples().all())


async def _starter_names(db: AsyncSession, ids: set[str]) -> dict[str, str | None]:
    if not ids:
        return {}
    rows = await db.execute(select(User.id, User.display_name).where(User.id.in_(ids)))
    return dict(rows.tuples().all())


async def cards_of(
    db: AsyncSession, rows: Sequence[RRRequest], editing: Editing
) -> list[CardFacts]:
    """The card facts of ``rows``, in their order, from two statements whatever their count."""
    decisions = await _decisions(db, [row.id for row in rows])
    starters = {row.started_by for row in rows if is_open(row) and row.started_by is not None}
    names = await _starter_names(db, starters)
    return [
        CardFacts(
            request=row,
            decision=decisions.get(row.id),
            can_edit=editing.can_edit(row),
            started_by_name=(
                names.get(row.started_by) if is_open(row) and row.started_by else None
            ),
        )
        for row in rows
    ]
