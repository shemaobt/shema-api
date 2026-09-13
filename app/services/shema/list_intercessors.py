"""The network directory: who consented to be listed, and how many are not shown.

**The consent gate is the query**, in ``_directory.listable_ids`` — FE-44 §8.2's third rule,
which the contract states for prayer text and which holds identically for a person. Somebody
who agreed that the Resource Circle may write to them has not agreed to be on a screen, and
the two answers are separate rows (``app/db/models/shema_consent.py``).

**The count of who is not shown travels with the list.** FE-44 §8.1 rule 2 makes the map
announce how many projects it is withholding, *because a silently incomplete map is its own
hazard*. A directory filtered by consent has exactly that hazard: a Resource Circle member who
cannot tell a short network from a filtered one concludes the wrong thing about both. The
number is a number and never a name, and it is counted rather than read — nothing about a
withheld person is loaded into the process at all.

**No region scope.** The network is people around the world with no project and no region
(``docs/shema.md`` §5.7), and giving it one would be the ``regionKey`` *"added for
convenience"* that FE-44 §5.5 says a format check would not survive. The narrowing here is by
role, in the router, and it is one role.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shema_intercessor import IntercessorDirectory
from app.services.shema._directory import count_people, entries_of, listable_ids


async def list_intercessors(db: AsyncSession) -> IntercessorDirectory:
    """Everyone who consented to be listed, plus how many did not.

    Four statements whatever the size of the network — the gate, the order, the count and
    the batched read — rather than two per person; ``entries_of`` carries the argument.
    """
    visible = await listable_ids(db)
    total = await count_people(db)
    return IntercessorDirectory(
        people=await entries_of(db, visible),
        withheldCount=total - len(visible),
    )
