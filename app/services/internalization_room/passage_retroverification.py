"""The retroverification file of a passage: every session of it, under its release's name."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.internalization_room import IRSession
from app.models.internalization_room import PassageRetroverificationFile
from app.services.internalization_room.approved_draft import approved_draft
from app.services.internalization_room.entered import latest_entered_first
from app.services.internalization_room.live import live
from app.services.internalization_room.retroverification import retroverification_file
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.take_downloads import _release_id
from app.services.internalization_room.takes import current_parts, takes_of
from app.services.project.facilitated_scope import TEAM_NOT_FOUND
from app.services.project.reads_project import reads_project

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


async def passage_retroverification_file(
    db: AsyncSession, user: User, *, project_id: str, pericope: str
) -> PassageRetroverificationFile:
    """The passage's live sessions, oldest first.

    A session whose stored telling-back cannot be read makes the whole file unreadable: left
    out, it would read as a session nobody told.
    """
    if not await reads_project(db, user, project_id):
        raise NotFoundError(TEAM_NOT_FOUND)
    in_scope = (
        IRSession.project_id == project_id,
        IRSession.pericope == pericope,
        live(),
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
    release_id, notices = await _read_as_the_draft(db, latest)
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
