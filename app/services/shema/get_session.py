"""``GET /api/shema/session``'s answers, each read from the place that owns it.

``GET /api/auth/my-roles`` cannot answer this and never will: the grant has no region
(FE-44 §3.1). What it adds is the region, and **none of the parts is a store of the session's
own** — ``roles`` (and ``role``, its first entry) come from ``authorization_service.list_roles``
through ``_scope.session_roles`` — plus, since OBT-524, the ``equipe`` a live row in
``shema_project_members`` adds — ``regionScope`` from ``shema_user_regions`` through
``_scope.py``, and ``name`` from the org chart ``shema_region_teams``, which FE-44 §5.3 freezes
as the single source of who holds which role where, with the session named as one of its four
consumers.

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

**``apps`` is the registry's row, read once per sign-in** (OBT-544). The form's address is
``apps.app_url`` — the value its own letters build their links from — so the console opens
the form where the form says it lives, and a registry without the value answers ``None``
rather than an address the console would have to invent.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_enums import ShemaRegionKey, ShemaRoleKey
from app.db.models.shema_org_chart import ShemaRegionTeam
from app.models.shema_session import SessionApps, ShemaSession
from app.services.authorization.get_app_by_key import get_app_by_key
from app.services.shema._scope import RegionScope, role_from, roles_from, scope_from_roles


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


async def _app_url(db: AsyncSession, app_key: str) -> str | None:
    """The registry's address for ``app_key``, without a trailing slash, or ``None``."""
    app = await get_app_by_key(db, app_key)
    url = (app.app_url or "").strip().rstrip("/") if app is not None else ""
    return url or None


async def get_session(
    db: AsyncSession, user: User, *, roles: tuple[str, ...], form_app_key: str
) -> ShemaSession:
    """The signed-in persona, as FE-44 §9.13 froze it and OBT-523 widened it.

    ``roles`` is what the PME's door already read — ``_scope.session_roles`` — handed down
    rather than read again, and answered in :data:`~app.services.shema._scope.ROLE_PRECEDENCE`
    order whatever order it arrived in, the same trade
    :func:`~app.services.shema._scope.scope_from_roles` exists for: the door and the body are
    one fact and asking it twice read it twice. **Keyword-only on purpose**: this function
    took an app key positionally until OBT-523, and a ``str`` is a sequence of strings, so a
    caller still passing one would have been answered off the letters of ``"shema"``.

    No cache. The session is asked once per sign-in rather than once per request; a cache
    here would buy nothing and would hold a persona that a rename in the org chart is
    supposed to change immediately.

    ``form_app_key`` is handed in by the router, as ``session_roles`` takes it: a service does
    not import the router that names it.
    """
    held = frozenset(roles)
    role = role_from(held)
    scope = await scope_from_roles(db, user, held)
    return ShemaSession(
        role=role,
        roles=list(roles_from(held)),
        regionScope=scope.wire,
        name=await _resolve_name(db, user, role, scope),
        apps=SessionApps(resourceRequestForm=await _app_url(db, form_app_key)),
    )
