"""ENG-1419 — a part counts as heard under her rule: at most 0.75 s unheard in total.

Her rule (src/backtranslation/heard.ts:22-38 and store.ts at 18fa7c4): played stretches 0.25 s
or less apart are joined as one, and a part is heard when what is left unplayed adds up to at
most 0.75 s and never more than half the part. The same rule decides a sentence laid into a
part. Listening is counted per take, and reports add up, so a later report never takes away a
part an earlier one heard.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSession, IRTake
from app.models.internalization_room import PlayedTake
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    unheard_parts,
)
from app.services.internalization_room.segments import capture_segment
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    report_playback,
    save_back_translation,
)
from tests.release_harness import PREFIX, ensaio_take
from tests.room_harness import (
    PART_MS,
    PLAYBACK_BLOCKER,
    played_every_part,
    press_terminei,
    record_the_part_again,
    rehearsed_in_parts,
    release_blockers,
    release_packet,
    room_client,
    tell_back_about,
    the_analyst_reads,
    the_room_speaks,
)

TEN_SECONDS = 10000


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> None:
    the_analyst_reads(monkeypatch)


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


def _entry(take_id: str, played: list[list[int]], length_ms: int = PART_MS) -> dict[str, Any]:
    return {"take_id": take_id, "played_ranges": played, "clip_duration_ms": length_ms}


def _heard(played: list[list[int]], length_ms: int) -> bool:
    state = BackTranslationState(played_by_take=[_entry("parte", played, length_ms)])
    return unheard_parts(state, [IRTake(id="parte")], []) == []


def _with_holes(length_ms: int, holes: int, hole_ms: int) -> list[list[int]]:
    step = length_ms // holes
    return [[at, at + step - hole_ms] for at in range(0, step * holes, step)]


async def _a_part_measured_at(db: AsyncSession, part: IRTake, length_ms: int) -> None:
    part.duration_ms = length_ms
    await db.commit()


async def _a_part_never_told(db: AsyncSession) -> tuple[IRSession, IRTake]:
    session, _ = await rehearsed_in_parts(db, 0)
    part = ensaio_take(
        session.id, scope="parte-1", ordinal=1, sha256="d" * 64, project_id=session.project_id
    )
    db.add(part)
    await db.commit()
    return session, part


async def _told_to(db: AsyncSession, session: IRSession, part: IRTake, ends_ms: int) -> None:
    await capture_segment(
        db,
        session,
        take_id=part.id,
        starts_ms=0,
        ends_ms=ends_ms,
        bridge_take_id="retro-1",
        transcript="a parte contada de volta",
    )


async def _a_part_told_to(db: AsyncSession, ends_ms: int) -> tuple[IRSession, IRTake]:
    session, part = await _a_part_never_told(db)
    await _told_to(db, session, part, ends_ms)
    return session, part


async def _the_door_says(client: httpx.AsyncClient, session_id: str) -> list[str]:
    answered = await client.post(f"{PREFIX}/sessions/{session_id}/back-translation/listened-whole")
    assert answered.status_code == 200, answered.text
    return answered.json()["unheard_take_ids"]


async def _listened(
    client: httpx.AsyncClient, session_id: str, *entries: dict[str, Any]
) -> httpx.Response:
    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/listened-whole",
        json={"played_by_take": list(entries)},
    )
    assert answered.status_code == 200, answered.text
    return answered


EIGHT_HOLES_OF_SEVEN_TENTHS = [
    [0, 500],
    [1200, 1700],
    [2400, 2900],
    [3600, 4100],
    [4800, 5300],
    [6000, 6500],
    [7200, 7700],
    [8400, 8900],
    [9600, 10000],
]


def test_a_ten_second_part_with_eight_holes_of_seven_tenths_of_a_second_is_not_heard() -> None:
    assert not _heard(EIGHT_HOLES_OF_SEVEN_TENTHS, TEN_SECONDS)


def test_a_ten_second_part_with_one_hole_of_six_tenths_of_a_second_is_heard() -> None:
    assert _heard([[0, 4000], [4600, 10000]], TEN_SECONDS)


def test_a_one_second_part_with_three_tenths_played_is_not_heard_and_with_six_tenths_is() -> None:
    assert not _heard([[0, 300]], 1000), "metade da parte por ouvir passava como ouvida"
    assert _heard([[0, 600]], 1000)


def test_two_played_stretches_two_tenths_of_a_second_apart_leave_no_unheard_gap_between_them() -> (
    None
):
    five_stretches_two_tenths_apart = [
        [0, 1840],
        [2040, 3880],
        [4080, 5920],
        [6120, 7960],
        [8160, 10000],
    ]

    assert _heard(five_stretches_two_tenths_apart, TEN_SECONDS)


def test_stretches_more_than_a_quarter_of_a_second_apart_leave_their_gap_unheard() -> None:
    three_gaps_of_260 = [[0, 2305], [2565, 4870], [5130, 7435], [7695, 10000]]
    four_gaps_of_250 = [[0, 1800], [2050, 3850], [4100, 5900], [6150, 7950], [8200, 10000]]

    assert not _heard(three_gaps_of_260, TEN_SECONDS)
    assert _heard(four_gaps_of_250, TEN_SECONDS), "um vão de exatamente 0,25 s não era unido"


def test_unheard_time_adds_up_wherever_it_falls() -> None:
    assert not _heard([[400, 9600]], TEN_SECONDS)


def test_the_allowance_is_absolute_never_a_percentage() -> None:
    four_minutes = 240000

    assert not _heard([[0, four_minutes - 12000]], four_minutes)
    assert _heard([[0, four_minutes - 750]], four_minutes)


def test_a_part_with_nothing_played_or_with_no_length_is_not_heard() -> None:
    assert not _heard([], TEN_SECONDS)
    assert not _heard([[0, TEN_SECONDS]], 0)


def test_a_sentence_laid_into_a_part_is_heard_under_the_same_rule() -> None:
    def unheard(played: list[list[int]]) -> list[str]:
        state = BackTranslationState(
            played_by_take=[_entry("parte-nova", played, 5000)],
            sentences=[
                {
                    "sentence_id": "sentence-0001",
                    "segment_id": "frase",
                    "previous_take_id": "parte",
                    "take_id": "parte-nova",
                    "starts_ms": 1000,
                    "ends_ms": 4000,
                    "sha256": "f" * 64,
                    "storage_key": "frases/1",
                    "heard_before": True,
                }
            ],
        )
        return unheard_parts(state, [IRTake(id="parte-nova")], [])

    five_stretches_two_tenths_apart = [
        [1000, 1440],
        [1640, 2080],
        [2280, 2720],
        [2920, 3360],
        [3560, 4000],
    ]
    two_holes_of_four_tenths = [[1000, 1800], [2200, 3200], [3600, 4000]]

    assert unheard(five_stretches_two_tenths_apart) == []
    assert unheard(two_holes_of_four_tenths) == ["parte-nova"]


async def test_a_later_report_that_names_fewer_parts_keeps_the_parts_heard_before(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (a, b, c, d) = await rehearsed_in_parts(db_session, 4)

    await _listened(client, session.id, _entry(a.id, [[0, PART_MS]]), _entry(b.id, [[0, PART_MS]]))
    await _listened(client, session.id, _entry(c.id, [[0, PART_MS]]), _entry(d.id, [[0, PART_MS]]))
    finished = await press_terminei(client, session.id)

    assert finished.status_code == 200, finished.text
    assert finished.json()["refusal"] is None, "o relato seguinte apagava as partes já ouvidas"
    assert (await release_packet(db_session, session))["readiness"] == "ready_for_refine"


async def test_a_part_heard_in_two_halves_over_two_reports_is_heard(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (a,) = await rehearsed_in_parts(db_session, 1)
    half = PART_MS // 2

    first = await _listened(client, session.id, _entry(a.id, [[0, half]]))
    second = await _listened(client, session.id, _entry(a.id, [[half, PART_MS]]))

    assert first.json()["unheard_take_ids"] == [a.id]
    assert second.json()["unheard_take_ids"] == []


async def test_listening_to_a_part_recorded_again_is_not_carried_to_its_new_take(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, parts = await rehearsed_in_parts(db_session, 3)
    await _listened(client, session.id, *played_every_part(p.id for p in parts)["played_by_take"])

    fresh = await record_the_part_again(db_session, session, parts[0], sha256="e" * 64)
    answered = await _listened(client, session.id)

    assert answered.json()["unheard_take_ids"] == [fresh.id]


async def test_the_packet_carries_the_listening_to_the_current_parts_only(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (a, b, c) = await rehearsed_in_parts(db_session, 3)
    await _listened(client, session.id, *played_every_part([a.id, b.id, c.id])["played_by_take"])
    fresh = await record_the_part_again(db_session, session, a, sha256="e" * 64)
    await tell_back_about(db_session, session, fresh, bridge_take_id="retro-de-novo")
    await _listened(client, session.id, _entry(fresh.id, [[0, PART_MS]]))
    assert (await press_terminei(client, session.id)).json()["refusal"] is None

    packet = await release_packet(db_session, session)

    assert sorted(
        entry["take_id"] for entry in packet["back_translation"]["played_by_take"]
    ) == sorted([fresh.id, b.id, c.id]), "o pacote levava a escuta de uma parte aposentada"


async def test_a_part_is_heard_against_its_take_s_measured_length_whatever_a_report_says(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, a = await _a_part_told_to(db_session, 1000)
    await _a_part_measured_at(db_session, a, PART_MS)

    await _listened(client, session.id, _entry(a.id, [[0, 1]], 1))
    answered = await _listened(client, session.id, _entry(a.id, [[0, 2000]], PART_MS))
    finished = await press_terminei(client, session.id)

    assert answered.json()["unheard_take_ids"] == [a.id], (
        "um comprimento curto relatado abria a parte com 2 s de 61 tocados"
    )
    assert finished.json()["refusal"] == "PART_UNHEARD"


async def test_a_part_with_no_measured_length_is_never_shorter_than_its_told_end(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, part = await _a_part_told_to(db_session, 5000)

    answered = await _listened(client, session.id, _entry(part.id, [[0, 4000]], 4000))

    assert answered.json()["unheard_take_ids"] == [part.id], (
        "a parte passava como ouvida contra um comprimento menor que a frase contada nela"
    )


async def test_a_short_length_reported_before_anything_was_told_never_opens_the_part(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, part = await _a_part_never_told(db_session)
    await _listened(client, session.id, _entry(part.id, [[0, 1]], 1))
    await _listened(client, session.id, _entry(part.id, [[0, 2000]], PART_MS))

    await _told_to(db_session, session, part, PART_MS)
    finished = await press_terminei(client, session.id)

    assert finished.json()["refusal"] == "PART_UNHEARD", (
        "a parte passava com 2 s de 61 tocados porque o comprimento curto ficou guardado"
    )
    assert await _the_door_says(client, session.id) == [part.id]


async def test_a_length_stored_before_this_rule_is_read_against_the_take_s_measured_length(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (a,) = await rehearsed_in_parts(db_session, 1)
    await _a_part_measured_at(db_session, a, PART_MS)
    state = back_translation_of(session)
    state.played_by_take = [PlayedTake(**_entry(a.id, [[0, 2000]], 2000))]
    await save_back_translation(db_session, session, state)

    finished = await press_terminei(client, session.id)

    assert finished.json()["refusal"] == "PART_UNHEARD"
    assert await _the_door_says(client, session.id) == [a.id]
    assert PLAYBACK_BLOCKER in await release_blockers(db_session, session)


async def test_a_report_landing_beside_another_never_restores_a_short_length(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    session, (a, b) = await rehearsed_in_parts(db_session, 2)
    await _a_part_measured_at(db_session, a, PART_MS)
    state = back_translation_of(session)
    state.played_by_take = [PlayedTake(**_entry(a.id, [[0, 2000]], 2000))]
    await save_back_translation(db_session, session, state)
    async with rival_factory() as flat_db, rival_factory() as parts_db:
        flat = await get_session(flat_db, session.id)
        named = await get_session(parts_db, session.id)
        flat_state, named_state = back_translation_of(flat), back_translation_of(named)
        await report_playback(
            flat_db,
            flat,
            flat_state,
            played_by_take=[],
            played_ranges=[(0, PART_MS)],
            clip_duration_ms=PART_MS,
        )
        await report_playback(
            parts_db,
            named,
            named_state,
            played_by_take=[PlayedTake(**_entry(b.id, [[0, PART_MS]]))],
            played_ranges=[],
            clip_duration_ms=None,
        )
    await db_session.refresh(session)

    assert await _the_door_says(client, session.id) == [a.id], (
        "a escrita concorrente devolvia o comprimento curto e a parte passava com 2 s tocados"
    )


async def test_a_part_with_no_measured_length_is_heard_against_the_longest_length_reported(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, part = await _a_part_told_to(db_session, 5000)
    played = [[0, 8000]]

    first = await _listened(client, session.id, _entry(part.id, played, 8500))
    not_measured = await _listened(client, session.id, _entry(part.id, [], 0))
    longer = await _listened(client, session.id, _entry(part.id, played, 9000))
    shorter_again = await _listened(client, session.id, _entry(part.id, played, 8500))

    assert first.json()["unheard_take_ids"] == []
    assert not_measured.json()["unheard_take_ids"] == [], "um zero valia como comprimento"
    assert longer.json()["unheard_take_ids"] == [part.id]
    assert shorter_again.json()["unheard_take_ids"] == [part.id], (
        "uma medida mais curta depois da mais longa abria a parte"
    )


async def test_a_part_reported_with_no_length_is_heard_against_its_told_end(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, part = await _a_part_told_to(db_session, PART_MS)

    answered = await _listened(client, session.id, _entry(part.id, [[0, PART_MS]], 0))

    assert answered.json()["unheard_take_ids"] == [], (
        "a parte tocada até o fim contado ficava não ouvida porque o relato não trazia comprimento"
    )


async def test_the_listen_door_stores_the_report_and_answers_which_parts_are_still_unheard(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (a, b, c) = await rehearsed_in_parts(db_session, 3)

    first = await _listened(
        client,
        session.id,
        _entry(a.id, [[0, PART_MS]]),
        _entry(b.id, _with_holes(PART_MS, 8, 700)),
    )
    second = await _listened(client, session.id, _entry(b.id, [[0, PART_MS]]))
    finished = await press_terminei(client, session.id)

    assert first.json()["unheard_take_ids"] == sorted([b.id, c.id])
    assert first.json()["automatic_check"] is False
    assert first.json()["refusal"] is None
    assert second.json()["unheard_take_ids"] == [c.id]
    assert finished.json()["refusal"] == "PART_UNHEARD"
    assert finished.json()["unheard_take_ids"] == [c.id]


async def test_two_reports_landing_together_keep_the_listening_each_one_brought(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session, (a, b) = await rehearsed_in_parts(db_session, 2)
    async with rival_factory() as first_db, rival_factory() as second_db:
        first = await get_session(first_db, session.id)
        second = await get_session(second_db, session.id)
        first_state, second_state = back_translation_of(first), back_translation_of(second)

        for db, read, state, part in (
            (first_db, first, first_state, a),
            (second_db, second, second_state, b),
        ):
            await report_playback(
                db,
                read,
                state,
                played_by_take=[PlayedTake(**_entry(part.id, [[0, PART_MS]]))],
                played_ranges=[],
                clip_duration_ms=None,
            )

    async with rival_factory() as fresh_db:
        stored = back_translation_of(await get_session(fresh_db, session.id))
    assert unheard_parts(stored, [a, b], []) == [], (
        "o relato que leu antes gravava por cima, e a parte ouvida pelo outro sumia"
    )
