from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTake
from app.models.internalization_room import (
    KeptRehearsal,
    KeptTakeView,
    MotherTongueTake,
    MotherTongueTakesResponse,
)
from app.services.internalization_room.classify_coverage import KeptRecording, Retelling
from app.services.internalization_room.release import _recording_grain
from app.services.internalization_room.session_turns import TeamTurn, team_turn_of
from app.services.internalization_room.takes import (
    TakeStore,
    current_parts,
    listen_url,
    signed_listen_url,
    takes_of,
)
from app.utils.stored_time import as_utc


async def _link_of(store: TakeStore, take: IRTake) -> str | None:
    try:
        held = await store.stat(take.storage_key)
        if held is None:
            return None
        return await listen_url(take)
    except Exception:
        return None


async def mother_tongue_takes_of(
    db: AsyncSession, session: IRSession, store: TakeStore
) -> MotherTongueTakesResponse:
    """The recordings of the session in the mother tongue, one per part, in reading order."""
    rows: list[MotherTongueTake] = []
    position = 0
    parts = current_parts(await takes_of(db, session.id))
    links = await asyncio.gather(*(_link_of(store, take) for take in parts))
    for take, link in zip(parts, links, strict=True):
        if take.ordinal is not None:
            position += 1
        rows.append(
            MotherTongueTake(
                take_id=take.id,
                part=None if take.ordinal is None else position,
                size_kb=(take.size_bytes + 512) // 1024,
                fingerprint=take.sha256[:12],
                recorded_at=as_utc(take.created_at).isoformat(),
                play_url=link,
                unread=link is None,
            )
        )
    return MotherTongueTakesResponse(
        session_id=session.id,
        takes=rows,
        kept_rehearsals=await kept_rehearsals_of(db, session),
        recording_grain=_recording_grain(parts) if parts else None,
    )


def _latest_kept_of_each_scope(session: IRSession) -> dict[str, tuple[int, KeptRecording]]:
    latest: dict[str, tuple[int, KeptRecording]] = {}
    for number, entry in sorted((int(n), e) for n, e in (session.retellings or {}).items()):
        told = Retelling.model_validate(entry)
        if told.kept is not None:
            latest[told.scope] = (number, told.kept)
    return latest


async def kept_rehearsals_of(db: AsyncSession, session: IRSession) -> list[KeptRehearsal]:
    siblings = (
        (
            await db.execute(
                select(IRSession).where(
                    IRSession.project_id == session.project_id,
                    IRSession.pericope == session.pericope,
                    IRSession.language == session.language,
                    IRSession.archive_id == session.archive_id,
                )
            )
        )
        .scalars()
        .all()
    )
    latest: dict[str, tuple[TeamTurn, int, bool]] = {}
    for sibling in siblings:
        for scope, (number, _) in _latest_kept_of_each_scope(sibling).items():
            turn = team_turn_of(sibling, number)
            if scope not in latest or turn.at > latest[scope][0].at:
                latest[scope] = (turn, number, sibling.id != session.id)
    told = latest.values()
    return [
        KeptRehearsal(turn_number=number, words=turn.words, from_other_session=other)
        for turn, number, other in sorted(told, key=lambda each: each[0].at)
    ]


async def kept_takes_of(session: IRSession) -> list[KeptTakeView]:
    latest = _latest_kept_of_each_scope(session)
    ordered = sorted(latest.items(), key=lambda kept: kept[1][0])
    links = await asyncio.gather(
        *(
            signed_listen_url(recording.storage_key, recording.content_type)
            for _, (_, recording) in ordered
        )
    )
    return [
        KeptTakeView(scope=scope, turn_number=number, audio_url=link)
        for (scope, (number, _)), link in zip(ordered, links, strict=True)
    ]
