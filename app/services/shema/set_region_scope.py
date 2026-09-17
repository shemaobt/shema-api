"""Writing an account's region scope — the module's half of a two-part grant.

The **role** is granted through ``app/services/authorization/grant_app_role.py`` and never
through ``scripts/grant_app_role.py``, which matches on ``(user_id, app_id)`` and
*overwrites* ``role_id`` (OBT-484) — and a Shemá account legitimately holds more than one
role, so that script would silently drop one. That half is the platform's and this module
does not reimplement it.

This is the other half, and it is the module's own table. The two are deliberately separate
calls rather than one wrapper: a wrapper would be a third place that knows what a Shemá
grant is, and the day the client wants a role without a region — ``globalStrategist``
already is one — the wrapper is the thing that has to grow a special case.

**There is no route here yet**, and that is not an oversight. Who may hand out a region is a
question about a screen nobody has drawn: the org chart is BE-13's (FE-44 §5.3), and the
platform's own granting surface is ``app/api/roles.py``. Until one of them owns it, the
scope is written by an operator through this function, the same way the other seven
applications' grants were before they had screens.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_region import ShemaUserRegion

logger = logging.getLogger(__name__)


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
    for key in sorted(wanted - held, key=lambda k: k.value):
        db.add(ShemaUserRegion(user_id=user_id, region_key=key, granted_by=granted_by))

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
