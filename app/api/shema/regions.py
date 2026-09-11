"""The org chart — FE-44 §9.10's three routes, plus the read its editor loads.

**Who may read what, stated here because the DoD asks for the rule in one place.**

``GET /regions`` takes ``CurrentUser``: any account with a Shemá grant. It is the
organisation's own directory of **offices** — which is why it is not narrowed further — and
FE-44 §5.3 gives it four consumers that all read it by reference, including the sidebar panel
that shows every region at once and the session's own name resolution. It carries a name per
seat and nothing else about a person: no contact, no country, no e-mail. Narrowing it would
make three screens ask a fourth for permission to render a label.

The other three are ``coordinator`` — *Administrador*, the role whose stated responsibility is
the region itself — and they are narrower than authentication in both directions that matter:
the trail names people who **left** a seat, and the write moves people in and out of one.

**Region scope is applied by the service and not here.** ``docs/shema.md`` §6.2 refuses a
scope the router applies by name, so these handlers declare ``Scope`` and hand the value down.
``app/api/shema/`` issues no query — ADR 0009,
``docs/adr/0009-routers-never-touch-the-database.md``.

**An unknown region key is a 422 from the path type, not a 404.** The seven keys are a public
vocabulary the console already holds (``RegionKey``), so there is no existence to protect and
nothing to be coy about — unlike a project slug, where ``_scope.py`` argues at length for the
opposite answer.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.shema._deps import CoordinatorUser, CurrentUser, Db, Scope
from app.db.models.shema_enums import ShemaRegionKey
from app.models.shema_org_chart import Region, RegionTeamSave, RegionTeamSaved, RoleChange
from app.services.shema import (
    get_region_team,
    list_regions,
    list_role_changes,
    save_region_team,
)

router = APIRouter()


@router.get("/regions", response_model=list[Region])
async def read_regions(user: CurrentUser, db: Db) -> list[Region]:
    """All seven regions and their three seats each, assigned or not.

    Twenty-one seats always: the grid is the two vocabularies and the stored rows are an
    overlay, so a region nobody has filled renders as empty rather than as absent. FE-44 §5.3
    makes that the honest wave-1 state and not a gap.
    """
    return await list_regions(db)


@router.get("/regions/role-changes", response_model=list[RoleChange])
async def read_role_changes(user: CoordinatorUser, db: Db, scope: Scope) -> list[RoleChange]:
    """The audit trail of seat changes the caller's regions cover, newest first.

    Declared **before** ``/regions/{region_key}/team`` would matter if the two could collide;
    they cannot, because that one is two segments deep. It sits here because a reader looking
    for the chart's routes should meet the trail beside the chart.
    """
    return await list_role_changes(db, scope)


@router.get("/regions/{region_key}/team", response_model=Region)
async def read_region_team(region_key: ShemaRegionKey, user: CoordinatorUser, db: Db) -> Region:
    """One region's seats, with the account behind each — what the editing screen loads.

    ``coordinator`` rather than ``CurrentUser``, which is the one place this module answers
    the same fact at two widths on purpose: the collection above serves four consumers a
    name, and this serves an editor the account behind that name. A user id is an internal
    identifier and the fewer surfaces hand one out, the fewer there are to think about.
    """
    return await get_region_team(db, region_key)


@router.put("/regions/{region_key}/team", response_model=RegionTeamSaved)
async def write_region_team(
    region_key: ShemaRegionKey,
    payload: RegionTeamSave,
    user: CoordinatorUser,
    db: Db,
    scope: Scope,
) -> RegionTeamSaved:
    """Put three names in three seats, and answer what actually moved.

    The answer is ``SaveOutcome`` and not a 204: FE-44 §9.10 requires that *a save that
    changed nothing says so*, which a status code cannot express and a screen has no other way
    to learn.
    """
    return await save_region_team(db, scope, region_key=region_key, payload=payload, actor=user)
