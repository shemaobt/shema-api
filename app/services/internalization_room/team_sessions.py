"""The Desk's third column: one card per conversation a team held (RF-06).

The cards are built here rather than on the response model, which is where the devices
panel builds its rows. The reason is the import direction and nothing else: naming a bead
needs `canon.labels`, and `canon.labels` already imports the models, so a
`TeamSessionResponse.of` would close a cycle.

**Every moment leaves here saying which clock it is on**, and this is where that is done
rather than in a validator on the model — `app/models/` takes its vocabulary from
`app/core/` and `app/db/models/` and reaches into no service, which the five other response
modules keep. `DateTime(timezone=True)` hands back a naive value on SQLite and an aware one
on Postgres, off one schema and one writer; a naive one serialises bare, and whoever receives
a `20:00:56` with nothing after it reads it as local. `end_of` normalises the end it answers;
the start is normalised here beside it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.models.internalization_room import SessionBead, TeamSessionResponse
from app.services.internalization_room.canon.labels import labelled_elements
from app.services.internalization_room.coverage import CoverageStatus, is_panorama
from app.services.internalization_room.coverage_events import necklaces_of
from app.services.internalization_room.session_end import as_utc, end_of


async def list_team_sessions(db: AsyncSession, project_id: str) -> list[TeamSessionResponse]:
    """A team's history, newest first, each card carrying the necklace it left behind.

    Ordering is the server's: RF-06 reads a history from the most recent conversation
    backwards, and a client that re-sorted what it was handed would be a second place
    deciding it. The id breaks a tie — two sessions opened in the same second are ordinary
    on a schema whose clock is the database's, and a list route that answers a different
    order each time it is asked is a list route nobody can test.

    One statement for the rows and one for every portrait on them. A query per card is what
    this service has already had to take back out once.
    """
    sessions = await _history_of(db, project_id)
    portraits = await necklaces_of(db, sessions)
    now = datetime.now(UTC)
    return [_card(session, portraits[session.id], at=now) for session in sessions]


async def _history_of(db: AsyncSession, project_id: str) -> Sequence[IRSession]:
    result = await db.execute(
        select(IRSession)
        .where(IRSession.project_id == project_id)
        .order_by(IRSession.created_at.desc(), IRSession.id.desc())
    )
    return result.scalars().all()


def _card(session: IRSession, portrait: dict[str, str], *, at: datetime) -> TeamSessionResponse:
    end = end_of(session, at=at)
    return TeamSessionResponse(
        session_id=session.id,
        pericope=session.pericope,
        started_at=as_utc(session.created_at),
        ended_at=end.ended_at,
        duration_minutes=end.duration_minutes,
        state=end.state,
        coverage=_portrait(session.pericope, portrait),
    )


def _portrait(pericope: str, standing: dict[str, str]) -> list[SessionBead]:
    """The beads in the order the necklace strings them, so the two drawings agree.

    A panorama addresses the book rather than a passage and has no spine at all. It is
    answered with nothing rather than dropped from the history: the team really held that
    conversation, and the Desk draws an empty portrait as one that reached nothing.
    """
    if is_panorama(pericope):
        return []

    return [
        SessionBead(
            key=element.key,
            kind=element.kind,
            label_pt=element.label_pt,
            label_en=element.label_en,
            label_es=element.label_es,
            status=standing.get(element.key, CoverageStatus.NOT_ENCOUNTERED.value),
        )
        for element in labelled_elements(pericope)
    ]
