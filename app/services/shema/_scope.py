"""How far a caller reaches — the second axis the platform's grant has no column for.

``require_role(app_key, role_key)`` answers a global yes/no per application. Shemá's
authorization is by role **and** by region, and ``docs/shema.md`` §6.1 settles where the
second axis lives: a module-owned table, ``shema_user_regions``, read by this one service.
The split is the sibling's — the platform answers *who are you and in what role*, and the
module answers *how far does that reach*.

**This file holds the module's only ``select(ShemaProject)``, and that is the mechanism
rather than a convention.** The issue's own sentence is that a query which can return an
out-of-scope row is a bug even if no endpoint calls it that way; the way to make that true
is for there to be no unscoped query to call. Every reader in this module starts from
:func:`visible_projects`, which is a ``Select`` with the region predicate already applied,
and ``tests/test_shema/test_scope.py`` globs the package and fails on a second one. A rule
applied per endpoint is a rule the next endpoint forgets; a glob is not — the same argument
``docs/shema.md`` §6.4 makes for the consent gate.

**What a caller sees of another region's project: nothing.** The issue names the two
defensible answers — nothing, or the existence without detail — and asks that one be
chosen rather than fall out of how a query was written. It is *nothing*, and the sharp end
of that choice is the status code: an out-of-scope row is refused with
:class:`~app.core.exceptions.NotFoundError` and never with
:class:`~app.core.exceptions.AuthorizationError`, because a 403 on a direct id **is** the
existence-without-detail answer, delivered by status code. A caller who can tell *this slug
is real but not yours* apart from *no such slug* holds an oracle over the whole collection,
and a Shemá slug is ``<language>-<place>`` — for the records FE-44 §8.1 flags, existence in
a region is precisely the fact being protected. So the two refusals are indistinguishable
on the wire — **and they are indistinguishable in here too**, because the scoped statement
returns no row either way and settling which case it was would take the unscoped query the
404 exists to avoid. What the log below gives an investigator is therefore the event and not
the verdict: who asked, for which id, holding which regions. A misconfigured scope and a
probe look different in those fields, and the id is what somebody allowed to know the answer
joins against.

**Reads and writes take the same value.** A regional holder who may read a region may write
it; the product has no third answer, so nothing here offers one.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

from sqlalchemy import ColumnElement, Select, false, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_region import ShemaUserRegion
from app.services import authorization_service

logger = logging.getLogger(__name__)

#: The role whose reach is every region. It is the one key of the four with no seat in the
#: org chart (FE-44 §5.3 gives the chart three roles *per region*), which is the same fact
#: read from the other side: it is not a regional role, so it is not regionally scoped.
GLOBAL_ROLE = "globalStrategist"
COORDINATOR_ROLE = "coordinator"
OBT_LAB_ROLE = "obtLab"
RESOURCE_CIRCLE_ROLE = "resourceCircle"

#: The three roles the org chart holds per region. Holding one of these and no row in
#: ``shema_user_regions`` reaches nothing — see :func:`region_scope`.
REGIONAL_ROLES = (COORDINATOR_ROLE, OBT_LAB_ROLE, RESOURCE_CIRCLE_ROLE)

#: The four Shemá role keys, in FE-44's own order — the ``SessionRole`` union of
#: ``src/types/role.ts``, read verbatim rather than translated (``docs/shema.md`` §2.3).
#:
#: **That order is also widest-first, so it is the precedence** :func:`role_from` **reads**,
#: and the two uses are one tuple on purpose. ``GET /api/shema/session`` owes the frontend
#: exactly one ``SessionRole`` while an account legitimately holds more than one grant — a
#: regional ``coordinator`` who is also ``resourceCircle`` is the example ``docs/shema.md``
#: §4.2 uses for why grants go through ``grant_app_role`` and never through
#: ``scripts/grant_app_role.py``. Answering by a written order is what keeps two calls from
#: answering differently; a second tuple stating the same four keys is what would let the
#: seed and the guard disagree.
ROLE_KEYS = (GLOBAL_ROLE, COORDINATOR_ROLE, OBT_LAB_ROLE, RESOURCE_CIRCLE_ROLE)


class RegionScope(NamedTuple):
    """How far a caller reaches, as the two answers the scope actually has.

    **One value from one read**, which is the ``Reach`` precedent of
    ``app/services/resource_request/_scope.py`` and holds for its reason: the two questions
    come from one fact, and asking them separately read that fact twice per request.

    ``global_`` and a non-empty ``regions`` are not both meaningful — a reach that contains
    every region contains any particular one — so a global caller carries the empty set and
    every consumer asks ``global_`` first. :func:`within_scope` is the one place that
    ordering is written.
    """

    #: Every region. A platform admin, or a holder of ``globalStrategist``.
    global_: bool
    #: The regions named in ``shema_user_regions``. **Empty and not global reaches
    #: nothing**, which is this module's fail-closed floor rather than an accident of the
    #: query — see :func:`region_scope`.
    regions: frozenset[str]

    @property
    def wire(self) -> list[str] | None:
        """``regionScope`` as FE-44 §9.13 freezes it: ``RegionKey[] | null``, ``null`` = global.

        Sorted, because the frontend renders the list and an unordered one would reshuffle
        between requests for no reason a reader could explain.
        """
        return None if self.global_ else sorted(self.regions)


async def granted_roles(db: AsyncSession, user_id: str, app_key: str) -> set[str]:
    """The role keys this account holds in ``app_key``, read fresh.

    Deliberately not the cached list ``require_app_access`` keeps: that cache exists to
    spare a join on every request to a route the account already passed, and it can be up
    to ``AUTH_CACHE_TTL_SECONDS`` stale for a grant written in another process. A scope
    decides which rows leave, so it reads the grant as it stands — the same trade
    ``app/services/resource_request/holds_capability.py`` makes, and for the same half.
    """
    pairs = await authorization_service.list_roles(db, user_id, app_key)
    return {role_key for _app_key, role_key in pairs}


async def region_scope(db: AsyncSession, user: User, app_key: str) -> RegionScope:
    """The caller's reach, from their roles and their rows in ``shema_user_regions``.

    **A platform admin is global**, short-circuiting before either query, as they pass
    every other guard in this repository (``docs/shema.md`` §4.2). The cost lands on the
    tests and is stated there: a negative test written per role must not use an admin
    account, or it passes for the wrong reason.

    **"No rows means global" holds for** ``globalStrategist`` **and for nobody else**, and
    this is the one place ``docs/shema.md`` §6.1 is read narrowly on purpose. That section
    names who the empty case serves — *"the ``globalStrategist``, and any account the
    client wants unscoped"* — and reading it as *anyone with no rows is global* inverts the
    product's own sentence, which is that a regional coordinator sees **their** region. It
    also opens a hole with a real path to it: ``app/services/access_request`` grants a role
    on approval and grants no region, so every approved account would land globally scoped
    by default. So a regional role with no row reaches nothing, and making such an account
    global is an explicit act — name its regions, or grant it ``globalStrategist`` as well.
    """
    if user.is_platform_admin:
        return RegionScope(global_=True, regions=frozenset())
    return await scope_from_roles(db, user, await granted_roles(db, user.id, app_key))


async def scope_from_roles(db: AsyncSession, user: User, granted: set[str]) -> RegionScope:
    """:func:`region_scope`, for a caller that has already read the account's roles.

    ``GET /api/shema/session`` answers ``role`` and ``regionScope`` from one account, and
    both start at the same three-table join. Without this entry point it ran twice per
    request — the defect the sibling's ``Reach`` was written to close (PR #281, review),
    arriving here by a different door because the second read is in another file.

    The admin check below repeats :func:`region_scope`'s, which is deliberate rather than
    redundant: this is a second public entry point, and one that answered a regional scope
    for an administrator because its caller happened not to check first would be a guard
    with a way around it.
    """
    if user.is_platform_admin or GLOBAL_ROLE in granted:
        return RegionScope(global_=True, regions=frozenset())

    rows = await db.execute(
        select(ShemaUserRegion.region_key).where(ShemaUserRegion.user_id == user.id)
    )
    return RegionScope(global_=False, regions=frozenset(key.value for key in rows.scalars()))


def within_scope(scope: RegionScope) -> ColumnElement[bool]:
    """The ``WHERE`` clause of the region axis, as one expression every reader shares.

    A global caller gets a literal true rather than an absent predicate, so a caller can
    compose this into any statement without branching on the scope — which is what keeps
    the branch from being rewritten slightly differently by the next reader.

    An empty, non-global scope gets a literal false: the fail-closed floor written as SQL,
    so a query cannot leak by forgetting to check the set was empty first. ``false()`` and
    not a predicate over a column — a column comparison is a filter somebody can optimise
    away on the grounds that a primary key is never null, and this one must survive that.
    """
    if scope.global_:
        return true()
    if not scope.regions:
        return false()
    return ShemaProject.region_key.in_(sorted(scope.regions))


def visible_projects(scope: RegionScope) -> Select[tuple[ShemaProject]]:
    """The projects this caller may reach, as a ``Select`` to build on.

    **Start here rather than at** ``select(ShemaProject)``. A ``LIMIT`` or an ``ORDER BY``
    layered onto this statement stays scoped, because the predicate is underneath them
    rather than beside them — which is the whole reason paging past a scope is not a thing
    a later query can do by accident.

    An aggregate is the one exception and composes :func:`within_scope` into a ``count()``
    of its own instead; ``app/services/shema/count_projects.py`` carries the reason, which
    is that a count layered onto *this* statement loses its ``FROM`` for a global caller.
    """
    return select(ShemaProject).where(within_scope(scope))


def reaches(scope: RegionScope, region_key: ShemaRegionKey | str) -> bool:
    """Whether ``region_key`` is inside ``scope`` — :func:`within_scope`'s rule, in Python.

    For the write path, which asks about a region it already holds rather than about a set
    of rows it has yet to read. Two spellings of one rule is exactly what this module is
    trying not to have, so they are adjacent and both are tested against the same cases.
    """
    if scope.global_:
        return True
    key = region_key.value if isinstance(region_key, ShemaRegionKey) else region_key
    return key in scope.regions


def refuse_out_of_scope(
    scope: RegionScope,
    *,
    user: User,
    operation: str,
    project_id: str,
) -> NotFoundError:
    """Log the refusal with enough context to investigate, and return what to raise.

    **What goes in the line, and what deliberately does not.** The caller's id, the
    operation and the regions the caller *does* hold are the account's own facts and are
    what an investigator needs to tell a misconfigured scope from a probe. ``project_id``
    is in the line because the caller supplied it — echoing back a value they already hold
    leaks nothing, and without it the event names no object and cannot be chased.

    **The target's region is not in the line, and neither is any other column of it.** That
    is precisely the fact the refusal withholds, and a log is read by more people and kept
    longer than a response body; an investigator who is allowed to know it joins it from
    the id, in a place where being allowed is checked. The same goes for the project's
    name, its location and its team — none of them appear here, and the DoD's last line is
    the reason.

    **The line records an event and not a verdict, and says so.** Its caller reaches it on
    any miss of a scoped statement, so an id that never existed arrives here exactly as an
    out-of-region one does — the indistinguishability the 404 was chosen for, felt from the
    logging side. Naming it *authorization refused* would assert a decision this function
    has no way to have made: telling the two apart takes the unscoped query the module
    deliberately does not have, and a mistyped slug counted as a refused authorization is a
    false positive on whatever reads these lines. So the message classifies the outcome it
    knows — no row, for one of two reasons — and offers the id to an investigator who may
    join it where being allowed to is checked.

    Nothing in ``extra`` discriminates the two, because nothing here can: a constant field
    saying *undetermined* on every line would carry no information the message does not.

    It returns the exception rather than raising it, so the call site reads ``raise
    refuse_out_of_scope(...)`` and mypy can see the function ends there.
    """
    logger.warning(
        "shema scoped project read found no row: out of region scope or no such id",
        extra={
            "shema_operation": operation,
            "shema_user_id": user.id,
            "shema_project_id": project_id,
            "shema_scope_global": scope.global_,
            "shema_scope_regions": sorted(scope.regions),
        },
    )
    return NotFoundError("Project not found")


def role_from(granted: set[str]) -> str | None:
    """The one ``SessionRole`` to answer for an account that may hold several.

    Widest first, off :data:`ROLE_KEYS`, whose docstring carries the argument.

    ``None`` when the account holds no Shemá role at all, which the session endpoint cannot
    see — ``require_app_access`` refuses first — but a service called from anywhere else
    can, and answering a role nobody granted is the wrong half to guess on.
    """
    return next((role for role in ROLE_KEYS if role in granted), None)
