"""ENG-1349 — the team moves the pause of the scene rehearsal's last frase.

A **Moved pause** is a **Scene frase** posted through the frase door with `replaces` naming the
rehearsal's last current frase, from the same start to a new end. The room refuses it in her
three ways, with the Ensaio Final's three codes: not the last frase, past the end of the
recording, and a pause that cannot stand there (the frase was replaced since the tablet read
it, the start changed, or the frase would be shorter than 0.2 s). A frase that replaces
another over the same place is that frase translated again, never a moved pause. Two tablets of
one team speak through the real doors; the cases that say a row or an object exists read the
table and the bucket.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.hard_stretch_harness import a_session
from tests.scene_rehearsal_harness import (
    IR,
    Room,
    a_room,
    current,
    frases_read_by_b,
    recorded,
    recording,
    restart,
    translate,
    translated,
)

THREE = [(0, 5000), (5000, 11000), (11000, 17000)]


@pytest.fixture()
async def room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    async with a_room(db_session, rival_factory, monkeypatch) as built:
        yield built


async def kept_by_b(
    room: Room,
    session_id: str,
    rehearsal_id: str,
    place: tuple[int, int],
    audio: bytes,
    *,
    replaces: str | None = None,
) -> None:
    starts, ends_ms = place
    data = {"starts_ms": str(starts), "ends_ms": str(ends_ms)}
    if replaces is not None:
        data["replaces"] = replaces
    kept = await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/frases",
        data=data,
        files={"file": ("frase.wav", audio, "audio/wav")},
        headers=room.tablet_b,
    )
    assert kept.status_code == 200, kept.text


async def ends(db: AsyncSession, rehearsal_id: str) -> list[int]:
    found = await db.execute(
        text("SELECT ends_ms FROM ir_scene_frases WHERE rehearsal_id = :r ORDER BY ends_ms"),
        {"r": rehearsal_id},
    )
    return list(found.scalars())


async def read_by_the_desk(room: Room, session_id: str) -> dict[str, Any]:
    listed = await room.client.get(
        f"{IR}/facilitator/sessions/{session_id}/scene-rehearsals", headers=room.desk
    )
    assert listed.status_code == 200, listed.text
    (rehearsal,) = listed.json()["scene_rehearsals"]
    return dict(rehearsal)


async def test_the_last_frases_pause_moves_later_and_the_frase_takes_the_new_span(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(room, session_id, rehearsal_id, THREE)

    moved = await translate(
        room, session_id, rehearsal_id, (11000, 18500), recording(1, 900), replaces=third
    )

    assert moved.status_code == 200, moved.text
    frases = await frases_read_by_b(room, session_id)
    assert current(frases) == [(0, 5000), (5000, 11000), (11000, 18500)]
    replacing = next(f["frase_id"] for f in frases if f["ends_ms"] == 18500)
    assert {f["frase_id"]: f["replaced_by"] for f in frases}[third] == replacing


async def test_the_last_frases_pause_moves_earlier(room: Room, db_session: AsyncSession) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(room, session_id, rehearsal_id, THREE)

    moved = await translate(
        room, session_id, rehearsal_id, (11000, 15000), recording(1, 900), replaces=third
    )

    assert moved.status_code == 200, moved.text
    assert current(await frases_read_by_b(room, session_id)) == [
        (0, 5000),
        (5000, 11000),
        (11000, 15000),
    ]


async def test_an_earlier_frases_pause_cannot_move(room: Room, db_session: AsyncSession) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    _, second, _ = await translated(room, session_id, rehearsal_id, THREE)

    refused = await translate(
        room, session_id, rehearsal_id, (5000, 12000), recording(1, 900), replaces=second
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_ONLY_ON_THE_LAST_FRASE"
    assert current(await frases_read_by_b(room, session_id)) == THREE


async def test_a_frase_appended_by_the_second_tablet_makes_the_moved_frase_not_the_last(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(room, session_id, rehearsal_id, THREE)
    await kept_by_b(room, session_id, rehearsal_id, (17000, 22000), recording(1, 800))

    refused = await translate(
        room, session_id, rehearsal_id, (11000, 18500), recording(1, 900), replaces=third
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_ONLY_ON_THE_LAST_FRASE"
    assert 18500 not in await ends(db_session, rehearsal_id)


async def test_a_frase_appended_while_the_move_is_heard_refuses_the_move(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(room, session_id, rehearsal_id, THREE)
    the_move = recording(1, 900)

    async def b_appends() -> None:
        await kept_by_b(room, session_id, rehearsal_id, (17000, 22000), recording(1, 800))

    room.while_hearing.append(b_appends)
    refused = await translate(
        room, session_id, rehearsal_id, (11000, 18500), the_move, replaces=third
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_ONLY_ON_THE_LAST_FRASE"
    assert current(await frases_read_by_b(room, session_id)) == [*THREE, (17000, 22000)]
    assert the_move in room.bucket.objects.values()
    assert 18500 not in await ends(db_session, rehearsal_id)


async def test_a_moved_pause_past_the_end_of_the_recording_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(room, session_id, rehearsal_id, THREE)

    refused = await translate(
        room, session_id, rehearsal_id, (11000, 40500), recording(1, 900), replaces=third
    )
    new_past_the_end = await translate(
        room, session_id, rehearsal_id, (17000, 41000), recording(1, 901)
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_PAST_THE_END"
    assert new_past_the_end.status_code == 422, new_past_the_end.text
    assert new_past_the_end.json()["code"] == "FRASE_OUT_OF_PLACE"
    assert current(await frases_read_by_b(room, session_id)) == THREE


async def test_a_move_against_a_frase_replaced_since_the_tablet_read_it_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(room, session_id, rehearsal_id, THREE)
    moved = await translate(
        room, session_id, rehearsal_id, (11000, 18000), recording(1, 900), replaces=third
    )
    assert moved.status_code == 200, moved.text

    refused = await translate(
        room, session_id, rehearsal_id, (11000, 19000), recording(1, 901), replaces=third
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_CANNOT_STAND_THERE"
    assert current(await frases_read_by_b(room, session_id))[-1] == (11000, 18000)


async def test_two_moves_of_the_last_pause_at_once_keep_only_the_first_to_land(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(room, session_id, rehearsal_id, THREE)

    async def b_moves() -> None:
        await kept_by_b(
            room, session_id, rehearsal_id, (11000, 18000), recording(1, 800), replaces=third
        )

    room.while_hearing.append(b_moves)
    refused = await translate(
        room, session_id, rehearsal_id, (11000, 19000), recording(1, 900), replaces=third
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_CANNOT_STAND_THERE"
    assert current(await frases_read_by_b(room, session_id))[-1] == (11000, 18000)
    assert 19000 not in await ends(db_session, rehearsal_id)


async def test_a_frase_translated_again_over_the_place_a_move_left_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(room, session_id, rehearsal_id, THREE)
    moved = await translate(
        room, session_id, rehearsal_id, (11000, 18500), recording(1, 900), replaces=third
    )
    assert moved.status_code == 200, moved.text

    refused = await translate(
        room, session_id, rehearsal_id, (11000, 17000), recording(1, 901), replaces=third
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_CANNOT_STAND_THERE"
    assert current(await frases_read_by_b(room, session_id))[-1] == (11000, 18500)


async def test_the_last_pause_of_an_attempt_whose_restart_has_not_landed_moves(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000)])
    attempt = str(uuid.uuid4())
    held = await translate(
        room, session_id, rehearsal_id, (0, 3000), recording(1, 900), after_restart=attempt
    )
    assert held.status_code == 200, held.text
    ((named,),) = [
        [f["frase_id"] for f in waiting["frases"]]
        for waiting in (await read_by_the_desk(room, session_id))["held"]
    ]

    moved = await translate(
        room,
        session_id,
        rehearsal_id,
        (0, 2500),
        recording(1, 901),
        replaces=named,
        after_restart=attempt,
    )
    landed = await restart(room, session_id, rehearsal_id, attempt)

    assert moved.status_code == 200, moved.text
    assert landed.status_code == 200, landed.text
    assert current(await frases_read_by_b(room, session_id)) == [(0, 2500)]


async def test_a_move_heard_while_a_restart_lands_is_set_aside_for_the_consultant(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(room, session_id, rehearsal_id, THREE)

    async def recomeca() -> None:
        landed = await restart(room, session_id, rehearsal_id)
        assert landed.status_code == 200, landed.text

    room.while_hearing.append(recomeca)
    moved = await translate(
        room, session_id, rehearsal_id, (11000, 18500), recording(1, 900), replaces=third
    )

    assert moved.status_code == 200, moved.text
    assert current(await frases_read_by_b(room, session_id)) == []
    (kept,) = (await read_by_the_desk(room, session_id))["restarts"]
    assert (11000, 18500) in [(f["starts_ms"], f["ends_ms"]) for f in kept["frases"]]


async def test_a_move_that_changes_where_the_frase_starts_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(room, session_id, rehearsal_id, THREE)

    refused = await translate(
        room, session_id, rehearsal_id, (10000, 18000), recording(1, 900), replaces=third
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_CANNOT_STAND_THERE"
    assert current(await frases_read_by_b(room, session_id)) == THREE


async def test_a_move_that_leaves_the_frase_shorter_than_two_tenths_of_a_second_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(room, session_id, rehearsal_id, THREE)

    refused = await translate(
        room, session_id, rehearsal_id, (11000, 11150), recording(1, 900), replaces=third
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "PAUSE_CANNOT_STAND_THERE"
    assert current(await frases_read_by_b(room, session_id)) == THREE


async def test_an_earlier_frase_translated_again_over_its_own_place_is_accepted(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    _, second, _ = await translated(room, session_id, rehearsal_id, THREE)

    again = await translate(
        room, session_id, rehearsal_id, (5000, 11000), recording(1, 900), replaces=second
    )

    assert again.status_code == 200, again.text
    frases = await frases_read_by_b(room, session_id)
    assert current(frases) == THREE
    assert {f["frase_id"]: f["replaced_by"] for f in frases}[second] is not None


async def test_after_a_restart_the_old_frases_stay_for_the_consultant(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000)])

    restarted = await restart(room, session_id, rehearsal_id)

    assert restarted.status_code == 200, restarted.text
    assert current(await frases_read_by_b(room, session_id)) == []
    (kept,) = (await read_by_the_desk(room, session_id))["restarts"]
    assert [(f["starts_ms"], f["ends_ms"]) for f in kept["frases"]] == [(0, 5000), (5000, 11000)]


async def test_a_moved_frase_keeps_the_replaced_one_as_history_for_the_consultant(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(room, session_id, rehearsal_id, THREE)
    moved = await translate(
        room, session_id, rehearsal_id, (11000, 18500), recording(1, 900), replaces=third
    )
    assert moved.status_code == 200, moved.text

    frases = (await read_by_the_desk(room, session_id))["frases"]

    by_place = {(f["starts_ms"], f["ends_ms"]): f for f in frases}
    assert by_place[(11000, 17000)]["replaced_by"] == by_place[(11000, 18500)]["frase_id"]
    assert by_place[(11000, 18500)]["replaced_by"] is None
