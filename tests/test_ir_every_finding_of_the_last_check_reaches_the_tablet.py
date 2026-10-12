from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sessions import get_session
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    Room,
    ScriptedAnalyst,
    heard_every_part,
    nothing_is_read_ahead,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    the_analyst_is_scripted,
    the_bucket_is_in_memory,
    the_room_speaks,
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


async def test_the_verdict_lists_every_finding_of_the_check_by_kind_frase_and_stretch(
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
                {"kind": "addition", "note": "Rute foi junto", "chunk": 2},
                {"kind": "unclear", "note": "não deu para ouvir", "chunk": 4},
            ]
        }
    ]

    answered = await _finish(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    assert answered.json()["findings"] == [
        {"kind": "addition", "frase": 2, "segment_id": told[1].id},
        {"kind": "unclear", "frase": 4, "segment_id": told[3].id},
    ], "o tablet só recebia o primeiro achado e não podia marcar os outros"


async def test_the_list_keeps_the_analysts_order_while_the_addition_still_leads(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    told = await final_segments(db_session, session.id)
    analyst.readings = [
        {
            "findings": [
                {"kind": "missing", "note": "a notícia do pão", "chunk": 2, "where": "inside"},
                {"kind": "addition", "note": "o pedido das noras", "chunk": 2},
            ]
        }
    ]

    answered = await _finish(client, db_session, session.id)

    body = answered.json()
    assert body["finding_kind"] == "addition"
    assert body["finding_segment_id"] == told[1].id
    assert [one["kind"] for one in body["findings"]] == ["missing", "addition"], (
        "a lista seguia a ordem da escolha da sala e não a da conferência"
    )


async def test_a_listed_finding_carries_no_word_of_the_analyst(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [
        {"findings": [{"kind": "addition", "note": "Rute foi junto sem ser chamada", "chunk": 2}]}
    ]

    answered = await _finish(client, db_session, session.id)

    (listed,) = answered.json()["findings"]
    assert set(listed) == {"kind", "frase", "segment_id"}
    assert "Rute foi junto sem ser chamada" not in answered.text, (
        "a nota da analista chegava à tela, e a sala nunca a mostra"
    )


async def test_a_finding_with_no_readable_frase_is_listed_unnumbered_and_unplaced(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [
        {
            "findings": [
                {"kind": "addition", "note": "Rute foi junto"},
                {"kind": "unclear", "note": "não deu para ouvir", "chunk": 99},
            ]
        }
    ]

    answered = await _finish(client, db_session, session.id)

    assert answered.json()["findings"] == [
        {"kind": "addition", "frase": None, "segment_id": None},
        {"kind": "unclear", "frase": None, "segment_id": None},
    ]


async def test_a_clean_check_lists_nothing(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": []}]

    answered = await _finish(client, db_session, session.id)

    assert answered.json()["checked"] is True
    assert answered.json()["findings"] == []


async def test_pressing_terminei_again_serves_the_same_list(
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
                {"kind": "addition", "note": "Rute foi junto", "chunk": 2},
                {"kind": "unclear", "note": "não deu para ouvir", "chunk": 4},
            ]
        }
    ]
    await _finish(client, db_session, session.id)

    again = await _finish(client, db_session, session.id)

    assert again.json()["findings"] == [
        {"kind": "addition", "frase": 2, "segment_id": told[1].id},
        {"kind": "unclear", "frase": 4, "segment_id": told[3].id},
    ], "a segunda vez que a equipe aperta terminei perdia os achados que a primeira listou"


async def test_a_check_that_could_not_read_leaves_the_earlier_checks_list_standing(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 4)
    told = await final_segments(db_session, session.id)
    analyst.readings = [
        {"findings": [{"kind": "addition", "note": "Rute foi junto", "chunk": 2}]},
        {"findings": "nada"},
    ]
    await _finish(client, db_session, session.id)
    stored = await get_session(db_session, session.id)
    state = dict(stored.back_translation)
    state["analysed_segment_ids"] = None
    stored.back_translation = state
    await db_session.commit()

    again = await _finish(client, db_session, session.id)

    body = again.json()
    assert body["checked"] is False
    assert body["finding_kind"] is None
    assert body["findings"] == [{"kind": "addition", "frase": 2, "segment_id": told[1].id}], (
        "uma conferência que não pôde ler apagava as marcas da anterior"
    )


async def test_the_session_read_lists_the_same_findings_as_the_verdict(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 4)
    analyst.readings = [
        {
            "findings": [
                {"kind": "addition", "note": "Rute foi junto", "chunk": 2},
                {"kind": "unclear", "note": "não deu para ouvir", "chunk": 4},
            ]
        }
    ]
    verdict = await _finish(client, db_session, session.id)

    resumed = await client.get(f"{PREFIX}/sessions/{session.id}")

    assert resumed.status_code == 200, resumed.text
    assert len(verdict.json()["findings"]) == 2
    assert resumed.json()["back_translation"]["findings"] == verdict.json()["findings"], (
        "uma equipe que voltava à sala não via de novo as marcas da última conferência"
    )


async def test_the_session_read_drops_the_mark_of_a_frase_translated_again(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_bucket_is_in_memory(monkeypatch)
    nothing_is_read_ahead(monkeypatch)

    async def heard(*_: object, **__: object) -> str:
        return "Rute disse que iria aonde Noemi fosse."

    monkeypatch.setattr(segments_api, "heard", heard)
    session, _parts = await rehearsed_in_parts(db_session, 4)
    told = await final_segments(db_session, session.id)
    analyst.readings = [
        {
            "findings": [
                {"kind": "addition", "note": "Rute foi junto", "chunk": 2},
                {"kind": "unclear", "note": "não deu para ouvir", "chunk": 4},
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
    resumed = await client.get(f"{PREFIX}/sessions/{session.id}")

    assert resumed.json()["back_translation"]["findings"] == [
        {"kind": "unclear", "frase": 4, "segment_id": told[3].id}
    ], "a marca da frase 2 voltava depois de a equipe traduzi-la de novo"
