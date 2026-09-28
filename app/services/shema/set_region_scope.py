"""Writing an account's region scope — the module's half of a two-part grant.

The **role** is granted through ``app/services/authorization/grant_app_role.py`` and never
through ``scripts/grant_app_role.py``, which matches on ``(user_id, app_id)`` and
*overwrites* ``role_id`` (OBT-484) — and a Shemá account legitimately holds more than one
role, so that script would silently drop one. That half is the platform's and this module
does not reimplement it.

This is the other half, and it is the module's own table. The two stay separate calls: the
role belongs to the auth spine and the region to this module, and a wrapper here would be a
third place that knows what a Shemá grant is. **What composes them is the Admin's surface**
(OBT-543, ``docs/shema.md``, *The Admin grants*): ``grant_role`` writes a regional role and
its regions in one commit, and ``_grant_rules.py`` is the one owner of the rule that a
regional role is granted with its regions and any other role touches none. An operator can
still call this function alone, the way the other applications' grants were written before
they had screens.

**This file is the scope's only writer, and it writes the trail too.** Every region that
enters or leaves an account leaves a row in ``shema_scope_changes``, by whom and when — so the
Admin's history sees a coordinator moved between regions, which writes no role row at all,
and it sees it whichever caller made the move. ``held_regions`` is the rows' one reader
outside ``_scope.py``, which reads them only to compute a reach.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_grant import ShemaScopeChange
from app.db.models.shema_region import ShemaUserRegion

logger = logging.getLogger(__name__)


async def held_regions(db: AsyncSession, user_id: str) -> list[ShemaUserRegion]:
    """The account's scope rows as they stand — who granted each and when — by region key.

    The stored rows and not the reach: a row counts only under a regional role, and what an
    account actually reaches is ``_scope.scope_from_roles``'s to say. The Admin's screen shows
    both, because the rows are what it edits.
    """
    rows = await db.execute(
        select(ShemaUserRegion)
        .where(ShemaUserRegion.user_id == user_id)
        .order_by(ShemaUserRegion.region_key)
    )
    return list(rows.scalars())


async def set_region_scope(
    db: AsyncSession,
    user_id: str,
    regions: Iterable[ShemaRegionKey | str],
    *,
    granted_by: str | None = None,
    commit: bool = True,
) -> list[ShemaRegionKey]:
    """Make ``regions`` the account's whole scope, and answer what it now holds.

    **Replace and not append.** A scope is the answer to *how far does this account reach*,
    so the caller states it entirely; an append-only spelling would make narrowing someone
    a two-call operation, and the call that removes is the one an operator forgets. Rows
    already present keep their ``granted_at`` — re-stating a scope is not a new grant of
    the part that did not change, and an audit question asked later should not find every
    seat stamped with the day somebody added one region.

    Passing an empty ``regions`` leaves the account reaching **nothing**, not everything.
    ``app/services/shema/_scope.py`` is where that floor is argued; it is repeated here
    because this is the call that can put an account on it by accident.

    ``granted_by`` is the person acting, and the trail records them for a region that leaves
    as well as for one that enters. Only what changed is recorded: re-stating the same scope
    writes nothing. An unknown key raises before anything is written.
    """
    wanted = {key if isinstance(key, ShemaRegionKey) else ShemaRegionKey(key) for key in regions}

    held = set(
        (
            await db.execute(
                select(ShemaUserRegion.region_key).where(ShemaUserRegion.user_id == user_id)
            )
        ).scalars()
    )

    for key in sorted(held - wanted, key=lambda k: k.value):
        await db.execute(
            delete(ShemaUserRegion).where(
                ShemaUserRegion.user_id == user_id, ShemaUserRegion.region_key == key
            )
        )
        db.add(
            ShemaScopeChange(user_id=user_id, region_key=key, granted=False, changed_by=granted_by)
        )
    for key in sorted(wanted - held, key=lambda k: k.value):
        db.add(ShemaUserRegion(user_id=user_id, region_key=key, granted_by=granted_by))
        db.add(
            ShemaScopeChange(user_id=user_id, region_key=key, granted=True, changed_by=granted_by)
        )

    if commit:
        await db.commit()
    else:
        await db.flush()

    logger.info(
        "shema region scope written",
        extra={
            "shema_user_id": user_id,
            "shema_regions": sorted(key.value for key in wanted),
            "shema_granted_by": granted_by,
        },
    )
    return sorted(wanted, key=lambda k: k.value)
