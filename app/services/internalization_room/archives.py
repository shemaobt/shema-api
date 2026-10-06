"""Zerar: a facilitator gives a team a clean pericope, and the work stays for the consultant.

Nothing moves and nothing is deleted but the team's open-door pointers: every live row of the
pericope's work is stamped with one new **Archive**, in every language, in one transaction
(ADR 0047). The doors that pick or list a team's work then leave the stamped rows out, so the
next open mints a new session.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.internalization_room import (
    IRArchive,
    IRCoverageEvent,
    IRRelease,
    IRSegment,
    IRSession,
    IRTake,
    IRTeamSession,
)
from app.models.internalization_room_archive import ArchivedSession, KeptPart
from app.services.internalization_room.live import live
from app.services.internalization_room.takes import current_parts, takes_of
from app.services.project.facilitated_scope import TEAM_NOT_FOUND
from app.services.project.facilitates_project import facilitates_project
from app.utils.stored_time import as_utc

_HANGING_OFF_A_SESSION = (IRTake, IRSegment, IRCoverageEvent, IRRelease)


async def archive_pericope(
    db: AsyncSession, user: User, *, project_id: str, pericope: str
) -> IRArchive | None:
    """Stamp the team's live work on this pericope with a new archive, or ``None`` when
    nothing of it is live.

    The sessions are stamped first and only those whose stamp is still null, by one UPDATE
    that names them back: the predicate is checked again under the row lock, so two Zerars at
    once never stamp a row twice and the second finds nothing. A row hanging off a session
    belongs to that session's archive, so the four tables below are stamped by the sessions
    just stamped and never by pericope. ``updated_at`` is written back as it was: an archive
    is not the team's activity, and the snapshot keeps the session as it stood. ``version``
    moves, so a turn still in flight on a stamped session cannot land on it.

    The pointers deleted are the ones naming a stamped session, so a pointer another open
    claims for a new session while this runs is never the one deleted.

    Nothing live is not a conflict: nothing is written, not even the archive row, and the
    caller says so in a field.
    """
    if not await facilitates_project(db, user, project_id):
        raise NotFoundError(TEAM_NOT_FOUND)
    archive_id = str(uuid.uuid4())
    stamped = list(
        await db.scalars(
            update(IRSession)
            .where(
                IRSession.project_id == project_id,
                IRSession.pericope == pericope,
                live(),
            )
            .values(
                archive_id=archive_id,
                updated_at=IRSession.updated_at,
                version=IRSession.version + 1,
            )
            .returning(IRSession.id)
            .execution_options(synchronize_session=False)
        )
    )
    if not stamped:
        return None
    for model in _HANGING_OFF_A_SESSION:
        await db.execute(
            update(model)
            .where(model.session_id.in_(stamped), live(model))
            .values(archive_id=archive_id)
            .execution_options(synchronize_session=False)
        )
    archive = IRArchive(
        id=archive_id,
        project_id=project_id,
        pericope=pericope,
        archived_by=user.id,
        snapshot=[entry.model_dump() for entry in await _as_they_stood(db, stamped)],
    )
    db.add(archive)
    await db.execute(
        delete(IRTeamSession).where(
            IRTeamSession.project_id == project_id,
            IRTeamSession.pericope == pericope,
            IRTeamSession.session_id.in_(stamped),
        )
    )
    await db.commit()
    return archive


async def _as_they_stood(db: AsyncSession, session_ids: list[str]) -> list[ArchivedSession]:
    """Each session's dossier: ``turns`` counts the guide's lines, her ``turnCount``.

    ``kept_takes`` are the parts the team had kept, the newest rehearsal under each part number
    as the room reads them, and not every rehearsal ever uploaded; a list, because the passage
    told whole is a part with no number. ``ir_sessions.kept_takes`` is never written and says
    nothing.
    """
    kept = {
        session_id: [
            KeptPart(part=take.ordinal, take_id=take.id)
            for take in current_parts(await takes_of(db, session_id))
        ]
        for session_id in session_ids
    }
    sessions = await db.scalars(
        select(IRSession)
        .where(IRSession.id.in_(session_ids))
        .order_by(IRSession.created_at, IRSession.id)
        .execution_options(populate_existing=True)
    )
    minted = await db.execute(
        select(IRRelease.session_id, IRRelease.version)
        .where(IRRelease.session_id.in_(session_ids))
        .order_by(IRRelease.version)
    )
    versions: dict[str, list[int]] = {}
    for session_id, version in minted.all():
        versions.setdefault(session_id, []).append(version)
    return [
        ArchivedSession(
            session_id=session.id,
            language=session.language,
            status=session.status.value,
            coverage=session.coverage_state,
            turns=sum(1 for line in session.messages or [] if line.get("role") == "guide"),
            kept_takes=kept[session.id],
            release_versions=versions.get(session.id, []),
            created_at=as_utc(session.created_at).isoformat(),
            updated_at=as_utc(session.updated_at).isoformat(),
        )
        for session in sessions
    ]
