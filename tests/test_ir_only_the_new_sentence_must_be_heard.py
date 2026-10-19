"""After a sentence is laid in, what did not change stays heard and only the new sentence must be.

Marcia's Q2 of 21 September: "only the new sentence must be heard in its place before the next
check". Her `isStretchHeard` (src/backtranslation/heard.ts at 18fa7c4) measures that stretch on
its own: at most 0.75 s of it unplayed, and never more than half of it.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.internalization_room import PlayedTake
from app.services.internalization_room.back_translation import unheard_parts
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    save_back_translation,
)
from tests.hard_stretch_harness import MemoryStore
from tests.room_harness import room_client, stored_telling_back, the_bucket_is_in_memory
from tests.sentence_harness import re_record, rehearsed_in_wav, spoken


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _laid_in(
    client: httpx.AsyncClient,
    db: AsyncSession,
    store: MemoryStore,
    *,
    heard_before: bool,
    sentence: float = 1.0,
) -> tuple[str, str, str]:
    session, (one, two), ((_, middle, _), _) = await rehearsed_in_wav(
        db, store, [[(0, 1000), (1000, 2000), (2000, 3000)], [(0, 2000)]]
    )
    state = back_translation_of(session)
    state.played_by_take = [
        *(
            [PlayedTake(take_id=one.id, played_ranges=[(0, 3000)], clip_duration_ms=3000)]
            if heard_before
            else []
        ),
        PlayedTake(take_id=two.id, played_ranges=[(0, 2000)], clip_duration_ms=2000),
    ]
    await save_back_translation(db, session, state)
    laid = await re_record(client, session.id, middle.id, spoken(sentence))
    return session.id, laid.json()["segments"][1]["take_id"], two.id


async def _unheard_after_playing(
    db: AsyncSession, session_id: str, laid: str, other: str, played: list[tuple[int, int]]
) -> list[str]:
    session = await get_session(db, session_id)
    state = await stored_telling_back(db, session)
    state.played_by_take = [
        PlayedTake(take_id=laid, played_ranges=played, clip_duration_ms=3400),
        PlayedTake(take_id=other, played_ranges=[(0, 2000)], clip_duration_ms=2000),
    ]
    return unheard_parts(state, [laid, other])


async def test_a_part_heard_before_needs_only_its_new_sentence_heard(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session_id, laid, other = await _laid_in(client, db_session, store, heard_before=True)

    kept = await stored_telling_back(db_session, await get_session(db_session, session_id))
    assert unheard_parts(kept, [laid, other]) == [laid], (
        "a frase nova apagava o que a equipe já tinha ouvido da outra parte"
    )
    almost = await _unheard_after_playing(db_session, session_id, laid, other, [(1000, 1800)])
    short = await _unheard_after_playing(db_session, session_id, laid, other, [(1000, 1650)])

    assert almost == [], "a parte inteira tinha de ser ouvida de novo por uma frase só"
    assert short == [laid], "a frase nova passava como ouvida com mais de metade dela por tocar"


async def test_a_part_never_heard_before_is_heard_whole_after_the_lay_in(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session_id, laid, other = await _laid_in(client, db_session, store, heard_before=False)

    only_the_sentence = await _unheard_after_playing(
        db_session, session_id, laid, other, [(1000, 2400)]
    )
    whole = await _unheard_after_playing(db_session, session_id, laid, other, [(0, 3400)])

    assert only_the_sentence == [laid], (
        "uma parte que ninguém ouviu passava como ouvida por causa da frase nova"
    )
    assert whole == []


async def test_a_long_new_sentence_is_heard_with_at_most_three_quarters_of_a_second_unplayed(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session_id, laid, other = await _laid_in(
        client, db_session, store, heard_before=True, sentence=2.0
    )

    almost = await _unheard_after_playing(db_session, session_id, laid, other, [(1000, 2700)])
    short = await _unheard_after_playing(db_session, session_id, laid, other, [(1000, 2600)])

    assert almost == []
    assert short == [laid], "uma frase longa passava como ouvida com mais de 0,75 s por tocar"
