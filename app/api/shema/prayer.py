"""The prayer wall and the Prayer Pulse — FE-44 §9.6's ``/prayer/requests``, and the file.

**The wall is for any Shemá role, inside its scope**, because it holds only what the teams
authorized to be shared with a network outside the organisation; the gate is the service's, and
the router hands down the scope and nothing else. The intercessor network's routes share the
``/prayer`` prefix and live in ``intercessors.py`` (BE-13, ``docs/shema.md`` §1.3 C3).

**The Pulse is ``resourceCircle``'s**, the role whose stated responsibility is sharing with the
network — the same single role the network's routes are guarded on, for the same reason: an OR
guard is the capability map ``_deps.py`` refuses. A global strategist who sends the Pulse is
granted ``resourceCircle`` beside their own role. The Pulse covers the caller's scope, so a
regional Resource Circle's file carries its own regions.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from app.api.shema._deps import Db, ResourceCircleUser, Scope
from app.models.shema_prayer import PrayerRequestEntry, PulseLanguage
from app.services.shema import generate_prayer_pulse, list_prayer_requests

router = APIRouter()

#: Nothing between the server and the reader keeps either answer: the wall differs per scope, and
#: a Pulse is a file that is not meant to exist anywhere the network did not receive it.
NO_STORE = "private, no-store"


@router.get("/prayer/requests", response_model=list[PrayerRequestEntry])
async def read_prayer_wall(db: Db, scope: Scope, response: Response) -> list[PrayerRequestEntry]:
    """Every authorized request in the caller's reach — the consent gate applied by the query."""
    response.headers["Cache-Control"] = NO_STORE
    return await list_prayer_requests(db, scope)


@router.get("/prayer/pulse", response_class=PlainTextResponse)
async def download_prayer_pulse(
    user: ResourceCircleUser, db: Db, scope: Scope, lang: PulseLanguage = PulseLanguage.PT_BR
) -> PlainTextResponse:
    """The Prayer Pulse as a text file — the wall inside the caller's scope, rendered.

    A ``GET``: generating changes nothing. The day is the UTC day, as every read here takes it.
    """
    pulse = await generate_prayer_pulse(
        db, scope, user=user, language=lang, day=datetime.now(UTC).date()
    )
    return PlainTextResponse(
        pulse.text,
        headers={
            "Content-Disposition": f'attachment; filename="{pulse.filename}"',
            "Cache-Control": NO_STORE,
        },
    )
