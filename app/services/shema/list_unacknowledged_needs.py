"""The one query the area exists for: needs nobody has answered, and nobody has even seen.

**The failure this module is built to prevent is silence.** A need raised in March and still
open in the following March, with nobody having so much as said *we have seen this*, is not a
backlog item — it is the thing the *Necessidades* area exists to make impossible to miss. A
failure of that shape is only preventable if it is **findable**, and findable means one query
rather than a person remembering to look.

So the two axes are stored and this asks them together: ``status`` is *what is happening* and
``acknowledged_at`` is *whether anybody looked*, and the sweep is the conjunction of *still
somebody's problem* and *nobody has looked* and *for longer than this*.
``ix_shema_needs_unacknowledged`` is its index, leading on the column the sweep pins.

**Scoped, like every read in this module.** The needs are reached through
``visible_projects(scope)``, so a caller who may not see a region does not learn that it has
an unanswered need — which for a sensitive project is the existence fact ``_scope.py`` refuses
to hand out. There is no unscoped spelling of this call: ``scope`` is positional and has no
default, for the reason ``list_projects`` states.

**It answers rows and not a number.** *Seven needs outstanding* is a sentence nobody can act
on; the categories are not commensurable, the currencies are not commensurable, and a total
would be an invitation to treat them as if they were. What a caller gets is the needs, and
what it does with them is its own.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import Select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema import ShemaProject
from app.db.models.shema_need import ShemaNeed
from app.models.shema_need import ShemaNeedLine
from app.services.shema._scope import RegionScope, visible_projects
from app.utils.shema_facets import OPEN_NEED_STATUSES

#: How long a need may sit unseen before this query is interested in it.
#:
#: **Thirty days, which is the product's own first band**: FE-44 §7.7's ``recent`` preset calls
#: a record recent for thirty days, so a month is already the interval this product means by
#: *nothing has happened lately*. It is a parameter and not a constant in a predicate, because
#: the band that matters to a coordinator (a fortnight before a rhythm meeting) and the band
#: that matters to a strategist (the year the issue names) are different questions of one
#: column — and neither of them should cost a migration to ask.
UNACKNOWLEDGED_AFTER_DAYS = 30


def raised_on() -> Any:
    """The day a need is aged from — its own, or the day the row arrived.

    ``submitted_at`` is what the product shows and what a derived notification is keyed on, and
    :func:`~app.services.shema._needs._new_need` fills it for everything this module writes. It
    is still nullable, because BE-12's import and BE-16's seed carry rows this module did not
    type — so the fallback is the row's own arrival, and an undated need **ages** instead of
    being invisible. Falling back to *now* would have been the same bug the acknowledgement
    column exists to prevent, one column along: a need nothing can measure is a need nothing
    reports.

    ``func.date`` rather than a cast: SQLite has no date type and ``CAST(x AS DATE)`` there
    gives a number, while ``date(x)`` is understood by both dialects — and SQLite is the one
    the suite can watch.
    """
    return func.coalesce(ShemaNeed.submitted_at, func.date(ShemaNeed.created_at))


def unacknowledged_needs(
    scope: RegionScope, *, before: date
) -> Select[tuple[ShemaProject, ShemaNeed]]:
    """The statement — open, unacknowledged, raised no later than ``before``, inside ``scope``.

    **It starts at** ``visible_projects(scope)`` **and not at a** ``select`` **of its own**,
    which is ``_scope.py``'s stated mechanism rather than a style: the region predicate is
    underneath the join rather than beside it, so a ``LIMIT``, an ``ORDER BY`` or a ``count()``
    layered on this stays scoped. A query that could return an out-of-scope row is a bug even
    if no caller writes it that way, and the way to make that true is for there to be no
    unscoped statement to build on.

    A ``Select`` rather than a list, so the caller that wants a page or a count has one to
    build. The join is inner, because a need whose project the caller cannot reach is not a
    need the caller has.
    """
    return (
        visible_projects(scope)
        .join(ShemaNeed, ShemaNeed.project_id == ShemaProject.id)
        .add_columns(ShemaNeed)
        .where(
            ShemaNeed.status.in_(sorted(OPEN_NEED_STATUSES)),
            ShemaNeed.acknowledged_at.is_(None),
            raised_on() <= before,
        )
        .order_by(raised_on(), ShemaNeed.id)
    )


async def list_unacknowledged_needs(
    db: AsyncSession,
    scope: RegionScope,
    *,
    today: date,
    after_days: int = UNACKNOWLEDGED_AFTER_DAYS,
) -> list[ShemaNeedLine]:
    """Every need inside ``scope`` that has been open and unseen for ``after_days``.

    Answers :class:`~app.models.shema_need.ShemaNeedLine`, which is a
    :class:`~app.models.shema_privacy.LeavingShape`: this is a *list* and FE-44 §8.7's rule is
    that display is never enforcement, so the rows leave reduced even though the caller could
    open each record. BE-04's own departure note makes the same call for the collection read
    and for the same sentence.

    ``today`` is injected rather than read, which is the module's habit and its reason: the
    whole path from a request to a threshold is then a pure function of a day the caller names,
    and a test can move the calendar without moving the machine.
    """
    before = today - timedelta(days=after_days)
    rows = await db.execute(unacknowledged_needs(scope, before=before))
    return [ShemaNeedLine.of(need, project) for project, need in rows]
