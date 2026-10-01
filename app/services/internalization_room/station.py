from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import (
    IRRelease,
    IRSegment,
    IRSession,
    IRTake,
    IRTakeKind,
)
from app.models.internalization_room import Station
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.entered import entered
from app.services.internalization_room.session_end import as_utc


@dataclass(frozen=True)
class Held:
    rehearsed: bool
    told: bool
    released: bool


def held_columns() -> tuple[ColumnElement[bool], ColumnElement[bool], ColumnElement[bool]]:
    return (
        select(IRTake.id)
        .where(IRTake.session_id == IRSession.id, IRTake.kind == IRTakeKind.ENSAIO)
        .exists()
        .label("rehearsed"),
        select(IRSegment.id).where(IRSegment.session_id == IRSession.id).exists().label("told"),
        select(IRRelease.id).where(IRRelease.session_id == IRSession.id).exists().label("released"),
    )


def station_of(session: IRSession, held: Held) -> Station:
    if held.released:
        return Station.APPROVED
    if BackTranslationState.model_validate(session.back_translation or {}).findings:
        return Station.FINDINGS
    if held.told:
        return Station.TELLING_BACK
    if held.rehearsed:
        return Station.REHEARSAL
    return Station.CONVERSATION


async def stations_of(db: AsyncSession, session_ids: Iterable[str]) -> dict[str, Station]:
    ids = list(session_ids)
    if not ids:
        return {}
    rows = await db.execute(select(IRSession, *held_columns()).where(IRSession.id.in_(ids)))
    return {
        session.id: station_of(session, Held(rehearsed, told, released))
        for session, rehearsed, told, released in rows.all()
    }


@dataclass(frozen=True)
class Visit:
    session_id: str
    station: Station
    started_at: datetime
    moved_at: datetime


def visit_in(
    visits: Mapping[tuple[str, str], Visit], project_id: str, pericope: str | None
) -> Visit | None:
    return None if pericope is None else visits.get((project_id, pericope))


async def latest_visits(
    db: AsyncSession, project_ids: Collection[str], pericopes: Collection[str] | None = None
) -> dict[tuple[str, str], Visit]:
    if not project_ids:
        return {}
    last_take = (
        select(func.max(IRTake.created_at))
        .where(IRTake.session_id == IRSession.id)
        .scalar_subquery()
    )
    last_stretch = (
        select(func.max(IRSegment.created_at))
        .where(IRSegment.session_id == IRSession.id)
        .scalar_subquery()
    )
    query = (
        select(IRSession, *held_columns(), last_take, last_stretch)
        .where(IRSession.project_id.in_(project_ids), entered())
        .order_by(IRSession.created_at.desc(), IRSession.id.desc())
    )
    if pericopes is not None:
        query = query.where(IRSession.pericope.in_(pericopes))
    visits: dict[tuple[str, str], Visit] = {}
    for session, rehearsed, told, released, take_at, stretch_at in (await db.execute(query)).all():
        key = (session.project_id, session.pericope)
        if key in visits:
            continue
        moments = [session.updated_at, session.warned_at, take_at, stretch_at]
        visits[key] = Visit(
            session_id=session.id,
            station=station_of(session, Held(rehearsed, told, released)),
            started_at=as_utc(session.created_at),
            moved_at=max(as_utc(moment) for moment in moments if moment is not None),
        )
    return visits
