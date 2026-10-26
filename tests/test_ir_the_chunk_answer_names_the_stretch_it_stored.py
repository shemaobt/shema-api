from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from app.services.internalization_room.segments import final_segments
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    rehearsed_in_parts_of,
    room_client,
    the_bucket_is_in_memory,
    the_transcriber_says,
)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _tell(
    client: httpx.AsyncClient, session_id: str, take_id: str, audio: bytes
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Device": TABLET},
        data={"take_id": take_id, "starts_ms": "0", "ends_ms": "1000"},
        files={"file": ("trecho.m4a", audio, "audio/mp4")},
    )


async def _replace(
    client: httpx.AsyncClient, session_id: str, segment_id: str, take_id: str
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment_id}/replace",
        headers={"X-Room-Device": TABLET},
        data={"take_id": take_id, "starts_ms": "0", "ends_ms": "1000"},
        files={"file": ("de-novo.m4a", b"a frase traduzida de novo", "audio/mp4")},
    )


def _the_replace_hears(monkeypatch: pytest.MonkeyPatch, said: str) -> None:
    async def heard(*_: object, **__: object) -> str:
        return said

    monkeypatch.setattr(segments_api, "heard", heard)


async def test_a_frase_told_before_any_check_is_replaced_by_the_id_its_telling_answered_with(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_bucket_is_in_memory(monkeypatch)
    the_transcriber_says(monkeypatch, ["a segunda parte, contada de volta"])
    _the_replace_hears(monkeypatch, "a segunda parte, contada de novo")
    session, parts = await rehearsed_in_parts_of(db_session, [1, 0, 1])

    told = await _tell(client, session.id, parts[1].id, b"um trecho traduzido")

    assert told.status_code == 200, told.text
    assert "segment_id" in told.json(), (
        "a resposta do trecho não trazia o id, e a frase contada nesta sessão não chegava"
        " à porta de traduzir de novo"
    )
    replaced = await _replace(client, session.id, told.json()["segment_id"], parts[1].id)
    assert replaced.status_code == 200, replaced.text
    standing = await final_segments(db_session, session.id)
    assert [one.transcript for one in standing if one.take_id == parts[1].id] == [
        "a segunda parte, contada de novo"
    ]


async def test_a_stretch_told_again_answers_with_its_new_version_not_the_one_it_replaced(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_bucket_is_in_memory(monkeypatch)
    the_transcriber_says(monkeypatch, ["a primeira parte, contada outra vez"])
    _the_replace_hears(monkeypatch, "a primeira parte, contada de novo")
    session, parts = await rehearsed_in_parts_of(db_session, [1])
    [first] = await final_segments(db_session, session.id)

    told = await _tell(client, session.id, parts[0].id, b"um trecho traduzido outra vez")

    assert told.status_code == 200, told.text
    assert told.json().get("segment_id") not in (None, first.id), (
        "a resposta apontava a versão que deixou de contar, e a porta recusava com"
        " STRETCH_NO_LONGER_COUNTS"
    )
    replaced = await _replace(client, session.id, told.json()["segment_id"], parts[0].id)
    assert replaced.status_code == 200, replaced.text
    standing = await final_segments(db_session, session.id)
    assert [one.transcript for one in standing] == ["a primeira parte, contada de novo"]


async def test_the_same_recording_sent_again_answers_with_the_id_the_first_answer_carried(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_bucket_is_in_memory(monkeypatch)
    the_transcriber_says(monkeypatch, ["a segunda parte, contada de volta"])
    session, parts = await rehearsed_in_parts_of(db_session, [1, 0, 1])

    first = await _tell(client, session.id, parts[1].id, b"um trecho traduzido")
    again = await _tell(client, session.id, parts[1].id, b"um trecho traduzido")

    assert first.status_code == 200, first.text
    assert again.status_code == 200, again.text
    assert "segment_id" in again.json(), (
        "a resposta perdida, pedida de novo, voltava sem o id e a frase não chegava à porta"
    )
    assert again.json()["segment_id"] == first.json()["segment_id"]
