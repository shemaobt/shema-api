"""The network directory: who consented to be listed, and how many are not shown.

**The consent gate is the query**, in ``_directory.listable_ids`` — FE-44 §8.2's third rule,
which the contract states for prayer text and which holds identically for a person. Somebody
who agreed that the Resource Circle may write to them has not agreed to be on a screen, and
the two answers are separate rows (``app/db/models/shema_consent.py``).

**The count of who is not shown travels with the list.** FE-44 §8.1 rule 2 makes the map
announce how many projects it is withholding, *because a silently incomplete map is its own
hazard*. A directory filtered by consent has exactly that hazard: a Resource Circle member who
cannot tell a short network from a filtered one concludes the wrong thing about both. The
number is a number and never a name, and it is counted rather than read — nothing that
identifies a withheld person is loaded into the process at all.

**Neither is the count of who among them is past their year** (OBT-531). The one-year review
flags an entry the list carries, and a person with no ``directory`` consent is on no list, so
nobody could review them on a screen. ``withheldReviewDueCount`` is what says they exist: three
dates per person are read, counted through ``_directory.review_due`` and discarded — no id, no
name, no country and no contact.

**No region scope.** The network is people around the world with no project and no region
(``docs/shema.md`` §5.7), and giving it one would be the ``regionKey`` *"added for
convenience"* that FE-44 §5.5 says a format check would not survive. The narrowing here is by
role, in the router, and it is one role.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shema_intercessor import IntercessorDirectory
from app.services.shema._directory import (
    count_people,
    count_review_due,
    entries_of,
    listable_ids,
)


async def list_intercessors(
    db: AsyncSession, *, now: datetime | None = None
) -> IntercessorDirectory:
    """Everyone who consented to be listed, plus how many did not and how many of those are due.

    Five statements whatever the size of the network — the gate, the order, the two counts and
    the batched read — rather than two per person; ``entries_of`` carries the argument. One
    clock for the whole answer, so an entry and the count beside it cannot disagree about the
    year by the length of a request.
    """
    moment = now or datetime.now(UTC)
    visible = await listable_ids(db)
    total = await count_people(db)
    return IntercessorDirectory(
        people=await entries_of(db, visible, now=moment),
        withheldCount=total - len(visible),
        withheldReviewDueCount=await count_review_due(db, excluding=visible, now=moment),
    )
