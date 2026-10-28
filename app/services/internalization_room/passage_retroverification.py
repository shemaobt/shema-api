"""The retroverification file of a passage: the draft's record, under its release's name."""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.internalization_room import IRArchive, IRRelease, IRSession
from app.models.retro_export import RetroExport
from app.services.internalization_room.approved_draft import approved_draft, stands_on
from app.services.internalization_room.entered import latest_entered_first
from app.services.internalization_room.live import live
from app.services.internalization_room.release import _mother_tongue, _slug, released_as
from app.services.internalization_room.retro_export import retro_export
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.take_downloads import _release_id
from app.services.internalization_room.takes import current_parts, takes_of
from app.services.project.facilitated_scope import TEAM_NOT_FOUND
from app.services.project.reads_project import reads_project
from app.utils.stored_time import as_utc


class RetroverificationUnreadable(Exception):
    """A session's stored telling-back cannot be read: the file waits rather than lie."""


async def _read_as_an_archive(
    db: AsyncSession, latest: IRSession, archive_id: str
) -> tuple[IRRelease | None, str]:
    """The release the archive's takes still stand on, else the archive's own stamp.

    ``approved_draft`` is the wrong question here: a Zerar retires every draft. This is what
    ``take_downloads`` asks of an archived session (ADR 0081). The stamp is ENG-1782's format and
    carries no number.
    """
    own = await db.scalar(
        select(IRRelease)
        .where(IRRelease.session_id == latest.id)
        .order_by(IRRelease.version.desc())
        .limit(1)
    )
    if own is not None and stands_on(own, current_parts(await takes_of(db, latest.id))):
        return own, released_as(own)
    archive = await db.get(IRArchive, archive_id)
    if archive is None:
        raise NotFoundError(f"Archive {archive_id} of session {latest.id} is gone")
    stamp = as_utc(archive.archived_at).strftime("%Y%m%d-%H%M")
    tongue = _slug(await _mother_tongue(db, latest))
    return None, f"internalize-{tongue}-{latest.pericope.lower()}-zerada-{stamp}"


async def passage_retroverification_file(
    db: AsyncSession, user: User, *, project_id: str, pericope: str, archive_id: str | None
) -> RetroExport:
    """The file of the passage's draft: the team's latest session in one archive, as hers.

    The live session unless an archive is named (ADR 0071). A session whose stored telling-back
    cannot be read makes the file unreadable: left out, it would read as a passage nobody told.
    """
    if not await reads_project(db, user, project_id):
        raise NotFoundError(TEAM_NOT_FOUND)
    latest = await db.scalar(
        select(IRSession)
        .where(
            IRSession.project_id == project_id,
            IRSession.pericope == pericope,
            IRSession.archive_id == archive_id if archive_id else live(),
        )
        .order_by(*latest_entered_first())
        .limit(1)
    )
    if latest is None:
        raise NotFoundError(f"No sessions of {pericope} for this team")
    try:
        back_translation_of(latest)
    except ValidationError as unreadable:
        raise RetroverificationUnreadable(latest.id) from unreadable
    if archive_id:
        release, release_id = await _read_as_an_archive(db, latest, archive_id)
    else:
        release = await approved_draft(db, latest)
        release_id = await _release_id(db, latest, current_parts(await takes_of(db, latest.id)))
    return await retro_export(db, latest, release, release_id)
