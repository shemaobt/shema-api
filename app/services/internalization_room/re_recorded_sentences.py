from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.internalization_room import IRSession, IRTake
from app.models.internalization_room import ReRecordedSentence, SessionReRecordedSentences
from app.services.internalization_room.manifest import _chain
from app.services.internalization_room.retroverification import retroverification_file
from app.services.internalization_room.sentences import WAV, the_sentence_awaiting
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.takes import (
    current_parts,
    part_positions,
    signed_listen_url,
    takes_of,
)
from app.utils.stored_time import as_utc


def _scene(take: IRTake, positions: dict[int | None, int | None]) -> str | None:
    if take.ordinal not in positions:
        return None
    position = positions[take.ordinal]
    return "whole" if position is None else f"S{position}"


async def re_recorded_sentences_of(
    db: AsyncSession, session: IRSession
) -> SessionReRecordedSentences:
    takes = await takes_of(db, session.id)
    by_id = {take.id: take for take in takes}
    parts = current_parts(takes)
    positions = part_positions(parts)
    laid_in = back_translation_of(session).sentences
    by_take = {one.take_id: one for one in laid_in}
    in_use = {take_id for part in parts for take_id in _chain(part.id, by_take)}
    awaiting = await the_sentence_awaiting(db, session)
    waits = (
        None
        if awaiting is None
        else next(
            one.sentence_id for one in reversed(laid_in) if one.segment_id == awaiting.segment_id
        )
    )
    numbers = {
        one.segment_id: one.frase
        for one in (await retroverification_file(db, session)).stretches
        if one.frase is not None
    }
    return SessionReRecordedSentences(
        session_id=session.id,
        sentences=[
            ReRecordedSentence(
                sentence_id=laid.sentence_id,
                segment_id=laid.segment_id,
                scene=_scene(by_id[laid.take_id], positions),
                at=as_utc(by_id[laid.take_id].created_at).isoformat(),
                starts_ms=laid.starts_ms,
                replaced_ends_ms=laid.replaced_ends_ms,
                ends_ms=laid.ends_ms,
                previous_take_id=laid.previous_take_id,
                in_use=laid.take_id in in_use,
                awaiting_frase=numbers.get(laid.segment_id) if laid.sentence_id == waits else None,
            )
            for laid in laid_in
        ],
    )


async def re_recorded_sentence_url(session: IRSession, sentence_id: str) -> str:
    laid = next(
        (one for one in back_translation_of(session).sentences if one.sentence_id == sentence_id),
        None,
    )
    if laid is None:
        raise NotFoundError(f"No sentence {sentence_id} was recorded again in this session")
    return await signed_listen_url(laid.storage_key, WAV)
