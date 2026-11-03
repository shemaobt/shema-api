from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sessions import get_session
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    PART_MS,
    Room,
    ScriptedAnalyst,
    a_piece_still_to_be_told,
    heard_every_part,
    played_every_part,
    press_terminei,
    record_the_part_again,
    rehearsed_in_parts,
    rehearsed_in_parts_of,
    room_client,
    the_analyst_is_scripted,
    the_bucket_is_in_memory,
    the_room_speaks,
    the_transcriber_says,
)


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> ScriptedAnalyst:
    return the_analyst_is_scripted(monkeypatch)


@pytest.fixture()
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _finish(client: httpx.AsyncClient, db: AsyncSession, session_id: str) -> httpx.Response:
    return await press_terminei(client, session_id, report=await heard_every_part(db, session_id))


async def _findings_of_the_read(client: httpx.AsyncClient, session_id: str) -> list[dict]:
    read = await client.get(f"{PREFIX}/sessions/{session_id}")
    assert read.status_code == 200, read.text
    return read.json()["back_translation"]["findings"]


async def test_a_divide_that_leaves_earlier_stretches_untold_moves_the_finding_down_with_its_frase(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    told = await final_segments(db_session, session.id)
    analyst.readings = [{"findings": [{"kind": "addition", "note": "Rute foi junto", "chunk": 3}]}]
    await _finish(client, db_session, session.id)
    assert await _findings_of_the_read(client, session.id) == [
        {"kind": "addition", "frase": 3, "segment_id": told[2].id}
    ]

    divided = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{told[0].id}/divide",
        headers={"X-Room-Device": TABLET},
        json={"at_ms": PART_MS // 2},
    )

    assert divided.status_code == 200, divided.text
    assert await _findings_of_the_read(client, session.id) == [
        {"kind": "addition", "frase": 2, "segment_id": told[2].id}
    ], "o achado seguia dizendo a frase 3 depois que o corte deixou a terceira como a segunda"


async def _tell(
    client: httpx.AsyncClient, session_id: str, take_id: str, *, starts_ms: int, ends_ms: int
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": take_id,
            "starts_ms": str(starts_ms),
            "ends_ms": str(ends_ms),
            "retelling": "false",
        },
        files={"file": ("trecho.m4a", b"um trecho traduzido", "audio/mp4")},
    )


async def test_telling_an_untold_piece_moves_the_finding_up_with_its_frase(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_bucket_is_in_memory(monkeypatch)
    the_transcriber_says(monkeypatch, ["a metade que faltava, contada de volta"])
    session, _parts = await rehearsed_in_parts(db_session, 3)
    told = await final_segments(db_session, session.id)
    analyst.readings = [{"findings": [{"kind": "addition", "note": "Rute foi junto", "chunk": 3}]}]
    await _finish(client, db_session, session.id)
    tail = await a_piece_still_to_be_told(db_session, session, told[0])
    assert await _findings_of_the_read(client, session.id) == [
        {"kind": "addition", "frase": 3, "segment_id": told[2].id}
    ]

    answered = await _tell(
        client, session.id, tail.take_id, starts_ms=tail.starts_ms, ends_ms=tail.ends_ms
    )

    assert answered.status_code == 200, answered.text
    assert await _findings_of_the_read(client, session.id) == [
        {"kind": "addition", "frase": 4, "segment_id": told[2].id}
    ], "o achado seguia dizendo a frase 3 depois que a metade contada empurrou a terceira"


async def test_a_part_recorded_again_moves_the_finding_down_with_its_frase(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, parts = await rehearsed_in_parts(db_session, 3)
    told = await final_segments(db_session, session.id)
    analyst.readings = [{"findings": [{"kind": "addition", "note": "Rute foi junto", "chunk": 3}]}]
    await _finish(client, db_session, session.id)

    await record_the_part_again(db_session, session, parts[0], sha256="f" * 64)

    assert await _findings_of_the_read(client, session.id) == [
        {"kind": "addition", "frase": 2, "segment_id": told[2].id}
    ], "o achado seguia dizendo a frase 3 depois que a primeira parte foi gravada de novo"


async def test_a_telling_placed_earlier_in_the_reading_moves_the_finding_up_with_its_frase(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_bucket_is_in_memory(monkeypatch)
    the_transcriber_says(monkeypatch, ["a segunda parte, contada de volta"])
    session, parts = await rehearsed_in_parts_of(db_session, [1, 0, 1])
    told = await final_segments(db_session, session.id)
    analyst.readings = [{"findings": [{"kind": "addition", "note": "Rute foi junto", "chunk": 2}]}]
    await press_terminei(client, session.id, report=played_every_part([part.id for part in parts]))

    await _tell(client, session.id, parts[1].id, starts_ms=0, ends_ms=1000)

    assert await _findings_of_the_read(client, session.id) == [
        {"kind": "addition", "frase": 3, "segment_id": told[1].id}
    ], "o achado seguia dizendo a frase 2 depois que uma fala anterior na leitura passou na frente"


async def test_the_check_that_could_not_read_answers_the_frase_the_session_read_serves(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_bucket_is_in_memory(monkeypatch)
    the_transcriber_says(monkeypatch, ["a segunda parte, contada de volta"])
    session, parts = await rehearsed_in_parts_of(db_session, [1, 0, 1])
    told = await final_segments(db_session, session.id)
    analyst.readings = [
        {"findings": [{"kind": "addition", "note": "Rute foi junto", "chunk": 2}]},
        {"findings": "nada"},
    ]
    await press_terminei(client, session.id, report=played_every_part([part.id for part in parts]))
    await _tell(client, session.id, parts[1].id, starts_ms=0, ends_ms=1000)

    again = await _finish(client, db_session, session.id)

    assert again.status_code == 200, again.text
    assert again.json()["used_fail_safe"] is True
    expected = [{"kind": "addition", "frase": 3, "segment_id": told[1].id}]
    assert again.json()["findings"] == expected, (
        "a conferência que não pôde ler devolvia a frase 2, e a leitura da sessão dizia a 3"
    )
    assert await _findings_of_the_read(client, session.id) == expected


async def test_a_missing_element_after_frase_two_follows_frase_twos_stretch_not_its_pointer(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 4)
    told = await final_segments(db_session, session.id)
    analyst.readings = [
        {
            "findings": [
                {"kind": "missing", "note": "a notícia do pão", "chunk": 2, "where": "after"}
            ]
        }
    ]
    await _finish(client, db_session, session.id)
    assert await _findings_of_the_read(client, session.id) == [
        {"kind": "missing", "frase": 2, "segment_id": told[2].id}
    ]

    await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{told[0].id}/divide",
        headers={"X-Room-Device": TABLET},
        json={"at_ms": PART_MS // 2},
    )

    assert await _findings_of_the_read(client, session.id) == [
        {"kind": "missing", "frase": 1, "segment_id": told[2].id}
    ], "o achado depois da frase 2 passou a dizer a frase do trecho para onde aponta"


async def test_a_finding_whose_numbered_stretch_was_told_again_keeps_its_stretch_not_its_frase(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_bucket_is_in_memory(monkeypatch)

    async def heard(*_: object, **__: object) -> str:
        return "Rute disse que iria aonde Noemi fosse."

    monkeypatch.setattr(segments_api, "heard", heard)
    session, _parts = await rehearsed_in_parts(db_session, 4)
    told = await final_segments(db_session, session.id)
    analyst.readings = [
        {
            "findings": [
                {"kind": "missing", "note": "a notícia do pão", "chunk": 2, "where": "after"}
            ]
        }
    ]
    await _finish(client, db_session, session.id)

    replaced = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{told[1].id}/replace",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": told[1].take_id,
            "starts_ms": str(told[1].starts_ms),
            "ends_ms": str(told[1].ends_ms),
        },
        files={"file": ("de-novo.m4a", b"a frase dois traduzida de novo", "audio/mp4")},
    )

    assert replaced.status_code == 200, replaced.text
    assert await _findings_of_the_read(client, session.id) == [
        {"kind": "missing", "frase": None, "segment_id": told[2].id}
    ], "o achado seguia numerado por uma frase que a equipe já tinha traduzido de novo"


async def test_a_number_past_the_end_of_the_reading_the_analyst_was_shown_is_served_as_stored(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 4)
    told = await final_segments(db_session, session.id)
    analyst.readings = [
        {"findings": [{"kind": "unclear", "note": "não deu para ouvir", "chunk": 4}]}
    ]
    await _finish(client, db_session, session.id)
    stored = await get_session(db_session, session.id)
    state = dict(stored.back_translation)
    state["analysed_segment_ids"] = [told[0].id, told[1].id]
    stored.back_translation = state
    await db_session.commit()

    assert await _findings_of_the_read(client, session.id) == [
        {"kind": "unclear", "frase": 4, "segment_id": told[3].id}
    ], "o registro da leitura era mais curto que o número do achado e a leitura da sessão caía"


async def test_a_part_recorded_again_while_the_analyst_reads_is_numbered_off_what_stands(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, parts = await rehearsed_in_parts(db_session, 4)
    told = await final_segments(db_session, session.id)
    analyst.readings = [{"findings": [{"kind": "addition", "note": "Rute foi junto", "chunk": 4}]}]

    async def _the_team_records_part_1_again() -> None:
        await record_the_part_again(db_session, session, parts[0], sha256="f" * 64)

    analyst.on_reading = _the_team_records_part_1_again

    answered = await press_terminei(
        client, session.id, report=played_every_part([part.id for part in parts])
    )

    assert answered.status_code == 200, answered.text
    expected = [{"kind": "addition", "frase": 3, "segment_id": told[3].id}]
    assert answered.json()["findings"] == expected, (
        "a resposta numerava pela leitura com que a conferência abriu, e a primeira parte"
        " gravada de novo durante a leitura já não contava"
    )
    assert await _findings_of_the_read(client, session.id) == expected
