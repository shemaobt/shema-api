"""The Rhythm's log - FE-44 §9.7's three routes on it, and not the fourth.

Each handler declares its dependencies, calls one service and returns what it answers: no query,
no filter, no role check of its own. The caller's reach arrives as a ``RegionScope`` from
``_deps.py``, and *who may read and write the log* is ``app/services/shema/_meeting_log.py``'s -
a service rule rather than a route condition, so the next caller of the services inherits it
(``docs/shema.md`` §6.2, ADR 0009).

**``GET /api/shema/meetings`` is not built, and that is a decision.** FE-44 §9.0 forbids an
endpoint that serves a vocabulary the console already holds, and made the definitions the one
exception only while GATE-02 might have answered *per region*. It answered *global*, and OBT-399
records the consequence in so many words: ``RITMO_MEETINGS`` stays the source on the console.
The server keeps only the cadence it derives periods from (``app/utils/shema_meetings.py``).

**The write answers 201 when it created the period's entry and 200 when it replaced one**, so
*a second log replaces the first* is visible on the wire rather than only in the table.

``response_model=None`` on the ``DELETE`` is not decoration: under ``from __future__ import
annotations`` a ``-> None`` reaches FastAPI as a string, and the route would then assert that a
204 must not carry a body. ``app/api/shema/intercessors.py`` carries the same line.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Response, status

from app.api.shema._deps import APP_KEY, CurrentUser, Db, Scope
from app.models.shema_meeting import (
    MeetingLogCreate,
    MeetingLogEntry,
    MeetingScopeKey,
    ShemaMeetingId,
)
from app.services.shema import list_meeting_log, log_meeting, undo_meeting

router = APIRouter()

_LOG = "/meetings/log"


@router.get(_LOG, response_model=list[MeetingLogEntry])
async def read_meeting_log(db: Db, scope: Scope, user: CurrentUser) -> list[MeetingLogEntry]:
    """Every entry the caller's regions cover - the console hydrates ``rhythmStore`` from it."""
    return await list_meeting_log(db, scope, reader=user, app_key=APP_KEY)


@router.post(
    _LOG,
    response_model=MeetingLogEntry,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_200_OK: {"description": "The period's entry was replaced"}},
)
async def write_meeting_log(
    payload: MeetingLogCreate, db: Db, scope: Scope, user: CurrentUser, response: Response
) -> MeetingLogEntry:
    """Log a meeting; the server derives the period, and a second log of it replaces the first.

    The day it is checked against is the UTC day, named here and injected, so the service is a
    function of it and a test can move the calendar.
    """
    logged = await log_meeting(
        db, scope, payload, actor=user, app_key=APP_KEY, today=datetime.now(UTC).date()
    )
    if logged.replaced:
        response.status_code = status.HTTP_200_OK
    return logged.entry


@router.delete(
    _LOG + "/{meeting_id}/{scope_key}/{period}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def remove_meeting_log(
    meeting_id: ShemaMeetingId,
    scope_key: MeetingScopeKey,
    period: str,
    db: Db,
    scope: Scope,
    user: CurrentUser,
) -> None:
    """Undo one period's entry - the period the server returned when it was logged."""
    await undo_meeting(db, scope, meeting_id, scope_key, period, actor=user, app_key=APP_KEY)
