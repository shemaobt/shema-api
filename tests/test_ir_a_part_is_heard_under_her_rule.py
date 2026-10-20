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

from app.models.internalization_room import PlayedTake
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    unheard_parts,
)
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    report_playback,
)
from tests.release_harness import PREFIX
from tests.room_harness import (
    PART_MS,
    played_every_part,
    press_terminei,
    record_the_part_again,
    rehearsed_in_parts,
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


def _heard(played: list[list[int]], length_ms: int) -> bool:
    state = BackTranslationState(
        played_by_take=[
            {"take_id": "parte", "played_ranges": played, "clip_duration_ms": length_ms}
        ]
    )
    return unheard_parts(state, ["parte"]) == []


def _entry(take_id: str, played: list[list[int]], length_ms: int = PART_MS) -> dict[str, Any]:
    return {"take_id": take_id, "played_ranges": played, "clip_duration_ms": length_ms}


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
        return unheard_parts(state, ["parte-nova"])

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


async def test_the_shortest_length_measured_for_a_take_is_the_one_it_is_heard_against(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (a,) = await rehearsed_in_parts(db_session, 1)
    played = [[0, 9000]]

    measured_long = await _listened(client, session.id, _entry(a.id, played, TEN_SECONDS))
    measured_short = await _listened(client, session.id, _entry(a.id, played, 9000))
    measured_long_again = await _listened(client, session.id, _entry(a.id, played, TEN_SECONDS))
    not_measured = await _listened(client, session.id, _entry(a.id, played, 0))

    assert measured_long.json()["unheard_take_ids"] == [a.id]
    assert measured_short.json()["unheard_take_ids"] == []
    assert measured_long_again.json()["unheard_take_ids"] == [], (
        "uma medida mais longa tomava o lugar da mais curta"
    )
    assert not_measured.json()["unheard_take_ids"] == [], "um zero tomava o lugar de uma medida"


async def test_the_listen_door_stores_the_report_and_answers_which_parts_are_still_unheard(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (a, b, c) = await rehearsed_in_parts(db_session, 3)

    first = await _listened(
        client,
        session.id,
        _entry(a.id, [[0, TEN_SECONDS]], TEN_SECONDS),
        _entry(b.id, EIGHT_HOLES_OF_SEVEN_TENTHS, TEN_SECONDS),
    )
    second = await _listened(client, session.id, _entry(b.id, [[0, TEN_SECONDS]], TEN_SECONDS))
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
    assert unheard_parts(stored, [a.id, b.id]) == [], (
        "o relato que leu antes gravava por cima, e a parte ouvida pelo outro sumia"
    )
