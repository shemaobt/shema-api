"""The prayer wall and the Prayer Pulse — FE-44 §9.6's ``/prayer/requests``, and the file.

**The wall is for any Shemá role, inside its scope**, because it holds only what the teams
authorized to be shared with a network outside the organisation; the gate is the service's, and
the router hands down the scope and nothing else. The intercessor network's routes share the
``/prayer`` prefix and live in ``intercessors.py`` (BE-13, ``docs/shema.md`` §1.3 C3).

**The Pulse is ``resourceCircle``'s**, the role whose stated responsibility is sharing with the
network — the same single role the network's routes are guarded on, for the same reason: an OR
guard is the capability map ``_deps.py`` refuses. A coordinator who sends the Pulse is
granted ``resourceCircle`` beside their own role. The Pulse covers the caller's scope, so a
regional Resource Circle's file carries its own regions.

**The review queue and the release are the coordination's** (OBT-575): a sensitive project's
request waits for them before the wall and the Pulse. The routes take the caller's reader, and
the service answers who coordinates where — a role guard here would refuse the ``admin`` who
coordinates every region, and admit a coordinator to a region that is not theirs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from fastapi.responses import PlainTextResponse

from app.api.shema._deps import (
    PER_READER_CACHE_CONTROL,
    CurrentUser,
    Db,
    Reading,
    ResourceCircleUser,
    Scope,
)
from app.models.shema_prayer import (
    PrayerRelease,
    PrayerRequestEntry,
    PrayerReviewEntry,
    PulseLanguage,
)
from app.services.shema import (
    generate_prayer_pulse,
    list_prayer_requests,
    list_prayer_review,
    release_prayer_request,
)

router = APIRouter()


@router.get("/prayer/requests", response_model=list[PrayerRequestEntry])
async def read_prayer_wall(db: Db, scope: Scope, response: Response) -> list[PrayerRequestEntry]:
    """Every authorized request in the caller's reach — the gate is the service's, never ours.

    One URL answers each scope differently, so nothing between the server and the reader keeps
    it: :data:`~app.api.shema._deps.PER_READER_CACHE_CONTROL`, for the collection's reason.
    """
    response.headers["Cache-Control"] = PER_READER_CACHE_CONTROL
    return await list_prayer_requests(db, scope)


@router.get("/prayer/pulse", response_class=PlainTextResponse)
async def download_prayer_pulse(
    user: ResourceCircleUser, db: Db, scope: Scope, lang: PulseLanguage = PulseLanguage.PT_BR
) -> PlainTextResponse:
    """The Prayer Pulse as a text file — the wall inside the caller's scope, rendered.

    A ``GET``: generating changes nothing. The day is the UTC day, as every read here takes it,
    and the file is kept by nothing on its way, like the wall it is rendered from.
    """
    pulse = await generate_prayer_pulse(
        db, scope, user=user, language=lang, day=datetime.now(UTC).date()
    )
    return PlainTextResponse(
        pulse.text,
        headers={
            "Content-Disposition": f'attachment; filename="{pulse.filename}"',
            "Cache-Control": PER_READER_CACHE_CONTROL,
        },
    )


@router.get("/prayer/review", response_model=list[PrayerReviewEntry])
async def read_prayer_review(
    user: CurrentUser, db: Db, reading: Reading, response: Response
) -> list[PrayerReviewEntry]:
    """The sensitive projects' requests waiting for this coordinator's release (OBT-575)."""
    response.headers["Cache-Control"] = PER_READER_CACHE_CONTROL
    return await list_prayer_review(db, reading, user=user)


@router.post(
    "/projects/{project_id}/prayer/release",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def release_prayer(
    project_id: str, payload: PrayerRelease, user: CurrentUser, db: Db, reading: Reading
) -> Response:
    """Release one waiting request to the wall and the Pulse — as the team wrote it, or edited."""
    await release_prayer_request(db, reading, project_id, payload, user=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
