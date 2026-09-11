"""``/api/shema/projects/{id}/health-assessments`` — the Avaliação de Saúde, and its questions.

Three routes, and each handler declares its dependencies, calls one service and returns what it
answers. No query here, no filter, no role check of its own: the caller's reach arrives as a
``RegionScope`` from ``_deps.py`` and the narrower audience question is
``app/services/shema/_health_audience.py``'s, which is ``docs/shema.md`` §6.2's first refused
temptation and [ADR 0009](../../../docs/adr/0009-routers-never-touch-the-database.md).

**The guard is a service function and not a dependency, deliberately.** Who may read a reading of
a team is one key narrower than who may open the record, and putting that in a route decorator
would make it a rule each new route has to remember — the same argument ``docs/shema.md`` §6.6
makes for the intake token and §6.4 for the consent gate. Here the rule travels with the
operation, so BE-15's panel gets it by calling the service rather than by reading this file.

**The** ``POST`` **answers the record and not the entry**, which is FE-44 §9.4's own arrow
(``-> Project``) and the right one: the flat fields, the overall reading, the history and the
derivations all move together, and a reply that carried only the new row would have the record
screen re-reading to find out what it now says. It is therefore a *coordination* surface — it
carries the true place, like the record's own read and for the same reason — and
``tests/test_shema/test_privacy_owners.py`` names it in ``COORDINATION_ROUTES`` so the exemption
is a line somebody wrote.

**No** ``If-Match``. ``app/services/shema/append_assessment.py``'s module docstring carries the
argument: appending is not replacing, two mentors filing two readings lose nothing, and a version
guard here could only refuse a reading that was taken in a conversation. The new version leaves
in the ``ETag`` anyway, because the record's flat fields did move and the screen holding the old
one has to learn so.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Header, Response, status

from app.api.shema._deps import APP_KEY, CurrentUser, Db, Scope
from app.core.exceptions import ValidationError
from app.models.shema_health import (
    ShemaHealthAssessmentSubmission,
    ShemaHealthQuestionCatalogue,
)
from app.models.shema_record import ShemaHealthAssessmentEntry, ShemaProjectRecord
from app.services.shema import append_assessment, build_record, list_assessments

router = APIRouter()

#: The header a client states its own calendar day in, shared with the record's write path.
LOCAL_DAY_HEADER = "X-Shema-Local-Date"


def _local_day(header: str | None, *, utc_today: date) -> date:
    """The day a submission with no date of its own is filed under — **the actor's**.

    The same rule ``app/api/shema/projects.py`` applies to a progress entry, for the same reason
    and with the same bound: the platform stores no timezone for an account, every real offset
    puts the local day within one of the UTC day, and a client whose clock is a year out should
    learn so rather than have a date quietly substituted. It matters a little less here than it
    does there — an assessment is not counted into an ETEN year — and it matters for the same
    kind of reason: a visit filed at 22:00 in UTC-3 belongs to today, not to tomorrow.

    The rule is stated twice in this package rather than shared, which is a real duplication and
    the smaller cost: the alternative is a second import edge into BE-06's router, and
    ``docs/shema.md`` §3.3 puts nothing shared between routers anywhere but ``_deps.py`` — where
    a function that parses a header and raises a business exception does not belong.
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


@router.get("/health-questions", response_model=ShemaHealthQuestionCatalogue)
async def read_question_sets() -> ShemaHealthQuestionCatalogue:
    """Every published set of guiding questions, and which one is current.

    **Provenance, not a rendering source.** The console renders the wizard from its own frozen
    constant and its i18next catalogue; this answers *what did set 1 ask*, which is the question
    the console stops being able to answer on the day it ships set 2 — and exactly the question
    an entry stamped ``1`` raises. ``app/models/shema_health.py``'s
    :class:`~app.models.shema_health.ShemaHealthQuestionCatalogue` carries the argument.

    No project, no id and no database: it is a module-level table, so it is the one route here
    that takes neither a scope nor a record. It is still inside the module's ``authenticated``
    router — the question set is not a secret, and a route that needs no guard is not a reason to
    open a hole in a file whose whole shape is that there are none.
    """
    return ShemaHealthQuestionCatalogue.published()


@router.get(
    "/projects/{project_id}/health-assessments",
    response_model=list[ShemaHealthAssessmentEntry],
)
async def read_assessments(
    project_id: str, db: Db, scope: Scope, user: CurrentUser
) -> list[ShemaHealthAssessmentEntry]:
    """One project's readings, oldest first — the history the trend is drawn from.

    The record already carries this list inline, and this route is the same history **behind the
    narrower gate**, for the screen whose subject is the readings. Out of region is a 404
    indistinguishable from *no such project*; outside the audience is a 403, because by then the
    only fact in the answer is the caller's own grant.
    """
    return await list_assessments(db, scope, project_id, user=user, app_key=APP_KEY)


@router.post(
    "/projects/{project_id}/health-assessments",
    response_model=ShemaProjectRecord,
    status_code=status.HTTP_201_CREATED,
)
async def file_assessment(
    project_id: str,
    payload: ShemaHealthAssessmentSubmission,
    db: Db,
    scope: Scope,
    user: CurrentUser,
    response: Response,
    local_day: Annotated[str | None, Header(alias=LOCAL_DAY_HEADER)] = None,
) -> ShemaProjectRecord:
    """File one reading: append it, re-project the record, and notify if it turned critical.

    ``201`` and not ``200``: a row is created and the history is the resource that grew. The body
    is the recomputed record all the same, for the reason FE-44 §9.3 gives the record's own save —
    the screen renders what the write actually produced, which for a backdated assessment is
    deliberately *not* the values that were just sent.
    """
    today = datetime.now(UTC).date()
    project = await append_assessment(
        db,
        scope,
        project_id,
        payload,
        user=user,
        app_key=APP_KEY,
        day=_local_day(local_day, utc_today=today),
    )
    record = await build_record(db, project, today=today)
    response.headers["ETag"] = f'"{record.version}"'
    return record
