"""ENG-1739 — a re-recorded part's stretches stay served, marked stale, for the tablet that asks.

Recording a **Part** again retires its stretches (ADR 0023), so the tablet lost them from its
list and had nothing to show the team in their place. Her app keeps them listed, marked, and
out of the check. The room still retires them — the check, the gate and the findings read the
standing stretches and nothing else — and serves them on top, only when the tablet asks.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room.segments import _units
from app.api.internalization_room.sessions import _progress
from app.db.models.auth import App
from app.db.models.internalization_room import IRSegment
from app.services.internalization_room.back_translation import (
    Finding,
    FindingKind,
    frase_numbers,
)
from app.services.internalization_room.hard_stretches import note_a_hard_stretch
from app.services.internalization_room.segments import current_segments, divide_segment
from app.services.internalization_room.sessions import (
    RETELLS_BEFORE_A_WARNING,
    back_translation_of,
    get_session,
    save_back_translation,
)
from tests.baker import make_app, make_role
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    TABLET,
    a_claimed_device,
    at_the_desk,
    session_retro,
    team_headers,
)
from tests.room_harness import (
    PART_MS,
    a_piece_still_to_be_told,
    played_every_part,
    press_terminei,
    rehearsed_in_parts,
    rehearsed_in_parts_of,
    release_blockers,
    room_client,
    the_analyst_is_scripted,
    the_bucket_is_in_memory,
    the_room_speaks,
    the_transcriber_says,
    upload_a_part,
)
from tests.sentence_harness import rehearsed_in_wav, spoken

NEW_AUDIO = b"a equipe gravou esta parte outra vez"
RETELLING = b"a equipe contou a parte regravada"


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    the_room_speaks(monkeypatch)


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    from app.api.internalization_room import segments as segments_api

    async def _heard(*_: Any, **__: Any) -> str:
        return "a parte contada de novo"

    monkeypatch.setattr(segments_api, "heard", _heard)
    the_transcriber_says(monkeypatch, [])
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _tell_again(
    client: httpx.AsyncClient,
    session_id: str,
    segment_id: str,
    *,
    take_id: str,
    starts_ms: int = 0,
    ends_ms: int = PART_MS,
    params: dict[str, str] | None = None,
    audio: bytes = RETELLING,
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment_id}/replace",
        headers={"X-Room-Device": TABLET},
        params=params,
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("de-novo.m4a", audio, "audio/mp4")},
    )


async def _read_asking_for_stale(client: httpx.AsyncClient, session_id: str) -> list[dict]:
    read = await client.get(f"{PREFIX}/sessions/{session_id}", params={"include_stale": "true"})
    assert read.status_code == 200, read.text
    return read.json()["back_translation"]["segments"]


async def test_a_part_recorded_again_keeps_its_earlier_stretch_listed_stale_for_a_tablet_that_asks(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}

    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    segments = await _read_asking_for_stale(client, session.id)

    assert [(row["segment_id"], row["stale"]) for row in segments] == [
        (by_part[one.id], False),
        (by_part[three.id], False),
        (by_part[two.id], True),
    ], "a parte regravada sumia da lista da tablet em vez de ficar marcada como regravada"


async def test_a_stretch_the_team_divided_is_served_as_its_pieces_and_not_as_itself(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (_one, two, _three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row for row in await current_segments(db_session, session.id)}
    head, tail = await divide_segment(db_session, session, by_part[two.id], at_ms=PART_MS // 2)

    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    stale = [row for row in await _read_asking_for_stale(client, session.id) if row["stale"]]

    assert [row["segment_id"] for row in stale] == [head.id, tail.id], (
        "o trecho cortado voltava inteiro, além das duas partes em que a equipe o tinha cortado"
    )


async def test_the_stale_stretches_follow_the_order_of_the_passage_not_the_order_they_went(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (_one, two, three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}

    for part in (3, 2):
        again = await upload_a_part(client, session.id, part=part, audio=NEW_AUDIO + bytes([part]))
        assert again.status_code == 200, again.text

    stale = [row for row in await _read_asking_for_stale(client, session.id) if row["stale"]]

    assert [row["segment_id"] for row in stale] == [by_part[two.id], by_part[three.id]], (
        "as regravadas voltavam na ordem em que foram regravadas, não na ordem da passagem"
    )


async def test_the_stale_stretches_of_a_whole_recording_leave_when_the_team_records_by_scene(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (_whole,) = await rehearsed_in_parts_of(db_session, [3], told_whole=True)
    told = [row.id for row in await current_segments(db_session, session.id)]
    again = await upload_a_part(client, session.id, part=None, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text
    asked = await _read_asking_for_stale(client, session.id)
    assert [row["segment_id"] for row in asked if row["stale"]] == told, (
        "o ensaio inteiro regravado devia continuar listado enquanto ainda é uma parte"
    )

    scene = await upload_a_part(client, session.id, part=1, audio=NEW_AUDIO + b"1")
    assert scene.status_code == 200, scene.text

    assert [
        row for row in await _read_asking_for_stale(client, session.id) if row["stale"]
    ] == [], "o ensaio inteiro já era história quando a equipe passou a gravar por cena"


async def test_a_translation_started_over_leaves_no_stale_stretch_to_serve(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text
    assert [row for row in await _read_asking_for_stale(client, session.id) if row["stale"]]

    restarted = await client.post(f"{PREFIX}/sessions/{session.id}/back-translation/restart")
    assert restarted.status_code == 200, restarted.text

    assert await _read_asking_for_stale(client, session.id) == [], (
        "a tradução recomeçada continuava listando a parte regravada antes do recomeço"
    )


async def test_telling_a_stale_stretch_again_replaces_it_and_the_marker_goes(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    told = await _tell_again(client, session.id, by_part[two.id], take_id=again.json()["take_id"])

    assert told.status_code == 200, told.text
    standing = await _read_asking_for_stale(client, session.id)
    assert [(row["take_id"], row["stale"], row["frase"]) for row in standing] == [
        (one.id, False, 1),
        (again.json()["take_id"], False, 2),
        (three.id, False, 3),
    ], "a parte contada de novo continuava marcada como regravada, ou não ocupava o seu lugar"
    old = (
        await db_session.execute(
            select(IRSegment)
            .where(IRSegment.id == by_part[two.id])
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert old.stale is False and old.superseded_by_id is None, (
        "a linha regravada continuava marcada, ou ganhou um sucessor que nunca teve"
    )


async def test_a_stale_stretch_is_told_again_only_over_the_recording_its_part_stands_on(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (one, two, _three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    for elsewhere in (two.id, one.id):
        refused = await _tell_again(client, session.id, by_part[two.id], take_id=elsewhere)

        assert refused.status_code == 400, (
            "a parte regravada aceitou ser contada de novo sobre uma gravação que não é a dela"
        )

    stale = [row for row in await _read_asking_for_stale(client, session.id) if row["stale"]]
    assert [row["segment_id"] for row in stale] == [by_part[two.id]]


async def test_a_stale_stretch_of_a_whole_that_stepped_aside_is_not_told_again(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts_of(db_session, [1], told_whole=True)
    told = (await current_segments(db_session, session.id))[0]
    again = await upload_a_part(client, session.id, part=None, audio=NEW_AUDIO)
    scene = await upload_a_part(client, session.id, part=1, audio=NEW_AUDIO + b"1")
    assert again.status_code == scene.status_code == 200

    refused = await _tell_again(client, session.id, told.id, take_id=scene.json()["take_id"])

    assert refused.status_code == 400, (
        "o ensaio inteiro já era história e aceitou ser contado de novo sobre uma cena"
    )


async def test_dividing_a_stretch_answers_with_the_stale_ones_to_a_tablet_that_asks(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    divided = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{by_part[one.id]}/divide",
        headers={"X-Room-Device": TABLET},
        params={"include_stale": "true"},
        json={"at_ms": PART_MS // 2},
    )

    assert divided.status_code == 200, divided.text
    answered = divided.json()["segments"]
    assert [(row["take_id"], row["stale"]) for row in answered] == [
        (one.id, False),
        (one.id, False),
        (three.id, False),
        (two.id, True),
    ], "a divisão respondia sem a parte regravada e a tablet a apagava da lista"


async def test_telling_a_stretch_again_answers_with_the_stale_ones_to_a_tablet_that_asks(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    told = await _tell_again(
        client,
        session.id,
        by_part[one.id],
        take_id=one.id,
        params={"include_stale": "true"},
    )

    assert told.status_code == 200, told.text
    assert [(row["take_id"], row["stale"]) for row in told.json()["segments"]] == [
        (one.id, False),
        (three.id, False),
        (two.id, True),
    ], "a nova contagem respondia sem a parte regravada e a tablet a apagava da lista"


async def test_laying_a_sentence_in_answers_with_the_stale_ones_to_a_tablet_that_asks(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _takes, (part_one, part_two) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)], [(0, 2000)]]
    )
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    laid = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{part_one[1].id}/sentence",
        params={"include_stale": "true"},
        data={"sentence_id": "sentence-0001"},
        files={"file": ("frase.wav", spoken(1.0), "audio/wav")},
    )

    assert laid.status_code == 200, laid.text
    answered = laid.json()["segments"]
    assert [row["stale"] for row in answered] == [False, False, False, True]
    assert answered[-1]["segment_id"] == part_two[0].id, (
        "a frase gravada de novo respondia sem a parte regravada e a tablet a apagava da lista"
    )


THE_KEYS_OF_A_STRETCH = {
    "segment_id",
    "take_id",
    "starts_ms",
    "ends_ms",
    "pass_number",
    "told",
    "bridge_take_id",
    "frase",
}


def _only_what_counts(rows: list[dict], expected_takes: list[str]) -> None:
    assert [row["take_id"] for row in rows] == expected_takes, (
        "uma tablet que não pediu recebeu a parte regravada na lista"
    )
    assert all(set(row) == THE_KEYS_OF_A_STRETCH for row in rows), (
        "uma tablet que não pediu recebeu uma chave nova em cada trecho"
    )


async def test_the_session_read_without_asking_is_the_list_it_always_was(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (one, _two, three) = await rehearsed_in_parts(db_session, 3)
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    read = await client.get(f"{PREFIX}/sessions/{session.id}")

    assert read.status_code == 200, read.text
    rows = read.json()["back_translation"]["segments"]
    _only_what_counts(rows, [one.id, three.id])
    assert [row["frase"] for row in rows] == [1, 2]


async def test_a_division_without_asking_answers_the_list_it_always_did(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (one, _two, three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    divided = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{by_part[one.id]}/divide",
        headers={"X-Room-Device": TABLET},
        json={"at_ms": PART_MS // 2},
    )

    assert divided.status_code == 200, divided.text
    _only_what_counts(divided.json()["segments"], [one.id, one.id, three.id])


async def test_a_retelling_without_asking_answers_the_list_it_always_did(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (one, _two, three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    told = await _tell_again(client, session.id, by_part[one.id], take_id=one.id)

    assert told.status_code == 200, told.text
    _only_what_counts(told.json()["segments"], [one.id, three.id])


async def test_a_sentence_laid_in_without_asking_answers_the_list_it_always_did(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _takes, (part_one, _part_two) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)], [(0, 2000)]]
    )
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    laid = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{part_one[1].id}/sentence",
        data={"sentence_id": "sentence-0001"},
        files={"file": ("frase.wav", spoken(1.0), "audio/wav")},
    )

    assert laid.status_code == 200, laid.text
    rows = laid.json()["segments"]
    assert len(rows) == 3, "uma tablet que não pediu recebeu a parte regravada na lista"
    assert all(set(row) == THE_KEYS_OF_A_STRETCH for row in rows), (
        "uma tablet que não pediu recebeu uma chave nova em cada trecho"
    )


async def test_a_stale_stretch_is_numbered_in_its_place_and_the_standing_ones_after_it(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    asked = await _read_asking_for_stale(client, session.id)

    assert [(row["stale"], row["frase"]) for row in asked] == [
        (False, 1),
        (False, 3),
        (True, 2),
    ], "a parte regravada ficava sem número, ou as frases depois dela perdiam o seu"


async def test_the_stale_frases_of_a_part_recorded_again_never_repeat_a_standing_number(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts_of(db_session, [1, 4, 1])
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    asked = await _read_asking_for_stale(client, session.id)

    assert [(row["stale"], row["frase"]) for row in asked] == [
        (False, 1),
        (False, 6),
        (True, 2),
        (True, 3),
        (True, 4),
        (True, 5),
    ], "uma frase velha chegava sem número ou repetia o de uma que está de pé"


def test_a_stale_frase_of_a_take_with_no_number_reads_before_the_standing_ones_of_part_zero() -> (
    None
):
    whole = IRSegment(id="whole", take_id="take-whole")
    zero = IRSegment(id="zero", take_id="take-zero")

    numbers = frase_numbers([zero], [whole], {"take-whole": None, "take-zero": 0})

    assert numbers == {"whole": 1, "zero": 2}, (
        "um take sem número e a parte 0 ficavam na mesma posição, e a de pé passava à frente"
    )


async def test_asking_for_the_stale_ones_reads_the_takes_of_the_session_once(
    db_session: AsyncSession, test_engine
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 2)
    said: list[str] = []

    def _heard(_conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        said.append(statement)

    event.listen(test_engine.sync_engine, "before_cursor_execute", _heard)
    try:
        await _units(db_session, session.id, include_stale=True)
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _heard)

    assert len([one for one in said if "FROM ir_takes" in one]) == 1, (
        "a leitura que a tablet refaz a lista lia os takes da sessão duas vezes"
    )


async def _takes_reads_of(test_engine, read: Any) -> int:
    said: list[str] = []

    def _heard(_conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        said.append(statement)

    event.listen(test_engine.sync_engine, "before_cursor_execute", _heard)
    try:
        await read()
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _heard)
    return len([one for one in said if "FROM ir_takes" in one])


async def test_the_progress_asking_for_the_stale_ones_reads_no_more_takes_than_without(
    db_session: AsyncSession, test_engine
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 2)

    plain = await _takes_reads_of(test_engine, lambda: _progress(db_session, session))
    asking = await _takes_reads_of(
        test_engine, lambda: _progress(db_session, session, include_stale=True)
    )

    assert asking == plain, "a sessão que pede as regravadas lia os takes uma vez a mais"


async def test_the_check_neither_reads_nor_waits_on_a_stale_stretch(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    analyst = the_analyst_is_scripted(monkeypatch)
    session, (one, _two, three) = await rehearsed_in_parts(db_session, 3)
    standing = await current_segments(db_session, session.id)
    await a_piece_still_to_be_told(db_session, session, standing[1])
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text
    assert [row for row in await _read_asking_for_stale(client, session.id) if row["stale"]]

    answered = await press_terminei(
        client,
        session.id,
        report=played_every_part([one.id, again.json()["take_id"], three.id]),
    )

    assert answered.status_code == 200, answered.text
    assert len(analyst.shown) == 1, (
        "o terminei esperou por um trecho da parte regravada em vez de ler o que conta"
    )
    assert "parte 0 contada de volta" in analyst.shown[0]
    assert "parte 2 contada de volta" in analyst.shown[0]
    assert "a primeira metade contada de volta" not in analyst.shown[0]
    assert "parte 1 contada de volta" not in analyst.shown[0]


async def test_the_release_gate_does_not_count_a_stale_stretch(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    standing = await current_segments(db_session, session.id)
    await a_piece_still_to_be_told(db_session, session, standing[1])
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text
    assert [row for row in await _read_asking_for_stale(client, session.id) if row["stale"]]

    blockers = await release_blockers(db_session, session)

    assert "untold_stretch" not in blockers, (
        "a liberação esperava pelo trecho por contar de uma parte que a equipe já regravou"
    )


async def test_a_finding_on_a_stale_stretch_is_never_served(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (_one, two, _three) = await rehearsed_in_parts(db_session, 3)
    stale = {row.take_id: row.id for row in await current_segments(db_session, session.id)}[two.id]
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text
    fresh = await get_session(db_session, session.id)
    state = back_translation_of(fresh)
    state.findings = [
        Finding(kind=FindingKind.UNCLEAR, note="nao deu para ouvir", segment_id=stale)
    ]
    await save_back_translation(db_session, fresh, state)

    for params in ({}, {"include_stale": "true"}):
        read = await client.get(f"{PREFIX}/sessions/{session.id}", params=params)

        progress = read.json()["back_translation"]
        assert progress["findings"] == [], "a tablet era mandada a um trecho que já não conta"
        assert progress["finding_segment_id"] is None


async def test_two_stale_stretches_of_one_part_are_not_both_told_over_the_same_slice(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (_one, two, _three) = await rehearsed_in_parts(db_session, 3)
    first = {row.take_id: row.id for row in await current_segments(db_session, session.id)}[two.id]
    second_take = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert second_take.status_code == 200, second_take.text
    told_on_second = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/chunks",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": second_take.json()["take_id"],
            "starts_ms": "0",
            "ends_ms": str(PART_MS),
        },
        files={"file": ("contada.m4a", RETELLING, "audio/mp4")},
    )
    assert told_on_second.status_code == 200, told_on_second.text
    third_take = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO + b"3")
    assert third_take.status_code == 200, third_take.text
    stale = [row for row in await _read_asking_for_stale(client, session.id) if row["stale"]]
    assert len(stale) == 2, "the part recorded three times serves the stretch of each earlier take"
    over = third_take.json()["take_id"]

    again = await _tell_again(client, session.id, first, take_id=over)
    assert again.status_code == 200, again.text
    twice = await _tell_again(
        client, session.id, stale[1]["segment_id"], take_id=over, audio=RETELLING + b"outra"
    )

    assert twice.status_code == 400, twice.text
    standing = await client.get(f"{PREFIX}/sessions/{session.id}")
    at_that_slice = [
        row
        for row in standing.json()["back_translation"]["segments"]
        if (row["take_id"], row["starts_ms"], row["ends_ms"]) == (over, 0, PART_MS)
    ]
    assert len(at_that_slice) == 1, "dois trechos ficaram de pé no mesmo lugar da mesma gravação"


@pytest.fixture()
async def room_app(db_session: AsyncSession) -> App:
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def test_telling_a_stale_stretch_again_leaves_the_file_as_it_was(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app: App
) -> None:
    project, credential = await a_claimed_device(db_session)
    client.headers.update(team_headers(credential))
    session, (_one, two, _three) = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    stale = {row.take_id: row.id for row in await current_segments(db_session, session.id)}[two.id]
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text

    told = await _tell_again(client, session.id, stale, take_id=again.json()["take_id"])

    assert told.status_code == 200, told.text
    desk, _user = await at_the_desk(db_session, room_app, project)
    filed = await session_retro(client, session.id, desk)
    assert filed.status_code == 200, filed.text
    file = filed.json()
    kept = next(row for row in file["history"] if row["idx"] == stale)
    assert kept["superseded"] is False, (
        "a linha regravada saiu das abandonadas quando a equipe a contou de novo"
    )
    fresh = next(row for row in file["frases"] if row["clipKey"] == "S2")
    assert fresh["idx"] != stale
    assert "supersedes" not in fresh, "a contagem nova herdou as contagens da gravação anterior"


async def test_a_hard_stretch_marked_before_the_part_was_recorded_again_can_be_marked_anew(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (_one, two, _three) = await rehearsed_in_parts(db_session, 3)
    marked = {row.take_id: row for row in await current_segments(db_session, session.id)}[two.id]
    marked.tellings = RETELLS_BEFORE_A_WARNING
    await db_session.commit()
    assert await note_a_hard_stretch(db_session, session, marked) is True
    stale = marked.id
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text
    over = again.json()["take_id"]
    first = await _tell_again(client, session.id, stale, take_id=over)
    assert first.status_code == 200, first.text
    fresh = next(
        row["segment_id"]
        for row in (await client.get(f"{PREFIX}/sessions/{session.id}")).json()["back_translation"][
            "segments"
        ]
        if row["take_id"] == over
    )

    for index in range(RETELLS_BEFORE_A_WARNING - 1):
        retold = await _tell_again(
            client, session.id, fresh, take_id=over, audio=RETELLING + bytes([index])
        )
        assert retold.status_code == 200, retold.text
        fresh = next(
            row["segment_id"]
            for row in (await client.get(f"{PREFIX}/sessions/{session.id}")).json()[
                "back_translation"
            ]["segments"]
            if row["take_id"] == over
        )

    assert retold.json()["needs_person"] is True, (
        "a contagem nova da parte regravada nunca chamou ninguém por já haver uma marca antiga"
    )


async def test_a_divided_stretch_whose_pieces_were_both_told_again_is_not_served(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (_one, two, _three) = await rehearsed_in_parts(db_session, 3)
    parent = {row.take_id: row for row in await current_segments(db_session, session.id)}[two.id]
    head, tail = await divide_segment(db_session, session, parent, at_ms=PART_MS // 2)
    again = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text
    over = again.json()["take_id"]

    first = await _tell_again(
        client, session.id, head.id, take_id=over, starts_ms=0, ends_ms=PART_MS // 2
    )
    second = await _tell_again(
        client,
        session.id,
        tail.id,
        take_id=over,
        starts_ms=PART_MS // 2,
        ends_ms=PART_MS,
        audio=RETELLING + b"2",
    )

    assert first.status_code == second.status_code == 200, (first.text, second.text)
    assert [
        row for row in await _read_asking_for_stale(client, session.id) if row["stale"]
    ] == [], "o trecho cortado voltou inteiro depois de as suas duas partes serem contadas de novo"


async def _part_one_recorded_again_before_part_two_was_told(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> tuple[Any, str, list[str]]:
    session, (_one, two) = await rehearsed_in_parts_of(db_session, [2, 1])
    again = await upload_a_part(client, session.id, part=1, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text
    return session, again.json()["take_id"], [again.json()["take_id"], two.id]


async def test_above_a_part_recorded_again_the_analyst_reads_the_frase_number_the_tablet_draws(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    analyst = the_analyst_is_scripted(monkeypatch)
    session, _again, played = await _part_one_recorded_again_before_part_two_was_told(
        client, db_session
    )

    answered = await press_terminei(client, session.id, report=played_every_part(played))

    assert answered.status_code == 200, answered.text
    block = analyst.shown[-1]
    assert "[frase 3 — a parte 2] a frase 3, contada de volta" in block, (
        "acima de uma parte regravada a analista lia «frase 1» na linha que a tablet desenha como 3"
    )
    assert "a frase 1, contada de volta" not in block
    assert "a frase 2, contada de volta" not in block


async def test_a_finding_named_by_the_number_the_tablet_draws_lands_on_that_row(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    analyst = the_analyst_is_scripted(monkeypatch)
    session, _again, played = await _part_one_recorded_again_before_part_two_was_told(
        client, db_session
    )
    (standing,) = await current_segments(db_session, session.id)
    analyst.readings = [
        {"findings": [{"kind": "unclear", "note": "a frase 3 ficou confusa", "frase": 3}]}
    ]

    answered = await press_terminei(client, session.id, report=played_every_part(played))

    assert answered.status_code == 200, answered.text
    assert answered.json()["findings"] == [
        {"kind": "unclear", "frase": 3, "segment_id": standing.id}
    ], "o achado na frase 3 não caía em trecho nenhum: a leitura só aceitava posições até 1"


async def test_the_session_read_numbers_a_finding_as_it_numbers_the_row_it_draws(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    analyst = the_analyst_is_scripted(monkeypatch)
    session, _again, played = await _part_one_recorded_again_before_part_two_was_told(
        client, db_session
    )
    (standing,) = await current_segments(db_session, session.id)
    analyst.readings = [
        {"findings": [{"kind": "unclear", "note": "a frase 3 ficou confusa", "frase": 3}]}
    ]
    answered = await press_terminei(client, session.id, report=played_every_part(played))
    assert answered.status_code == 200, answered.text

    read = await client.get(f"{PREFIX}/sessions/{session.id}", params={"include_stale": "true"})

    assert read.status_code == 200, read.text
    rows = {row["segment_id"]: row["frase"] for row in read.json()["back_translation"]["segments"]}
    assert rows[standing.id] == 3
    assert read.json()["back_translation"]["findings"] == [
        {"kind": "unclear", "frase": 3, "segment_id": standing.id}
    ], "a leitura desenhava a linha como 3 e dizia que o achado estava na frase 1"
