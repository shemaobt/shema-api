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
its records; the product has no third answer about *which records*, so nothing here offers one.
*Which fields* is a second question, and since OBT-528 it has an owner of its own: the place and
the flag are coordination's to write, and :func:`readership` below is where coordination is
decided.

**Who reads the truth is decided here too (OBT-528), in a function of its own.** GATE-04 gave
the truth of a sensitive place to coordination — ``globalStrategist``, and ``coordinator`` on a
project in a region of their scope — and the region half of that sentence is this file's.
:func:`readership` answers it from the grant and the scope a request already read, as a
:class:`Readership` the services ask per project; :func:`visible_projects` is untouched, because
who may *reach* a project and who may read its place are two different questions.

**A project membership is the second kind of reach, and it lives here for the first paragraph's
reason** (OBT-524, ``docs/shema.md`` §6.9). ``member_projects`` and ``roster_projects`` select
``ShemaProject`` too, so a query that could hand a member somebody else's project is no more a
thing a service can write by forgetting something than one that could hand a region's.

**A project the mesa's approval filed is nobody's until the Admin confirms it** (OBT-547,
``docs/shema.md`` §6.11). :func:`registered` is the predicate, and it is composed into
:func:`within_scope`, :func:`member_projects` and :func:`roster_projects` — every statement here
that hands out a project — so the collection, the counts, the record, the needs, the ETEN report,
the notification panel, the rosters and whatever export reads through the scope cannot see one,
for any reader, an installation admin included. The Admin reads them through
:func:`pending_projects` and decides them through :func:`filed_projects`, two statements of their
own that no reader of the collection composes.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Sequence
from collections.abc import Set as AbstractSet
from typing import NamedTuple

from sqlalchemy import ColumnElement, Select, and_, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_project_member import ShemaProjectMember
from app.db.models.shema_region import ShemaUserRegion
from app.models.shema_privacy import ShemaReader
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

#: The four Shemá role keys, in FE-44's own order — the four personas the console's screens
#: were drawn for, read verbatim from the frontend rather than translated (``docs/shema.md``
#: §2.3). The seed, the four role aliases and their probes read this tuple, and it is also
#: the head of :data:`ROLE_PRECEDENCE`, which is built from it rather than restating it: a
#: second tuple naming the same four keys is what would let the seed and the session
#: disagree.
ROLE_KEYS = (GLOBAL_ROLE, COORDINATOR_ROLE, OBT_LAB_ROLE, RESOURCE_CIRCLE_ROLE)

#: The Admin of OBT-522 — **one role for both apps**, seeded in ``shema`` and in
#: ``resource-request-form`` by ``20260927_shema08`` and labelled *"Admin da plataforma"*.
#: It is **not** ``users.is_platform_admin``, the Tripod installation's admin that passes every
#: guard: this is a role somebody is granted — by OBT-543's surface, in both apps. It has no seat in
#: the org chart and no region (:func:`scope_from_roles`).
ADMIN_ROLE = "admin"

#: The form's two privileged seats, spelled as the form spells them (``capabilities.ts``).
#: Held in ``resource-request-form``, either one opens the PME's door on its own — *"todos da
#: mesa vão ter conta no PME com a função já definida"*, 25/set — and neither reaches a region.
GESTOR_ROLE = "gestor"
MESA_ROLE = "mesa"

#: **A project membership, not a grant.** OBT-522 retires ``equipe`` as a form role, and since
#: OBT-524 the session answers it for an account that is a live member of at least one project
#: (``shema_project_members``, :func:`holds_membership`) — which is what lets a member with no
#: role anywhere through the PME's door. The form's own ``equipe`` grant — which
#: ``auto_approve`` hands to everybody who registers there — still does not count
#: (:data:`FORM_DOOR_ROLES`): only the PME's link does.
EQUIPE_ROLE = "equipe"

#: What the ``shema`` app seeds, and which of its grants the session counts.
SHEMA_APP_ROLES = (*ROLE_KEYS, ADMIN_ROLE)

#: Which of the form's grants the session counts. **Not** its ``admin``: every guard below the
#: door — ``AdminUser``, ``Scope``, the app gate on every other route — reads the ``shema``
#: grant, so a session answering *admin* off the form's row would name a power every admin
#: route then refuses. ``equipe`` is the form's floor and ``lider`` has no account since
#: 22/set; neither is a door.
FORM_DOOR_ROLES = (GESTOR_ROLE, MESA_ROLE)

#: The session's whole vocabulary, in the order ``roles`` is answered and ``role`` is picked.
#:
#: **The four Shemá roles come first**, widest-first as before, so every account that reached
#: the console before this list existed keeps the ``role`` it had, byte for byte — ``role`` is
#: kept on the wire only so no screen breaks during the transition, and an account holding
#: ``globalStrategist``, ``admin`` and ``gestor`` still answers ``globalStrategist``. The new
#: keys follow widest-first among themselves (Admin, Gestor, Mesa — OBT-522's hierarchy), and
#: the reserved ``equipe`` closes the list. The frontend's ``SESSION_ROLES`` is this tuple.
ROLE_PRECEDENCE = (*ROLE_KEYS, ADMIN_ROLE, GESTOR_ROLE, MESA_ROLE, EQUIPE_ROLE)

#: The roles that read the truth of a sensitive place in **every** region (OBT-528).
#: ``globalStrategist`` is GATE-04's own answer. ``admin`` is here on the issue's reading — the
#: Admin *vê tudo*, GATE of 23/set — and it is a **hypothesis to confirm with Daniel**: undoing
#: it is deleting it from this tuple. ``coordinator`` is not here because it reads the truth
#: only in its own regions (:func:`readership`).
COORDINATION_EVERYWHERE = (GLOBAL_ROLE, ADMIN_ROLE)


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
    #: The regions named in ``shema_user_regions``, for an account holding a regional role.
    #: **Empty and not global reaches nothing**, which is this module's fail-closed floor
    #: rather than an accident of the query — see :func:`region_scope`.
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
    The converse holds too: a row reaches nothing without a regional role to be the reach of
    (:func:`scope_from_roles`), so the ``admin`` role gains no region by holding one.
    """
    if user.is_platform_admin:
        return RegionScope(global_=True, regions=frozenset())
    return await scope_from_roles(db, user, await granted_roles(db, user.id, app_key))


async def scope_from_roles(db: AsyncSession, user: User, granted: AbstractSet[str]) -> RegionScope:
    """:func:`region_scope`, for a caller that has already read the account's roles.

    ``GET /api/shema/session`` answers ``role`` and ``regionScope`` from one account, and
    both start at the same three-table join. Without this entry point it ran twice per
    request — the defect the sibling's ``Reach`` was written to close (PR #281, review),
    arriving here by a different door because the second read is in another file.

    The admin check below repeats :func:`region_scope`'s, which is deliberate rather than
    redundant: this is a second public entry point, and one that answered a regional scope
    for an administrator because its caller happened not to check first would be a guard
    with a way around it.

    **A region row is the reach of a regional role, and of nothing else** (OBT-523). An
    account holding no regional role reaches nothing whatever rows it has — without reading
    the table. That is what keeps ``admin``, ``gestor`` and ``mesa`` out of the region axis as
    a property rather than an accident of data: nothing deletes an account's rows when its
    regional role is revoked, and an org-chart seat or an operator can leave one behind. For
    the three regional roles nothing changes.
    """
    if user.is_platform_admin or GLOBAL_ROLE in granted:
        return RegionScope(global_=True, regions=frozenset())
    if not any(role in granted for role in REGIONAL_ROLES):
        return RegionScope(global_=False, regions=frozenset())

    rows = await db.execute(
        select(ShemaUserRegion.region_key).where(ShemaUserRegion.user_id == user.id)
    )
    return RegionScope(global_=False, regions=frozenset(key.value for key in rows.scalars()))


async def holders_reaching(
    db: AsyncSession, users: Sequence[User], region_key: ShemaRegionKey, app_key: str
) -> list[User]:
    """Which of ``users`` reach ``region_key`` — the scope asked about a list of people.

    :func:`region_scope` answers *how far does this caller reach* and every read in the module
    starts there. Addressing a notice asks the same question from the other end, about a list
    of accounts that :func:`~app.services.authorization.list_role_holders` just answered — and
    it belongs here for that function's own stated reason: the rule about what a region grant
    means has one owner, and a second file deciding that *no rows means nothing unless you are
    ``globalStrategist``* is a second place for a fail-open to be introduced.

    **Two queries for a list rather than two per person.** The roles of every holder and the
    regions of every holder are each one read; the per-user loop underneath them is
    arithmetic. A routing path called inside a save is not the place to issue a join per
    recipient.

    Order is preserved, because the caller's order is ``list_role_holders``'s — by e-mail, so
    a recipient list is stable between calls and a test can assert one.

    **Precondition: ``users`` hold a regional or the global role.** :func:`scope_from_roles`
    refuses a region row to an account with no regional role; this function does not re-read
    roles to say the same, because every caller passes holders of named regional roles
    (``_needs.py``'s ``URGENT_NEED_ROLES``) and a second read per list is the cost it exists
    to avoid.
    """
    if not users:
        return []

    globals_ = {
        user.id
        for user in await authorization_service.list_role_holders(db, app_key, (GLOBAL_ROLE,))
    }
    rows = await db.execute(
        select(ShemaUserRegion.user_id, ShemaUserRegion.region_key).where(
            ShemaUserRegion.user_id.in_([user.id for user in users])
        )
    )
    granted: dict[str, set[str]] = {}
    for user_id, key in rows:
        granted.setdefault(user_id, set()).add(key.value)

    return [
        user
        for user in users
        if user.is_platform_admin
        or user.id in globals_
        or region_key.value in granted.get(user.id, set())
    ]


async def scopes_for(
    db: AsyncSession, users: Sequence[User], *, unscoped: Collection[str]
) -> dict[str, RegionScope]:
    """:func:`scope_from_roles` for a whole list of accounts, in **one** read of the region table.

    The singular is written for the caller standing in front of one account. Addressing a
    notification asks the same question about everybody who holds a role, and asking it one at a
    time is two round trips per person on a write a mentor is waiting in front of — the defect
    ``app/services/resource_request/_notices.py``'s ``board_watchers`` avoids on the other axis by
    reading the holders once and filtering in Python. This is that shape for the region axis: the
    rows are read for the whole list and each account's reach is resolved off them, so the cost is
    one query rather than *n*.

    ``unscoped`` is the ids of the accounts whose **role** already reaches every region — the
    :data:`GLOBAL_ROLE` holders — and it is a parameter rather than a read because
    ``docs/shema.md`` §2.4 gives ``user_app_roles`` to the auth spine: the caller asks
    ``list_role_holders`` once for the whole list, which is the same one-query trade this function
    makes for the table it does own. A platform admin is global here as they are everywhere else.

    Every account in ``users`` gets an entry, including the ones with no row at all: the
    fail-closed floor of :func:`region_scope` is an empty, non-global scope and not a missing key,
    so a caller cannot read *reaches nothing* as *not answered*.

    Same precondition as :func:`holders_reaching`: ``users`` hold a regional or the global role
    (``_health_audience.py``'s ``HEALTH_AUDIENCE``), which is why a row here is read as reach.
    """
    by_user: dict[str, set[str]] = {}
    if users:
        rows = await db.execute(
            select(ShemaUserRegion.user_id, ShemaUserRegion.region_key).where(
                ShemaUserRegion.user_id.in_([user.id for user in users])
            )
        )
        for user_id, region_key in rows:
            by_user.setdefault(user_id, set()).add(region_key.value)

    return {
        user.id: (
            RegionScope(global_=True, regions=frozenset())
            if user.is_platform_admin or user.id in unscoped
            else RegionScope(global_=False, regions=frozenset(by_user.get(user.id, ())))
        )
        for user in users
    }


def registered() -> ColumnElement[bool]:
    """The projects that are records — every row but one the Admin has not confirmed (OBT-547).

    A project the mesa's approval filed waits in ``pending_confirmation`` until the Admin
    confirms it, and a discarded one waits there for good. Composed into every statement below
    that hands out a project, so the exclusion is a property of the scope rather than of each
    reader — the export a later issue writes inherits it by starting where every reader starts.
    """
    return ShemaProject.pending_confirmation.is_(False)


def within_scope(scope: RegionScope) -> ColumnElement[bool]:
    """The ``WHERE`` clause of the region axis, as one expression every reader shares.

    A global caller gets :func:`registered` alone rather than an absent predicate, so a caller
    can compose this into any statement without branching on the scope — which is what keeps
    the branch from being rewritten slightly differently by the next reader.

    An empty, non-global scope gets a literal false: the fail-closed floor written as SQL,
    so a query cannot leak by forgetting to check the set was empty first. ``false()`` and
    not a predicate over a column — a column comparison is a filter somebody can optimise
    away on the grounds that a primary key is never null, and this one must survive that.
    """
    if scope.global_:
        return registered()
    if not scope.regions:
        return false()
    return and_(registered(), ShemaProject.region_key.in_(sorted(scope.regions)))


def visible_projects(scope: RegionScope) -> Select[tuple[ShemaProject]]:
    """The projects this caller may reach, as a ``Select`` to build on.

    **Start here rather than at** ``select(ShemaProject)``. A ``LIMIT`` or an ``ORDER BY``
    layered onto this statement stays scoped, because the predicate is underneath them
    rather than beside them — which is the whole reason paging past a scope is not a thing
    a later query can do by accident.

    An aggregate is the one exception and composes :func:`within_scope` into a ``count()``
    of its own instead; ``app/services/shema/count_projects.py`` carries the reason, which
    is that a count layered onto *this* statement lost its ``FROM`` for a global caller while
    that caller's predicate named no column.
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


class Readership(NamedTuple):
    """Where a caller reads the truth of a sensitive place — OBT-528's reader, by region.

    Carried as a :class:`RegionScope` because the question is the scope's own shape — *does
    this reach that region* — and :func:`reaches` is the one spelling of it. It is **not** the
    caller's scope: every project a caller reaches is read, and this says in which of them the
    place is read as it is.

    Region rows are per account and not per role (``shema_user_regions``), so an account holding
    ``coordinator`` and ``obtLab`` is coordination in every region it reaches. The org chart is
    not consulted: a seat names who holds a role, and the grant is what the guards read.

    **It also carries the prayer request's reader (BE-09)**, because the record read and its write
    are the two places that ask and both already take this value. Who reads a request nobody
    authorized is ``_consent.py``'s rule; ``app/api/shema/_deps.py`` asks it and sets the bit here.
    """

    #: The regions this caller coordinates: all of them, their own, or none.
    coordination: RegionScope
    #: Whether this caller reads a prayer request that has not been authorized to leave
    #: coordination — ``_consent.reads_withheld_requests``. ``False`` unless somebody said so.
    withheld_prayer: bool = False

    def reader_of(self, region_key: ShemaRegionKey | str) -> ShemaReader:
        """``coordination`` for a project in a region this caller coordinates, ``other`` else."""
        if reaches(self.coordination, region_key):
            return ShemaReader.COORDINATION
        return ShemaReader.OTHER

    @property
    def coordinates_anything(self) -> bool:
        """Whether this caller coordinates any region — who a notice about a collection is for."""
        return self.coordination.global_ or bool(self.coordination.regions)


#: A readership that coordinates nothing: every project reads as ``other``. For a caller that
#: builds cards and never shows their place — the notification panel's stale reading, whose
#: entries are an output path.
NO_COORDINATION = Readership(coordination=RegionScope(global_=False, regions=frozenset()))


def readership(
    scope: RegionScope, granted: AbstractSet[str], *, platform_admin: bool
) -> Readership:
    """Where this caller reads the truth, from the grant and the scope already read.

    No query of its own: the caller has already resolved both, once per request
    (``app/api/shema/_deps.py``), and a second read of one fact is the defect
    :func:`scope_from_roles` was written to close.

    * An installation admin, a ``globalStrategist`` and — the hypothesis in
      :data:`COORDINATION_EVERYWHERE` — an ``admin`` coordinate every region: an installation
      admin passes every guard in this repository, and reading less than the guards let it
      reach would be a stricter rule on one route than on the route beside it.
    * A ``coordinator`` coordinates the regions of its own scope — GATE-04's *cada um na sua
      região*.
    * Everybody else coordinates nothing, which is the fail-closed floor: a reader nobody named
      reads the region.
    """
    if platform_admin or any(role in granted for role in COORDINATION_EVERYWHERE):
        return Readership(coordination=RegionScope(global_=True, regions=frozenset()))
    if COORDINATOR_ROLE in granted:
        return Readership(coordination=scope)
    return NO_COORDINATION


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


async def session_roles(
    db: AsyncSession, user_id: str, *, app_key: str, form_app_key: str
) -> tuple[str, ...]:
    """The roles ``GET /api/shema/session`` answers, from **one** read of both apps' grants.

    ``list_roles`` asked without an app key answers every live grant the account holds, so
    the door and the body of the session are one query rather than one per app — and, being
    the same value, they cannot disagree about who got in. Each grant counts only from the
    app it belongs to: :data:`SHEMA_APP_ROLES` from ``app_key`` and :data:`FORM_DOOR_ROLES`
    from ``form_app_key``. A key another product happens to share — six of them seed an
    ``admin`` — is somebody else's role and never reaches this list.

    **And one read of the memberships** (OBT-524): a live row in ``shema_project_members``
    adds :data:`EQUIPE_ROLE`, which is how a project member holding no grant at all passes the
    door to the two reads a member has. It is not a grant and ``list_roles`` does not see it,
    so it is a second query — but still one per request, whichever of the door's routes asked.

    Read fresh, like :func:`granted_roles`, and for the same half: the session is asked once
    per sign-in and decides what the console believes it may show.
    """
    counted = {app_key: SHEMA_APP_ROLES, form_app_key: FORM_DOOR_ROLES}
    pairs = await authorization_service.list_roles(db, user_id)
    held = {role for app, role in pairs if role in counted.get(app, ())}
    if await holds_membership(db, user_id):
        held.add(EQUIPE_ROLE)
    return roles_from(held)


def roles_from(granted: AbstractSet[str]) -> tuple[str, ...]:
    """Every key of :data:`ROLE_PRECEDENCE` in ``granted``, in that order.

    A set and not a sequence on purpose: a ``str`` is a sequence of strings, and a caller that
    passed an app key by mistake would get the letters of ``"shema"`` checked one by one.
    """
    return tuple(role for role in ROLE_PRECEDENCE if role in granted)


def role_from(granted: AbstractSet[str]) -> str | None:
    """The one role the session still answers beside the list — **transitional** (OBT-523).

    The first of :func:`roles_from`: :data:`ROLE_PRECEDENCE` carries why the four Shemá roles
    lead. ``None`` when the account holds none of the vocabulary, which the session endpoint
    only answers to an installation admin with no grant — the door refuses everybody else
    first — and answering a role nobody granted is the wrong half to guess on.
    """
    return next(iter(roles_from(granted)), None)


# --- the member's reach (OBT-524) -------------------------------------------------------------


def live_membership_ids(user_id: str) -> Select[tuple[str]]:
    """The ids of the projects ``user_id`` is a live member of — the one statement of *live*.

    Public because the resource-request form reads the same fact (BE-19, OBT-520): a live
    member of a project is its team there, and ``resource_request/_membership.py`` filters and
    checks by this statement instead of keeping a second ``removed_at IS NULL`` beside it.
    """
    return select(ShemaProjectMember.project_id).where(
        ShemaProjectMember.user_id == user_id,
        ShemaProjectMember.removed_at.is_(None),
    )


async def holds_membership(db: AsyncSession, user_id: str) -> bool:
    """Whether ``user_id`` is a live member of any project — the session's :data:`EQUIPE_ROLE`."""
    found = await db.execute(live_membership_ids(user_id).limit(1))
    return found.scalar_one_or_none() is not None


def member_projects(user_id: str) -> Select[tuple[ShemaProject]]:
    """The projects ``user_id`` is a live member of — what ``GET /api/shema/me/projects`` lists.

    **A membership is not a region, and nothing here composes it into**
    :func:`visible_projects`. A member reaches their projects' ids and names and their rosters;
    the collection, the counts and the record stay where the region scope puts them, so a member
    with no regional role reaches no other project — OBT-524's DoD, as a property of there being
    no statement that could. What else a member is shown of their own project is OBT-544's to
    decide, and composing this statement is how it would.
    """
    return select(ShemaProject).where(
        registered(), ShemaProject.id.in_(live_membership_ids(user_id))
    )


class RosterReach(NamedTuple):
    """How far a caller reaches over the projects' **rosters** — a type of its own, on purpose.

    Three readers and no fourth: the caller's region ``scope``, their own live memberships, and
    the Admin, who reaches every roster. Membership is the Admin's to write (OBT-522, *só o admin
    escreve*), and the Admin reaches no region (OBT-523): confined to the regions it holds, the one
    role that writes rosters could write none.

    **Not a** :class:`RegionScope`, and that is the guard. A global ``RegionScope`` handed to the
    Admin would be one wrong annotation away from ``visible_projects``, ``read_record`` or
    ``browse_projects`` — the whole collection and every record for an account that reaches no
    region. A ``RosterReach`` cannot be passed to any of them, and mypy says so.
    """

    #: The caller's region scope, exactly as :func:`scope_from_roles` answered it.
    scope: RegionScope
    #: Whether the caller holds ``admin`` in ``shema`` — every roster, and nothing more.
    admin: bool


def roster_projects(reach: RosterReach, user_id: str) -> Select[tuple[ShemaProject]]:
    """The projects whose members this caller may read — or, for the Admin, write.

    Whoever the scope reaches, plus the projects ``user_id`` is a live member of, plus every
    project for the Admin — every :func:`registered` one: a roster written on a project nobody
    confirmed would be a membership reaching a project nobody may see. A project outside all
    three is absent, and its callers refuse it as :func:`refuse_out_of_scope` does — the same
    404 an id that does not exist gets.
    """
    if reach.admin:
        return select(ShemaProject).where(registered())
    return select(ShemaProject).where(
        registered(),
        or_(within_scope(reach.scope), ShemaProject.id.in_(live_membership_ids(user_id))),
    )


# --- the projects the mesa's approval filed (OBT-547) ------------------------------------------


def filed_projects() -> Select[tuple[ShemaProject]]:
    """Every project an approval filed, whatever became of it — what the Admin decides on.

    Confirmed, pending and discarded alike, so the Admin's two acts can tell *already decided*
    (409) from *no such project* (404). The Admin alone reaches it, behind ``AdminUser``, and no
    reader of the collection composes it.
    """
    return select(ShemaProject).where(ShemaProject.source_request_id.is_not(None))


def pending_projects() -> Select[tuple[ShemaProject]]:
    """The projects waiting for the Admin — filed, not confirmed and not discarded."""
    return filed_projects().where(
        ShemaProject.pending_confirmation.is_(True), ShemaProject.discarded_at.is_(None)
    )


def live_project_of_link(link_id: str) -> Select[tuple[ShemaProject]]:
    """The project a link already filed and nobody discarded — pending or confirmed.

    One per link, by ``uq_shema_projects_live_source_link``: a second request of the same team
    approved later must not file the team twice.
    """
    return filed_projects().where(
        ShemaProject.source_link_id == link_id, ShemaProject.discarded_at.is_(None)
    )
