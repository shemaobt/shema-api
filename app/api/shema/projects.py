"""``GET /api/shema/projects`` — the Projetos screen, and the Início band behind it.

The handler declares its dependencies, calls one service and returns what it answers. There is
no query here, no filter and no ``WHERE``: the caller's reach arrives as a ``RegionScope`` from
``_deps.py`` and is handed straight down, which is ``docs/shema.md`` §6.2's first refused
temptation and [ADR 0009](../../../docs/adr/0009-routers-never-touch-the-database.md).

**One endpoint, and it takes the filter and the counts together.** FE-44 §9.1 froze this route
as the whole scoped collection — no pagination, no filter parameters, no facet counts — and
named the one shape the server may take when that stops being enough: *the filter **and** the
counts together, in one endpoint, never the filter alone*. A filtered list whose counts are
computed somewhere else is the second owner that note exists to prevent. This issue's DoD asks
for that shape now rather than at the two-thousandth project, so it is built as §9.1 describes
it: the counts are not optional, there is no parameter that suppresses them, and a request with
no parameters still answers the whole scoped collection. What changed against the frozen
contract is the envelope — ``Project[]`` became ``{items, counts, …}`` — and the PR says so.

**No** ``/indicators`` **route, and that is a decision** (FE-44 §9.2). The Início screen's six
indicators are this response with six sets of filters, so the count a card shows is *by
construction* what its link returns. A second endpoint would be a second owner of that
relation, and the relation is the whole value.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.shema._deps import Db, Scope
from app.models.shema_projects import ProjectQuery, ShemaProjectPage
from app.services.shema import browse_projects

router = APIRouter()


@router.get("/projects", response_model=ShemaProjectPage)
async def list_projects(db: Db, scope: Scope, query: ProjectQuery) -> ShemaProjectPage:
    """Every project the caller's role and region allow, filtered, counted, ordered and paged.

    **The day is read here and injected**, so that everything below is a pure function of it —
    which is what the parity replay pins and what lets a test move the calendar. It is the UTC
    day, named rather than taken from the machine's ambient locale, and the cost is stated
    because it is real: a coordinator in UTC-3 asking at 22:00 is answered against tomorrow's
    date, which can move a project across the 60- or 120-day staleness line one day early.
    ``docs/shema.md`` §6.5's local-day rule is about the **write** stamp, where the actor's own
    day is knowable and matters to the year an ETEN credit falls in; a read has no actor's
    timezone to consult and inventing a parameter for one would be an API surface serving a
    one-day edge on a threshold measured in months.
    """
    return await browse_projects(db, scope, query, today=datetime.now(UTC).date())
