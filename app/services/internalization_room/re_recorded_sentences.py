from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTake
from app.models.internalization_room import ReRecordedSentence, SessionReRecordedSentences
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.takes import current_parts, part_positions, takes_of
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
    positions = part_positions(current_parts(takes))
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
            )
            for laid in back_translation_of(session).sentences
        ],
    )
