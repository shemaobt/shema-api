from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from app.services import internalization_room as room_package
from app.services.internalization_room import back_translation
from app.services.internalization_room.segments import final_segments
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    PART_MS,
    a_piece_still_to_be_told,
    heard_every_part,
    nothing_is_read_ahead,
    press_terminei,
    rehearsed_in_parts,
    rehearsed_in_parts_of,
    room_client,
    the_analyst_is_scripted,
    the_bucket_is_in_memory,
    the_room_speaks,
    the_transcriber_says,
)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _segments_of_the_read(client: httpx.AsyncClient, session_id: str) -> list[dict]:
    read = await client.get(f"{PREFIX}/sessions/{session_id}")
    assert read.status_code == 200, read.text
    return read.json()["back_translation"]["segments"]


async def test_the_session_read_numbers_four_told_stretches_one_to_four_in_the_voices_order(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 4)
    standing = await final_segments(db_session, session.id)

    segments = await _segments_of_the_read(client, session.id)

    assert [one["segment_id"] for one in segments] == [one.id for one in standing]
    assert [one.get("frase") for one in segments] == [1, 2, 3, 4], (
        "a sala dizia «na frase 3» e a leitura da sessão não numerava nenhum trecho"
    )


async def test_an_untold_piece_has_no_frase_and_takes_no_number_from_the_told_ones(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    standing = await final_segments(db_session, session.id)
    await a_piece_still_to_be_told(db_session, session, standing[1])

    segments = await _segments_of_the_read(client, session.id)

    assert [one["told"] for one in segments] == [True, True, False, True]
    assert [one.get("frase") for one in segments] == [1, 2, None, 3], (
        "a parte por contar ficava sem número, mas a frase seguinte contava com ela"
    )


async def test_dividing_a_stretch_answers_with_the_numbers_the_next_read_serves(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    standing = await final_segments(db_session, session.id)

    divided = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{standing[1].id}/divide",
        headers={"X-Room-Device": TABLET},
        json={"at_ms": PART_MS // 2},
    )

    assert divided.status_code == 200, divided.text
    answered = divided.json()["segments"]
    assert [one.get("frase") for one in answered] == [1, None, None, 2], (
        "o corte devolvia a lista sem números e a tela se renumerava sozinha"
    )
    assert answered == await _segments_of_the_read(client, session.id)


async def test_a_stretch_told_again_answers_with_the_number_it_already_had(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_bucket_is_in_memory(monkeypatch)
    nothing_is_read_ahead(monkeypatch)

    async def heard(*_: object, **__: object) -> str:
        return "Rute disse que iria aonde Noemi fosse."

    monkeypatch.setattr(segments_api, "heard", heard)
    session, _parts = await rehearsed_in_parts(db_session, 4)
    standing = await final_segments(db_session, session.id)

    replaced = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{standing[1].id}/replace",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": standing[1].take_id,
            "starts_ms": str(standing[1].starts_ms),
            "ends_ms": str(standing[1].ends_ms),
        },
        files={"file": ("de-novo.m4a", b"a frase dois traduzida de novo", "audio/mp4")},
    )

    assert replaced.status_code == 200, replaced.text
    answered = replaced.json()["segments"]
    assert [one.get("frase") for one in answered] == [1, 2, 3, 4], (
        "a frase traduzida de novo perdia o número e arrastava as seguintes"
    )
    assert answered == await _segments_of_the_read(client, session.id)


async def _tell(
    client: httpx.AsyncClient,
    session_id: str,
    take_id: str,
    *,
    starts_ms: int,
    ends_ms: int,
    retelling: bool = False,
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": take_id,
            "starts_ms": str(starts_ms),
            "ends_ms": str(ends_ms),
            "retelling": "true" if retelling else "false",
        },
        files={"file": ("trecho.m4a", b"um trecho traduzido", "audio/mp4")},
    )


async def test_the_telling_answer_numbers_a_stretch_told_between_two_others_as_the_read_will(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_bucket_is_in_memory(monkeypatch)
    nothing_is_read_ahead(monkeypatch)
    the_transcriber_says(monkeypatch, ["a segunda parte, contada de volta"])
    session, parts = await rehearsed_in_parts_of(db_session, [1, 0, 1])

    told = await _tell(client, session.id, parts[1].id, starts_ms=0, ends_ms=1000)

    assert told.status_code == 200, told.text
    assert told.json().get("frase") == 2, (
        "a frase recém-contada ficava sem número até a próxima leitura, e a tela contava sozinha"
    )
    read = await _segments_of_the_read(client, session.id)
    assert [one.get("frase") for one in read] == [1, 2, 3]
    assert next(one["frase"] for one in read if one["take_id"] == parts[1].id) == 2


async def test_a_stretch_told_again_through_the_telling_answer_keeps_its_number(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_bucket_is_in_memory(monkeypatch)
    nothing_is_read_ahead(monkeypatch)
    the_transcriber_says(monkeypatch, ["a primeira parte, contada outra vez"])
    session, parts = await rehearsed_in_parts_of(db_session, [1, 1, 1])

    told = await _tell(client, session.id, parts[0].id, starts_ms=0, ends_ms=1000, retelling=True)

    assert told.status_code == 200, told.text
    assert told.json().get("frase") == 1, (
        "a frase contada de novo recebia o número seguinte ao da última, e não o que já tinha"
    )
    read = await _segments_of_the_read(client, session.id)
    assert [one.get("frase") for one in read] == [1, 2, 3]


async def test_a_missing_element_after_frase_two_says_frase_two_and_points_at_the_next_stretch(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyst = the_analyst_is_scripted(monkeypatch)
    the_room_speaks(monkeypatch)
    session, _parts = await rehearsed_in_parts(db_session, 4)
    told = await final_segments(db_session, session.id)
    analyst.readings = [
        {
            "findings": [
                {"kind": "missing", "note": "a notícia do pão", "chunk": 2, "where": "after"}
            ]
        }
    ]

    answered = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )

    assert answered.status_code == 200, answered.text
    expected = [{"kind": "missing", "frase": 2, "segment_id": told[2].id}]
    assert answered.json()["findings"] == expected, (
        "o achado depois da frase 2 dizia a frase 3, porque apontava para o trecho seguinte"
    )
    read = await client.get(f"{PREFIX}/sessions/{session.id}")
    assert read.json()["back_translation"]["findings"] == expected


async def test_the_voices_block_and_the_views_number_their_stretches_with_one_function(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyst = the_analyst_is_scripted(monkeypatch)
    the_room_speaks(monkeypatch)
    original = back_translation.frase_numbers

    def ten_further(told: list) -> dict[str, int]:
        return {segment_id: number + 10 for segment_id, number in original(told).items()}

    monkeypatch.setattr(back_translation, "frase_numbers", ten_further)
    monkeypatch.setattr(room_package, "frase_numbers", ten_further)
    session, _parts = await rehearsed_in_parts(db_session, 3)

    await press_terminei(client, session.id, report=await heard_every_part(db_session, session.id))

    block = analyst.shown[-1]
    assert [f"[frase {number}" in block for number in (11, 12, 13)] == [True, True, True], (
        "a sala numerava as frases para a analista por conta própria, e as telas por outra"
    )
    read = await _segments_of_the_read(client, session.id)
    assert [one.get("frase") for one in read] == [11, 12, 13]


async def test_after_the_translation_starts_over_the_numbering_starts_over_with_it(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_bucket_is_in_memory(monkeypatch)
    nothing_is_read_ahead(monkeypatch)
    the_transcriber_says(monkeypatch, ["a terceira parte, de novo", "a primeira parte, de novo"])
    session, parts = await rehearsed_in_parts_of(db_session, [1, 1, 1])

    restarted = await client.post(f"{PREFIX}/sessions/{session.id}/back-translation/restart")
    assert restarted.json()["segments"] == []
    third = await _tell(client, session.id, parts[2].id, starts_ms=0, ends_ms=1000)
    first = await _tell(client, session.id, parts[0].id, starts_ms=0, ends_ms=1000)

    assert [third.json().get("frase"), first.json().get("frase")] == [1, 1], (
        "o número da frase seguia contando as que a equipe já tinha jogado fora"
    )
    read = await _segments_of_the_read(client, session.id)
    assert [one.get("frase") for one in read] == [1, 2]
