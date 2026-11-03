"""«Aprovar mesmo assim (forçar)»: a facilitator forces a passage's release (ADR 0075)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.internalization_room import IRRelease, IRSession, IRTake, IRTakeKind
from app.services.internalization_room.entered import latest_entered_first
from app.services.internalization_room.live import live
from app.services.internalization_room.release import (
    InternalizationReleaseBlocked,
    approve_release,
)
from app.services.project.facilitated_scope import TEAM_NOT_FOUND
from app.services.project.facilitates_project import facilitates_project


async def force_passage(
    db: AsyncSession, user: User, *, project_id: str, pericope: str
) -> IRRelease:
    """Force the release of the passage's live session that holds rehearsal takes.

    The most recently active one when there are several, in any language, as the Zerar reaches
    every language. A passage with no such session is refused with ``no_rehearsal_audio``,
    the one blocker no force passes, and nothing is written.
    """
    if not await facilitates_project(db, user, project_id):
        raise NotFoundError(TEAM_NOT_FOUND)
    rehearsed = (
        select(IRTake.id)
        .where(IRTake.session_id == IRSession.id, IRTake.kind == IRTakeKind.ENSAIO)
        .exists()
    )
    session = (
        await db.scalars(
            select(IRSession)
            .where(
                IRSession.project_id == project_id,
                IRSession.pericope == pericope,
                live(),
                rehearsed,
            )
            .order_by(*latest_entered_first())
            .limit(1)
        )
    ).first()
    if session is None:
        raise InternalizationReleaseBlocked(["no_rehearsal_audio"])
    return await approve_release(db, session, forced_by=user.id)
