"""The retroverification file of a passage: every session of it, under its release's name."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.internalization_room import IRArchive, IRRelease, IRSession
from app.models.internalization_room import PassageRetroverificationFile
from app.services.internalization_room.approved_draft import approved_draft, stands_on
from app.services.internalization_room.entered import latest_entered_first
from app.services.internalization_room.live import live
from app.services.internalization_room.release import _mother_tongue, _slug, released_as
from app.services.internalization_room.retroverification import retroverification_file
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.take_downloads import _release_id
from app.services.internalization_room.takes import current_parts, takes_of
from app.services.project.facilitated_scope import TEAM_NOT_FOUND
from app.services.project.reads_project import reads_project
from app.utils.stored_time import as_utc

NOT_APPROVED = (
    "rascunho ainda não aprovado — as frases abaixo são a tradução ao vivo, não uma versão fechada"
)
APPROVED_BEFORE_THE_RECORD = (
    "esta versão foi aprovada antes do registro de aprovação existir — "
    "sem estado de conferência gravado; as frases abaixo são a tradução ao vivo"
)


class RetroverificationUnreadable(Exception):
    """A session's stored telling-back cannot be read: the file waits rather than lie."""


async def _read_as_the_draft(db: AsyncSession, latest: IRSession) -> tuple[str, list[str]]:
    standing = await approved_draft(db, latest)
    notices = []
    if standing is None:
        notices.append(NOT_APPROVED)
    elif "check" not in standing.packet:
        notices.append(APPROVED_BEFORE_THE_RECORD)
    release_id = await _release_id(db, latest, current_parts(await takes_of(db, latest.id)))
    return release_id, notices


async def _read_as_an_archive(
    db: AsyncSession, latest: IRSession, archive_id: str
) -> tuple[str, list[str]]:
    """The release the archive's takes still stand on, else the archive's own stamp.

    ``approved_draft`` is the wrong question here: a Zerar retires every draft. This is the
    question ``take_downloads`` asks of an archived session (ADR 0081), so the file, its note
    and the takes' downloads agree: a release the takes were re-recorded past is not their name.
    The stamp is ENG-1782's format, from the archive's UTC moment.
    """
    own = await db.scalar(
        select(IRRelease)
        .where(IRRelease.session_id == latest.id)
        .order_by(IRRelease.version.desc())
        .limit(1)
    )
    if own is not None and stands_on(own, current_parts(await takes_of(db, latest.id))):
        notices = [] if "check" in own.packet else [APPROVED_BEFORE_THE_RECORD]
        return released_as(own), notices
    archive = await db.get(IRArchive, archive_id)
    if archive is None:
        raise NotFoundError(f"Archive {archive_id} of session {latest.id} is gone")
    stamp = as_utc(archive.archived_at).strftime("%Y%m%d-%H%M")
    tongue = _slug(await _mother_tongue(db, latest))
    return f"internalize-{tongue}-{latest.pericope.lower()}-zerada-{stamp}", [NOT_APPROVED]


async def passage_retroverification_file(
    db: AsyncSession, user: User, *, project_id: str, pericope: str, archive_id: str | None
) -> PassageRetroverificationFile:
    """The passage's sessions in one archive (the live ones by default), oldest first.

    A session whose stored telling-back cannot be read makes the whole file unreadable: left
    out, it would read as a session nobody told.
    """
    if not await reads_project(db, user, project_id):
        raise NotFoundError(TEAM_NOT_FOUND)
    in_scope = (
        IRSession.project_id == project_id,
        IRSession.pericope == pericope,
        IRSession.archive_id == archive_id if archive_id else live(),
    )
    sessions = list(
        await db.scalars(
            select(IRSession).where(*in_scope).order_by(IRSession.created_at, IRSession.id)
        )
    )
    latest = await db.scalar(
        select(IRSession).where(*in_scope).order_by(*latest_entered_first()).limit(1)
    )
    if latest is None:
        raise NotFoundError(f"No sessions of {pericope} for this team")
    release_id, notices = (
        await _read_as_an_archive(db, latest, archive_id)
        if archive_id
        else await _read_as_the_draft(db, latest)
    )
    for session in sessions:
        try:
            back_translation_of(session)
        except ValidationError as unreadable:
            raise RetroverificationUnreadable(session.id) from unreadable
    files = [await retroverification_file(db, session) for session in sessions]
    return PassageRetroverificationFile(
        release_id=release_id,
        project_id=project_id,
        pericope=pericope,
        generated_at=datetime.now(UTC).isoformat(),
        notices=notices,
        sessions=files,
    )
