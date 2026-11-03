"""ENG-1348 — the frase door refuses a frase that overlaps a current one.

A scene rehearsal never holds two current frases over one stretch: a frase whose span strictly
overlaps a current frase of the same attempt is `FRASE_OUT_OF_PLACE`, unless it replaces that
frase. Touching edges stand.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.hard_stretch_harness import a_session
from tests.scene_rehearsal_harness import (
    Room,
    a_room,
    count,
    frases_read_by_b,
    recorded,
    recording,
    restart,
    translate,
    translated,
)


@pytest.fixture()
async def room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    async with a_room(db_session, rival_factory, monkeypatch) as built:
        yield built


async def current_places(room: Room, session_id: str) -> list[tuple[int, int]]:
    return [
        (f["starts_ms"], f["ends_ms"])
        for f in await frases_read_by_b(room, session_id)
        if f["replaced_by"] is None
    ]


async def test_a_frase_over_a_stretch_a_current_frase_holds_is_refused_as_out_of_place_naming_that_frase(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    (kept,) = await translated(room, session_id, rehearsal_id, [(0, 4000)])

    rejected = recording(1, 900)

    refused = await translate(room, session_id, rehearsal_id, (0, 4000), rejected)

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "FRASE_OUT_OF_PLACE"
    assert kept in refused.json()["detail"]
    assert rejected not in room.bucket.objects.values()
    assert await current_places(room, session_id) == [(0, 4000)]


async def test_a_frase_that_only_partly_overlaps_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 4000)])

    refused = await translate(room, session_id, rehearsal_id, (3000, 6000), recording(1, 900))

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "FRASE_OUT_OF_PLACE"


async def test_a_frase_touching_the_end_of_the_last_one_is_kept(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 4000)])

    kept = await translate(room, session_id, rehearsal_id, (4000, 8000), recording(1, 900))

    assert kept.status_code == 200, kept.text
    assert await current_places(room, session_id) == [(0, 4000), (4000, 8000)]


async def test_the_same_bytes_sent_again_are_still_the_same_frase(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    audio = recording(1, 900)
    first = await translate(room, session_id, rehearsal_id, (0, 4000), audio)
    assert first.status_code == 200, first.text

    again = await translate(room, session_id, rehearsal_id, (0, 4000), audio)

    assert again.status_code == 200, again.text
    assert [f["frase_id"] for f in again.json()["frases"]] == [
        f["frase_id"] for f in first.json()["frases"]
    ]
    assert await current_places(room, session_id) == [(0, 4000)]


async def test_a_frase_that_names_the_overlapped_frase_in_replaces_is_kept(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    (kept,) = await translated(room, session_id, rehearsal_id, [(0, 4000)])

    replaced = await translate(
        room, session_id, rehearsal_id, (0, 4500), recording(1, 900), replaces=kept
    )

    assert replaced.status_code == 200, replaced.text
    assert await current_places(room, session_id) == [(0, 4500)]


async def test_a_frase_of_a_new_attempt_over_a_stretch_of_the_earlier_attempt_is_kept(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 4000)])
    restarted = await restart(room, session_id, rehearsal_id)
    assert restarted.status_code == 200, restarted.text

    kept = await translate(
        room,
        session_id,
        rehearsal_id,
        (0, 4000),
        recording(1, 900),
        after_restart=restarted.json()["after_restart"],
    )

    assert kept.status_code == 200, kept.text
    assert await current_places(room, session_id) == [(0, 4000)]


async def test_two_different_frases_posted_at_once_over_one_stretch_keep_only_one(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    rivals: list[httpx.Response] = []

    async def the_other_while_this_is_heard() -> None:
        rivals.append(await translate(room, session_id, rehearsal_id, (0, 4000), recording(1, 901)))

    room.while_hearing.append(the_other_while_this_is_heard)
    first = await translate(room, session_id, rehearsal_id, (0, 4000), recording(1, 900))

    (second,) = rivals
    assert sorted([first.status_code, second.status_code]) == [200, 422], (first.text, second.text)
    refused = first if first.status_code == 422 else second
    assert refused.json()["code"] == "FRASE_OUT_OF_PLACE"
    assert await current_places(room, session_id) == [(0, 4000)]


async def test_a_frase_of_an_attempt_whose_restart_has_not_landed_is_kept_over_the_current_attempts_stretch(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 4000)])

    held = await translate(
        room,
        session_id,
        rehearsal_id,
        (0, 4000),
        recording(1, 900),
        after_restart=str(uuid.uuid4()),
    )

    assert held.status_code == 200, held.text
    assert await current_places(room, session_id) == [(0, 4000)]


async def test_a_late_frase_of_an_attempt_a_restart_closed_is_kept_set_aside_over_the_frase_it_set_aside(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 4000)])
    restarted = await restart(room, session_id, rehearsal_id)
    assert restarted.status_code == 200, restarted.text
    closing = restarted.json()["after_restart"]

    late = await translate(room, session_id, rehearsal_id, (0, 4000), recording(1, 900))

    assert late.status_code == 200, late.text
    assert await current_places(room, session_id) == []
    assert await count(db_session, "ir_scene_frases", "restart_id", closing) == 2
