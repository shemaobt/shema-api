"""ENG-1320 — rehearsing a scene again makes rehearsal n+1; a sent one is frozen but still heard.

A team that rehearses a scene again gets the next **Scene rehearsal** of its session, and the
earlier one keeps its recording and its **Scene frases**. Once sent, a rehearsal takes no frase
and no restart, yet any tablet of the team can still hear it, its frases included, and the team
can still give it its scene label, said later.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.canon_harness import the_canon_moves_on
from tests.hard_stretch_harness import a_session
from tests.scene_rehearsal_harness import (
    IR,
    SAID,
    SCENE,
    Room,
    a_room,
    key_of,
    read_by_b,
    record,
    recorded,
    recording,
    restart,
    sent,
    the_kept_p02_tells_its_appeals_as_one_scene,
    translate,
    translated,
    write,
)

NEW_PIN = "a" * 40


@pytest.fixture()
async def room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    async with a_room(db_session, rival_factory, monkeypatch) as built:
        yield built


async def label(room: Room, session_id: str, rehearsal_id: str, scene: str) -> httpx.Response:
    return await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/scene",
        data={"scene": scene},
    )


async def hear_the_frase(
    room: Room, session_id: str, rehearsal_id: str, frase_id: str
) -> httpx.Response:
    return await room.client.get(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/frases/{frase_id}/audio",
        headers=room.tablet_b,
    )


async def the_record(room: Room, session_id: str, rehearsal_id: str) -> dict[str, Any]:
    (found,) = [r for r in await read_by_b(room, session_id) if r["rehearsal_id"] == rehearsal_id]
    return found


def places(rehearsal: dict[str, Any]) -> list[tuple[int, int]]:
    return [(f["starts_ms"], f["ends_ms"]) for f in rehearsal["frases"] if f["replaced_by"] is None]


def keys_anywhere(body: Any) -> set[str]:
    if isinstance(body, dict):
        return set(body) | {key for value in body.values() for key in keys_anywhere(value)}
    if isinstance(body, list):
        return {key for value in body for key in keys_anywhere(value)}
    return set()


THREE_PLACES = [(0, 5000), (5000, 11000), (11000, 17000)]


async def scene_2_sent_and_rehearsed_again(
    room: Room, db: AsyncSession, session_id: str
) -> tuple[str, httpx.Response]:
    first = await recorded(room, session_id)
    await translated(room, session_id, first, THREE_PLACES)
    await sent(db, first)
    again = await record(room, session_id, recording(40, 2), scene="S2")
    return first, again


async def test_a_scene_rehearsed_again_after_rehearsal_1_was_sent_is_rehearsal_2_and_rehearsal_1_stays_sent_with_its_frases(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    first, again = await scene_2_sent_and_rehearsed_again(room, db_session, session_id)

    assert again.status_code == 200, again.text
    assert again.json()["n"] == 2
    assert {r["rehearsal_id"] for r in await read_by_b(room, session_id)} == {
        first,
        again.json()["rehearsal_id"],
    }
    rehearsal_1 = await the_record(room, session_id, first)
    assert rehearsal_1["sent_at"] is not None
    assert rehearsal_1["scene"] == "S2"
    assert places(rehearsal_1) == THREE_PLACES
    heard = await room.client.get(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{first}/audio", headers=room.tablet_b
    )
    assert heard.status_code == 307, heard.text
    assert room.signed == [key_of(room, SCENE)]


async def test_the_list_names_each_rehearsals_number_scene_recording_time_frases_and_sent_state(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    await scene_2_sent_and_rehearsed_again(room, db_session, session_id)

    listed = sorted(await read_by_b(room, session_id), key=lambda r: r["n"])

    assert [(r["n"], r["scene"], len(places(r)), r["sent_at"] is not None) for r in listed] == [
        (1, "S2", 3, True),
        (2, "S2", 0, False),
    ]
    for rehearsal in listed:
        datetime.fromisoformat(rehearsal["recorded_at"])


async def test_a_sent_rehearsal_refuses_a_frase_and_a_restart_and_its_record_stays_as_it_was(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000)])
    await sent(db_session, rehearsal_id)
    before = await the_record(room, session_id, rehearsal_id)

    frase = await translate(room, session_id, rehearsal_id, (11000, 17000), recording(1, 700))
    restarted = await restart(room, session_id, rehearsal_id)

    assert (frase.status_code, frase.json()["code"]) == (409, "SCENE_REHEARSAL_SENT"), frase.text
    assert (restarted.status_code, restarted.json()["code"]) == (
        409,
        "SCENE_REHEARSAL_SENT",
    ), restarted.text
    after = await the_record(room, session_id, rehearsal_id)
    kept = ("frases", "after_restart", "scene")
    assert {k: after[k] for k in kept} == {k: before[k] for k in kept}


async def test_a_sent_rehearsal_with_no_label_takes_a_scene_of_the_passage_said_later(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = (await record(room, session_id, scene=None)).json()["rehearsal_id"]
    await sent(db_session, rehearsal_id)
    sent_at = (await the_record(room, session_id, rehearsal_id))["sent_at"]

    labelled = await label(room, session_id, rehearsal_id, "S2")

    assert labelled.status_code == 200, labelled.text
    rehearsal = await the_record(room, session_id, rehearsal_id)
    assert (rehearsal["scene"], rehearsal["scene_said"]) == ("S2", "later")
    assert rehearsal["sent_at"] == sent_at


async def test_a_scene_that_is_not_the_passages_is_refused_and_the_rehearsal_keeps_no_label(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = (await record(room, session_id, scene=None)).json()["rehearsal_id"]
    await sent(db_session, rehearsal_id)
    before = await the_record(room, session_id, rehearsal_id)

    refused = await label(room, session_id, rehearsal_id, "S99")

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "UNKNOWN_SCENE"
    after = await the_record(room, session_id, rehearsal_id)
    assert after["scene"] is None
    assert after == before


async def test_the_same_label_again_changes_nothing(room: Room, db_session: AsyncSession) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await sent(db_session, rehearsal_id)
    before = await the_record(room, session_id, rehearsal_id)

    again = await label(room, session_id, rehearsal_id, "S2")

    assert again.status_code == 200, again.text
    rehearsal = await the_record(room, session_id, rehearsal_id)
    assert (rehearsal["scene"], rehearsal["scene_said"]) == ("S2", "recording")
    assert rehearsal == before


async def test_a_rehearsal_reserved_but_never_recorded_is_not_in_the_list(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    refused = await record(room, session_id, b"")

    assert refused.status_code == 400, refused.text
    assert await read_by_b(room, session_id) == []


async def test_a_sent_rehearsals_frase_is_heard_from_another_tablet(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    _first, second = await translated(
        room, session_id, rehearsal_id, [(0, 5000), (5000, 11000)], tone=100
    )
    await sent(db_session, rehearsal_id)

    heard = await hear_the_frase(room, session_id, rehearsal_id, second)

    assert heard.status_code == 307, heard.text
    assert room.signed == [key_of(room, recording(1, 101))]


async def test_a_frase_of_another_rehearsal_is_not_heard_through_this_one(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_1 = await recorded(room, session_id)
    (frase_of_1,) = await translated(room, session_id, rehearsal_1, [(0, 5000)])
    rehearsal_2 = await recorded(room, session_id, recording(40, 2))

    refused = await hear_the_frase(room, session_id, rehearsal_2, frase_of_1)

    assert refused.status_code == 404, refused.text
    assert room.signed == []
    through_its_own = await hear_the_frase(room, session_id, rehearsal_1, frase_of_1)
    assert through_its_own.status_code == 307, through_its_own.text


async def test_the_label_door_answers_no_words_and_no_guess(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = (await record(room, session_id, scene=None)).json()["rehearsal_id"]
    await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000)])
    await write(db_session, "scene_guess", "S3", rehearsal_id)

    labelled = await label(room, session_id, rehearsal_id, "S2")

    assert labelled.status_code == 200, labelled.text
    assert labelled.json()["scene"] == "S2"
    assert {"transcript", "scene_guess"} & keys_anywhere(labelled.json()) == set()
    assert SAID not in labelled.text
    assert "S3" not in labelled.text


async def test_a_scene_the_sessions_pinned_canon_lacks_is_no_label_at_the_keep_and_later_though_the_deployed_canon_has_it(  # noqa: E501
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session_id = await a_session(db_session, pericope="P02")
    the_canon_moves_on(
        monkeypatch, tmp_path, NEW_PIN, keeping=the_kept_p02_tells_its_appeals_as_one_scene
    )

    kept = await record(room, session_id, scene="S3")

    assert kept.status_code == 200, kept.text
    rehearsal_id = kept.json()["rehearsal_id"]
    stored = await db_session.execute(
        text("SELECT scene, scene_foreign FROM ir_scene_rehearsals WHERE id = :id"),
        {"id": rehearsal_id},
    )
    assert tuple(stored.one()) == (None, "S3"), (
        "a cena que o cânone fixado da sessão não tem era guardada como rótulo"
    )
    refused = await label(room, session_id, rehearsal_id, "S3")
    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "UNKNOWN_SCENE"
    assert (await the_record(room, session_id, rehearsal_id))["scene"] is None


async def test_a_rehearsal_with_no_label_is_kept_though_the_sessions_pinned_canon_is_not_kept_here(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    await db_session.execute(
        text("UPDATE ir_sessions SET canon_pin = :pin WHERE id = :id"),
        {"pin": "b" * 40, "id": session_id},
    )
    await db_session.commit()

    kept = await record(room, session_id, scene=None)

    assert kept.status_code == 200, (
        f"um ensaio sem cena era recusado porque o cânone da sessão não está guardado: {kept.text}"
    )
    assert kept.json()["scene"] is None
