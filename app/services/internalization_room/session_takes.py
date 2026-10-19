from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTake
from app.models.internalization_room import (
    KeptTakeView,
    MotherTongueTake,
    MotherTongueTakesResponse,
)
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
    return MotherTongueTakesResponse(session_id=session.id, takes=rows)


async def kept_takes_of(session: IRSession) -> list[KeptTakeView]:
    kept = sorted(
        (int(number), told) for number, told in (session.retellings or {}).items() if "kept" in told
    )
    latest = {told["scope"]: number for number, told in kept}
    return [
        KeptTakeView(
            scope=told["scope"],
            turn_number=number,
            audio_url=await signed_listen_url(
                told["kept"]["storage_key"], told["kept"]["content_type"]
            ),
        )
        for number, told in kept
        if latest[told["scope"]] == number
    ]
