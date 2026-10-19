"""The team repairs a frase by recording its sentence again, whole, and it is laid in its place.

Her rule of 21 September (docs/ENSAIO-FINAL-SPEC.md §6, src/draft/splice.ts at 18fa7c4): the
new sentence replaces the old one inside the part, the audio around it stays as it was, and the
frases after it move by the difference in length.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.segments import final_segments
from tests.device_harness import a_linked_tablet
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.sentence_harness import (
    RATE,
    re_record,
    rehearsed_in_wav,
    samples_of,
    seconds,
    spoken,
    take_named,
    wav,
)


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def test_the_new_sentence_takes_the_old_ones_place_and_the_frases_after_it_move(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, (one, two), ((_, middle, _), _) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)], [(0, 2000)]]
    )

    laid = await re_record(client, session.id, middle.id, spoken(1.0))

    assert laid.status_code == 200, laid.text
    read = (await client.get(f"{PREFIX}/sessions/{session.id}")).json()
    spans = [
        (one["take_id"], one["starts_ms"], one["ends_ms"])
        for one in read["back_translation"]["segments"]
    ]
    new = spans[0][0]
    assert new not in (one.id, two.id), "a frase continuava sobre a gravação de antes"
    assert spans == [
        (new, 0, 1000),
        (new, 1000, 2400),
        (new, 2400, 3400),
        (two.id, 0, 2000),
    ], "as frases depois da nova não andavam a diferença, ou a outra parte mexia"
    before = samples_of(store.objects[one.storage_key])
    after = samples_of(store.objects[(await take_named(db_session, new)).storage_key])
    assert after[:RATE] == before[:RATE], "o áudio antes da frase mudava"
    assert after[-RATE:] == before[-RATE:], "o áudio depois da frase mudava"


async def test_a_tablet_of_another_team_lays_nothing_into_this_teams_part(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, (one,), ((frase,),) = await rehearsed_in_wav(db_session, store, [[(0, 2000)]])
    stranger = await a_linked_tablet(db_session, team_id="outra-equipe")

    refused = await re_record(client, session.id, frase.id, spoken(1.0), headers=stranger.headers)

    assert refused.status_code == 404, refused.text
    assert [stretch.take_id for stretch in await final_segments(db_session, session.id)] == [
        one.id
    ], "um tablet de outra equipe regravava uma frase desta"


async def test_a_sentence_over_four_megabytes_is_refused_before_anything_is_read(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, _ = await rehearsed_in_wav(db_session, store, [[(0, 2000)]])
    kept = dict(store.objects)

    refused = await re_record(
        client, session.id, "frase-que-nao-existe", b"R" * (4 * 1024 * 1024 + 1)
    )

    assert (refused.status_code, refused.json().get("code")) == (413, "SENTENCE_TOO_LONG"), (
        "uma frase de mais de 4 MB passava da porta, ou só depois de procurar a frase"
    )
    assert store.objects == kept, "a frase longa demais deixava algo guardado"


@pytest.mark.parametrize(
    "recorded",
    [
        wav(seconds(0.3, 9000)),
        wav(seconds(0.98, 0) + seconds(0.04, 9000) + seconds(0.98, 0)),
    ],
    ids=["a third of a second", "a blip in two seconds of silence"],
)
async def test_a_sentence_shorter_than_half_a_second_once_trimmed_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, recorded: bytes
) -> None:
    session, (one,), ((frase,),) = await rehearsed_in_wav(db_session, store, [[(0, 2000)]])
    kept = dict(store.objects)

    refused = await re_record(client, session.id, frase.id, recorded)

    assert (refused.status_code, refused.json().get("code")) == (400, "SENTENCE_TOO_SHORT"), (
        "um toque sem frase era emendado na parte"
    )
    assert store.objects == kept
    assert [stretch.take_id for stretch in await final_segments(db_session, session.id)] == [one.id]
