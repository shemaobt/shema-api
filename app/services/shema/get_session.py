"""``GET /api/shema/session``'s three answers, each read from the place that owns it.

``GET /api/auth/my-roles`` cannot answer this and never will: the grant has no region
(FE-44 §3.1). What it adds is the region, and **none of the three parts is a new store** —
``role`` comes from ``authorization_service.list_roles``, ``regionScope`` from
``shema_user_regions`` through ``_scope.py``, and ``name`` from the org chart
``shema_region_teams``, which FE-44 §5.3 freezes as the single source of who holds which
role where, with the session named as one of its four consumers.

**Open question 4 of** ``docs/shema.md`` **§10 is answered here: yes, the name falls back to**
``users.display_name``. The argument, since §6.3 asked for one rather than a coin toss:

* The rule the org chart protects is *never duplicate a role-holder's name into another
  model*, and it exists so a rename has one place to happen. ``globalStrategist`` **has no
  seat** — the chart's three roles are per region — so for that role there is no fact being
  duplicated and no rename to follow. The rule does not reach it.
* The alternative is ``null``, which the contract permits (``name: string | null``). But the
  console's one remaining hardcoded name is ``GLOBAL_STRATEGIST_NAME`` (FE-44 §12.2), and
  retiring it is a thing this endpoint exists to do. Answering ``null`` guarantees the
  hardcode stays, which is the outcome with a name in a file nobody maintains.
* ``display_name`` is the account's own name, owned by the account. Renaming it renames who
  the session says you are — which is exactly the property the chart gives the other three.

**The fallback is one rule and not four special cases.** A seat is looked up when there is
exactly one seat to look up: the role has a seat in the chart, and the scope names exactly
one region. Global scope, a scope spanning two regions, ``globalStrategist``, and an
unassigned seat all land on ``display_name`` — and the last of those is not an edge case
today but the normal one, because all twenty-one seats ship unassigned on purpose.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_enums import ShemaRegionKey, ShemaRoleKey
from app.db.models.shema_org_chart import ShemaRegionTeam
from app.models.shema_session import ShemaSession
from app.services.shema._scope import RegionScope, granted_roles, role_from, scope_from_roles


async def _seat_holder(db: AsyncSession, region_key: str, role: str) -> str:
    """The chart's name for one seat, or ``""`` when the seat is unassigned."""
    try:
        seat_role = ShemaRoleKey(role)
    except ValueError:
        return ""

    stmt = select(ShemaRegionTeam.holder_name).where(
        ShemaRegionTeam.region_key == ShemaRegionKey(region_key),
        ShemaRegionTeam.role == seat_role,
    )
    return (await db.execute(stmt)).scalar_one_or_none() or ""


async def _resolve_name(
    db: AsyncSession, user: User, role: str | None, scope: RegionScope
) -> str | None:
    if role is not None and not scope.global_ and len(scope.regions) == 1:
        holder = await _seat_holder(db, next(iter(scope.regions)), role)
        if holder:
            return holder
    return user.display_name or None


async def get_session(db: AsyncSession, user: User, app_key: str) -> ShemaSession:
    """The signed-in persona, as FE-44 §9.13 froze it.

    The roles are read once and answer both ``role`` and ``regionScope``, which is why
    ``_scope.py`` exposes :func:`~app.services.shema._scope.scope_from_roles` beside
    :func:`~app.services.shema._scope.region_scope` — the two questions come from one
    fact and asking them separately read that fact twice.

    No cache. The guard that let the caller in already consulted the role cache, and this
    endpoint is asked once per sign-in rather than once per request; a second cache here
    would buy nothing and would hold a persona that a rename in the org chart is supposed
    to change immediately.
    """
    granted = await granted_roles(db, user.id, app_key)
    role = role_from(granted)
    scope = await scope_from_roles(db, user, granted)
    return ShemaSession(
        role=role,
        regionScope=scope.wire,
        name=await _resolve_name(db, user, role, scope),
    )
