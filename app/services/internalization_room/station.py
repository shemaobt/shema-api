"""The stop of the room a session is in, derived from what the session holds.

Never stored and never sent by the tablet: a release of the session is `approved`, else a
telling-back still carrying a finding is `findings`, else a stretch told is `telling_back`,
else a rehearsal take kept is `rehearsal`, else the conversation. The facts that are rows
(take, stretch, release) arrive as correlated `EXISTS` columns of the select that already reads
the session, so a listing costs one statement however many sessions it holds; the one fact in
JSON, the findings, is read from the session's own `back_translation`.

`latest_visits` answers the rail and the team card: the latest entered session of a team on a
pericope, picked in SQL, with the moment it last moved. That moment is the team's own: its
turns, takes, stretches and halts. `updated_at` is a facilitator's click as much as a team's
act, so it counts only while a blocking halt stands, which is when the row is stamped for it.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import (
    IRRelease,
    IRSegment,
    IRSession,
    IRSessionStatus,
    IRTake,
    IRTakeKind,
    IRTurn,
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


def station_of(back_translation: dict[str, Any] | None, held: Held) -> Station:
    if held.released:
        return Station.APPROVED
    if BackTranslationState.model_validate(back_translation or {}).findings:
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
    rows = await db.execute(
        select(IRSession.id, IRSession.back_translation, *held_columns()).where(
            IRSession.id.in_(ids)
        )
    )
    return {
        session_id: station_of(back_translation, Held(rehearsed, told, released))
        for session_id, back_translation, rehearsed, told, released in rows.all()
    }


@dataclass(frozen=True)
class Visit:
    session_id: str
    station: Station
    released: bool
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
    entered_here = [IRSession.project_id.in_(project_ids), entered()]
    if pericopes is not None:
        entered_here.append(IRSession.pericope.in_(pericopes))
    latest = (
        select(
            IRSession.id.label("id"),
            func.row_number()
            .over(
                partition_by=(IRSession.project_id, IRSession.pericope),
                order_by=(IRSession.created_at.desc(), IRSession.id.desc()),
            )
            .label("rank"),
        )
        .where(*entered_here)
        .subquery()
    )
    last_turn = (
        select(func.max(IRTurn.created_at))
        .where(IRTurn.session_id == IRSession.id)
        .scalar_subquery()
    )
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
    rows = await db.execute(
        select(
            IRSession.id,
            IRSession.project_id,
            IRSession.pericope,
            IRSession.status,
            IRSession.created_at,
            IRSession.updated_at,
            IRSession.warned_at,
            IRSession.back_translation,
            *held_columns(),
            last_turn,
            last_take,
            last_stretch,
        )
        .join(latest, latest.c.id == IRSession.id)
        .where(latest.c.rank == 1)
    )
    visits: dict[tuple[str, str], Visit] = {}
    for (
        session_id,
        project_id,
        pericope,
        status,
        created_at,
        updated_at,
        warned_at,
        back_translation,
        rehearsed,
        told,
        released,
        turn_at,
        take_at,
        stretch_at,
    ) in rows.all():
        halted_at = updated_at if status is IRSessionStatus.NEEDS_PERSON else None
        moments = [created_at, warned_at, halted_at, turn_at, take_at, stretch_at]
        visits[(project_id, pericope)] = Visit(
            session_id=session_id,
            station=station_of(back_translation, Held(rehearsed, told, released)),
            released=released,
            started_at=as_utc(created_at),
            moved_at=max(as_utc(moment) for moment in moments if moment is not None),
        )
    return visits
