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

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Header, Response, status
from fastapi.responses import JSONResponse

from app.api.shema._deps import CurrentUser, Db, Scope
from app.core.exceptions import ERROR_CODE_CONFLICT, ValidationError
from app.models.shema import ShemaProjectCreate, ShemaProjectUpdate
from app.models.shema_projects import ProjectQuery, ShemaProjectPage
from app.models.shema_record import ShemaProjectRecord
from app.services.shema import (
    RecordVersionConflict,
    browse_projects,
    build_record,
    create_project,
    read_record,
    save_project,
)

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


#: The header a client states its own calendar day in — see :func:`_local_day`.
LOCAL_DAY_HEADER = "X-Shema-Local-Date"

#: What ``If-Match`` is for, in the one place OpenAPI will show it.
_IF_MATCH = (
    "The version this record was read at, from the ETag of the read. Required: a save that "
    "cannot say which version it is replacing has no basis for replacing one."
)


def _etag(version: int) -> str:
    """The record's version as an entity tag — what a client sends back in ``If-Match``.

    A **strong** tag, because it is not a digest of the bytes but the record's own counter: two
    responses carrying the same version are the same record, which is what strong comparison
    means. Quoted, because the header's grammar says so.
    """
    return f'"{version}"'


def _expected_version(if_match: str) -> int:
    """The version the caller believes it is saving over.

    **The header is required**, which is the one place this module departs from
    ``app/api/sound_necklace/sessions.py``'s otherwise identical shape. There the writer is a
    single tab autosaving its own session and an unconditional write is what it wants; here
    several coordinators edit one record in one meeting, and a guard that can be skipped is
    last-write-wins one forgotten header away. ``app/services/shema/save_project.py`` carries
    the argument; FastAPI's own 422 is what a client that omits it meets, naming the header.

    ``*`` — *any current version* — is refused with everything else that is not a number, and
    for the same reason the header is required: it is the spelling of *I do not know what I am
    overwriting*.
    """
    tag = if_match.strip().removeprefix("W/").strip().strip('"')
    if not tag.isdigit():
        raise ValidationError(f"If-Match: {if_match!r} is not a version this record has had")
    return int(tag)


def _local_day(header: str | None, *, utc_today: date) -> date:
    """The day a progress entry is stamped with — **the actor's**, not the server's.

    FE-44 §7.2 requires the coordinator's local day and gives the reason in a sentence: in
    UTC-3 a save after 21:00 lands on tomorrow's UTC date, and on 31 December in the next
    *year*, which is exactly the boundary the ETEN report reconstructs a credit from. The
    platform stores no timezone for an account, so the day is the client's to state and
    ``toLocalIsoDate`` on the other side is what states it.

    **Bounded to one day either side of the server's own**, which is what keeps a
    client-supplied date from being a backdating tool: every real offset, UTC-12 to UTC+14,
    puts the local day within one of the UTC day, and moving a credit into a closed year needs
    more than one. Outside the window it is refused rather than ignored — a client whose clock
    is a year out should learn so, and quietly substituting the UTC day would file the entry on
    a date nobody chose.

    Absent, it is the UTC day, with the cost stated rather than hidden: a coordinator in UTC-3
    saving at 22:00 has the entry filed on tomorrow. That is the same trade
    :func:`list_projects` names for the read, and it is why the header exists at all.
    """
    if header is None:
        return utc_today
    try:
        stated = date.fromisoformat(header.strip())
    except ValueError:
        raise ValidationError(f"{LOCAL_DAY_HEADER}: {header!r} is not a YYYY-MM-DD day") from None
    if abs((stated - utc_today).days) > 1:
        raise ValidationError(
            f"{LOCAL_DAY_HEADER}: {stated.isoformat()} is not a day any timezone is on today"
        )
    return stated


def _conflict(exc: RecordVersionConflict) -> JSONResponse:
    """The 409 a screen can explain itself with — the DoD's second line, on the wire.

    The envelope is the repository's own, ``detail`` and ``code``, with four keys beside it:
    *you are stale* is a sentence a screen can only answer with a reload, while *Maria changed
    the status comments and the translated units at 14:02* is one a coordinator can act on.
    ``changedFields`` are wire keys, so the console looks them up where it looks up its labels,
    and the ``ETag`` is the version to retry against without a second request to find it.

    A ``JSONResponse`` built here rather than an exception handler registered globally, because
    the extra keys are this module's and a handler in ``app/core/exceptions.py`` would put a
    Shemá shape on an envelope eight applications share. ``app/api/sound_necklace/sessions.py``
    does the same thing for the same reason.
    """
    changes = exc.changes
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        headers={"ETag": _etag(changes.version)},
        content={
            "detail": str(exc),
            "code": ERROR_CODE_CONFLICT,
            "expectedVersion": exc.expected,
            "currentVersion": changes.version,
            "changedFields": list(changes.fields),
            "changedBy": changes.by,
            "changedAt": None if changes.at is None else changes.at.isoformat(),
        },
    )


def _with_etag(record: ShemaProjectRecord, response: Response) -> ShemaProjectRecord:
    """Hand the record's version back in the header, since it is not in the body.

    ``version`` is not one of FE-44's 73 keys and a 74th added to a frozen shape is how a
    contract stops being one — so the value the next save has to quote travels where HTTP
    already keeps it.
    """
    response.headers["ETag"] = _etag(record.version)
    return record


@router.get("/projects/{project_id}", response_model=ShemaProjectRecord)
async def read_project(
    project_id: str, db: Db, scope: Scope, user: CurrentUser, response: Response
) -> ShemaProjectRecord:
    """One record, whole — what the ficha's ten tabs read, and the version its saves quote.

    **This read carries the true location**, and it is the only one in the module that does:
    FE-44 §9.0 states the split in a line — *the project read itself carries the true location,
    it is a coordination surface* — and §8.1 rule 5 gives the reason, which is that hiding the
    country from the record's own author is data loss rather than privacy. The shape therefore
    does not inherit ``LeavingShape``, and ``tests/test_shema/test_privacy_owners.py`` carries
    this route in ``COORDINATION_ROUTES`` so the exemption is a line somebody wrote.

    A project outside the caller's region is refused exactly as one that does not exist is —
    the two are indistinguishable on the wire on purpose (``app/services/shema/_scope.py``),
    and the log is what tells them apart for whoever has to investigate.
    """
    record = await read_record(db, scope, project_id, user=user, today=datetime.now(UTC).date())
    return _with_etag(record, response)


@router.post("/projects", response_model=ShemaProjectRecord, status_code=status.HTTP_201_CREATED)
async def create_record(
    payload: ShemaProjectCreate,
    db: Db,
    scope: Scope,
    user: CurrentUser,
    response: Response,
    local_day: Annotated[str | None, Header(alias=LOCAL_DAY_HEADER)] = None,
) -> ShemaProjectRecord:
    """File a new record at the slug the client minted — ``projectsStore.saveProject``'s half.

    No ``If-Match``: there is no version to be stale against. What this write owns instead is
    the collision, and a slug that already exists is a 409 naming it rather than a silent
    overwrite of somebody else's record.
    """
    today = datetime.now(UTC).date()
    project = await create_project(
        db, scope, payload, user=user, day=_local_day(local_day, utc_today=today)
    )
    return _with_etag(await build_record(db, project, today=today), response)


@router.patch(
    "/projects/{project_id}",
    response_model=ShemaProjectRecord,
    responses={status.HTTP_409_CONFLICT: {"description": "The record moved since it was read"}},
)
async def patch_record(
    project_id: str,
    payload: ShemaProjectUpdate,
    db: Db,
    scope: Scope,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match", description=_IF_MATCH)],
    local_day: Annotated[str | None, Header(alias=LOCAL_DAY_HEADER)] = None,
) -> ShemaProjectRecord | JSONResponse:
    """Save one tab's worth of a record, and refuse a save that is standing on old ground.

    **The body is whatever the tab owns and nothing else.** Ten tabs saving the whole record
    would have tab 3 writing tab 7's values as they stood when tab 3 was opened — a silent
    overwrite inside one person's own payload, which no version guard between people can catch.
    Absent means unchanged, all the way down.

    The response is the **recomputed** record, including any progress history entry the save
    produced, because FE-44 §9.3 asks for exactly that: the record screen renders what the save
    actually wrote, not what it sent.
    """
    today = datetime.now(UTC).date()
    try:
        project = await save_project(
            db,
            scope,
            project_id,
            payload,
            user=user,
            expected_version=_expected_version(if_match),
            day=_local_day(local_day, utc_today=today),
        )
    except RecordVersionConflict as conflict:
        return _conflict(conflict)
    return _with_etag(await build_record(db, project, today=today), response)
