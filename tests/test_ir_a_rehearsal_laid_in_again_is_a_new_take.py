"""ENG-1407 — a scene rehearsal laid in again at a new pass is a new take, sharing its bytes.

The **Rehearsal swap** puts a scene rehearsal in as the part's next pass. Swapping back to an
earlier rehearsal sends bytes the session already holds, and her server keeps that as a new take
over the one it replaces (join.ts:225-240 at 18fa7c4), so A → B → A is three takes and the last is
the part. The same bytes under the same number and pass are the same take: a resend, or a second
tablet's same join, and a late resend of an earlier pass never takes the part back (ADR 0072).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.segments import capture_segment
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX, checked_heard_and_approved
from tests.room_harness import (
    PART_MS,
    TABLET,
    a_scene_rehearsal,
    nothing_is_read_ahead,
    rehearsed_in_parts,
    room_client,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
)
from tests.session_row_lock_harness import the_session_row_locks_as_postgres_does

A = b"o ensaio A da cena 2"
B = b"o ensaio B da cena 2"
CENA_1 = b"o ensaio da cena 1"


@pytest.fixture(autouse=True)
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    the_analyst_reads(monkeypatch)
    the_room_speaks(monkeypatch)
    nothing_is_read_ahead(monkeypatch)

    async def said(*_: Any, **__: Any) -> str:
        return "a frase traduzida"

    monkeypatch.setattr(segments_api, "heard", said)


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _keep(
    client: httpx.AsyncClient,
    session_id: str,
    *,
    part: int | None,
    audio: bytes,
    pass_number: int | None,
    origin: str | None = None,
    reopens: bool = False,
    headers: dict[str, str] | None = None,
    kind: str = "ensaio",
) -> httpx.Response:
    data = {"kind": kind, "scope": "passagem-inteira" if part is None else f"parte-{part}"}
    if part is not None:
        data["chunk_index"] = str(part)
    if pass_number is not None:
        data["pass_number"] = str(pass_number)
    if origin is not None:
        data["origin"] = origin
    if origin is not None and part is not None:
        listed = await _takes_of_part(client, session_id, part)
        if listed:
            data["over_take"] = listed[-1]["take_id"]
    if reopens:
        data["reopens_the_approved_draft"] = "true"
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers=headers or {"X-Room-Device": TABLET},
        data=data,
        files={"file": ("cena.m4a", audio, "audio/mp4")},
    )


async def _kept(client: httpx.AsyncClient, session_id: str, **keep: Any) -> str:
    answered = await _keep(client, session_id, **keep)
    assert answered.status_code == 200, answered.text
    return str(answered.json()["take_id"])


async def _two_rehearsals(db: AsyncSession) -> tuple[IRSession, str, str]:
    session, _ = await rehearsed_in_parts(db, 0)
    first = await a_scene_rehearsal(db, session, 1)
    second = await a_scene_rehearsal(db, session, 2)
    return session, first.id, second.id


async def _takes_of_part(
    client: httpx.AsyncClient, session_id: str, part: int
) -> list[dict[str, Any]]:
    listed = await client.get(f"{PREFIX}/sessions/{session_id}/takes")
    assert listed.status_code == 200, listed.text
    return [take for take in listed.json()["takes"] if take["ordinal"] == part]


async def _the_parts(client: httpx.AsyncClient, session_id: str) -> list[str]:
    """The takes the room holds as the parts, named by the listen door with nothing heard yet."""
    listened = await client.post(f"{PREFIX}/sessions/{session_id}/back-translation/listened-whole")
    assert listened.status_code == 200, listened.text
    return list(listened.json()["unheard_take_ids"])


async def _stretches(
    client: httpx.AsyncClient, session_id: str, *, include_stale: bool
) -> list[dict[str, Any]]:
    read = await client.get(
        f"{PREFIX}/sessions/{session_id}",
        params={"include_stale": "true"} if include_stale else None,
    )
    assert read.status_code == 200, read.text
    return list(read.json()["back_translation"]["segments"])


async def _approval(client: httpx.AsyncClient, session_id: str) -> dict[str, Any] | None:
    read = await client.get(f"{PREFIX}/sessions/{session_id}")
    assert read.status_code == 200, read.text
    approval: dict[str, Any] | None = read.json()["approved"]
    return approval


async def _told_over(db: AsyncSession, session: IRSession, take_id: str, n: int) -> str:
    told = await capture_segment(
        db,
        session,
        take_id=take_id,
        starts_ms=0,
        ends_ms=PART_MS,
        bridge_take_id=f"retro-{n}",
        transcript=f"a cena contada de volta {n}",
    )
    return told.id


async def test_a_scene_swapped_from_a_to_b_and_back_to_a_holds_three_takes_and_the_last_is_the_part(
    client, db_session
) -> None:
    session, ra, rb = await _two_rehearsals(db_session)

    first = await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)
    await _kept(client, session.id, part=2, audio=B, pass_number=2, origin=rb)
    third = await _kept(client, session.id, part=2, audio=A, pass_number=3, origin=ra)

    takes = await _takes_of_part(client, session.id, 2)
    assert [(take["pass_number"], take["origin"]) for take in takes] == [
        (1, ra),
        (2, rb),
        (3, ra),
    ], "a troca de volta ao ensaio A não deixava uma terceira tomada"
    assert third != first, "a troca de volta respondia a tomada antiga de A"
    assert await _the_parts(client, session.id) == [third], (
        "a sala ficava com B como parte enquanto a tablet acreditava em A"
    )


async def test_the_takes_a_swap_replaces_stay_stored(client, db_session, store) -> None:
    session, ra, rb = await _two_rehearsals(db_session)

    first = await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)
    second = await _kept(client, session.id, part=2, audio=B, pass_number=2, origin=rb)

    assert [take["take_id"] for take in await _takes_of_part(client, session.id, 2)] == [
        first,
        second,
    ]
    assert A in store.objects.values(), "a troca apagava o ensaio que saiu"


async def test_the_stretches_over_the_swapped_out_take_leave_the_check_and_stay_in_history(
    client, db_session
) -> None:
    session, ra, rb = await _two_rehearsals(db_session)
    first = await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)
    told = await _told_over(db_session, session, first, 1)

    await _kept(client, session.id, part=2, audio=B, pass_number=2, origin=rb)

    assert told not in [
        row["segment_id"] for row in await _stretches(client, session.id, include_stale=False)
    ]
    assert [
        row["stale"]
        for row in await _stretches(client, session.id, include_stale=True)
        if row["segment_id"] == told
    ] == [True], "o trecho contado sobre o ensaio trocado sumia do histórico"


async def test_a_resent_join_at_the_same_pass_is_the_same_take(client, db_session) -> None:
    session, ra, rb = await _two_rehearsals(db_session)
    await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)
    await _kept(client, session.id, part=2, audio=B, pass_number=2, origin=rb)
    sent = await _kept(client, session.id, part=2, audio=A, pass_number=3, origin=ra)

    resent = await _kept(client, session.id, part=2, audio=A, pass_number=3, origin=ra)

    assert resent == sent, "o reenvio da caixa de saída virava outra tomada"
    assert len(await _takes_of_part(client, session.id, 2)) == 3


async def test_two_tablets_joining_the_same_rehearsal_at_the_same_pass_leave_one_take(
    client, db_session
) -> None:
    session, ra, _ = await _two_rehearsals(db_session)
    other = await a_linked_tablet(db_session, team_id=TABLET_TEAM)

    from_x = await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)
    from_y = await _kept(
        client,
        session.id,
        part=2,
        audio=A,
        pass_number=1,
        origin=ra,
        headers=other.headers | {"X-Room-Device": "tablet-y"},
    )

    assert from_y == from_x, "duas tablets juntando o mesmo ensaio deixavam duas tomadas"
    assert len(await _takes_of_part(client, session.id, 2)) == 1


async def test_a_second_tablet_joining_the_rehearsal_already_in_the_part_at_its_next_pass_leaves_one_take(  # noqa: E501
    client, db_session
) -> None:
    session, ra, _ = await _two_rehearsals(db_session)
    other = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    from_x = await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)

    from_y = await _kept(
        client,
        session.id,
        part=2,
        audio=A,
        pass_number=2,
        origin=ra,
        headers=other.headers | {"X-Room-Device": "tablet-y"},
    )

    assert from_y == from_x, "a segunda tablet juntando o mesmo ensaio deixava duas tomadas"
    assert len(await _takes_of_part(client, session.id, 2)) == 1


async def test_a_late_resend_of_an_earlier_join_does_not_take_the_part_back(
    client, db_session
) -> None:
    session, ra, rb = await _two_rehearsals(db_session)
    first = await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)
    second = await _kept(client, session.id, part=2, audio=B, pass_number=2, origin=rb)

    late = await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)

    assert late == first, "o reenvio atrasado do ensaio A virava uma tomada nova"
    assert await _the_parts(client, session.id) == [second], (
        "o ensaio que a equipe abandonou voltava a ser a parte"
    )


async def test_a_swap_back_over_an_approved_draft_without_the_armed_tap_is_refused(
    client, db_session, store
) -> None:
    session, ra, rb = await _two_rehearsals(db_session)
    scene_1 = await a_scene_rehearsal(db_session, session, 3)
    one = await _kept(client, session.id, part=1, audio=CENA_1, pass_number=1, origin=scene_1.id)
    await _told_over(db_session, session, one, 1)
    await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)
    b = await _kept(client, session.id, part=2, audio=B, pass_number=2, origin=rb)
    await _told_over(db_session, session, b, 2)
    await checked_heard_and_approved(client, db_session, session.id)
    takes_before = await _takes_of_part(client, session.id, 2)
    stored_before = dict(store.objects)

    refused = await _keep(client, session.id, part=2, audio=A, pass_number=3, origin=ra)

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "DRAFT_APPROVED"
    assert await _takes_of_part(client, session.id, 2) == takes_before
    assert store.objects == stored_before
    assert (await _approval(client, session.id) or {}).get("version") == 1

    armed = await _kept(client, session.id, part=2, audio=A, pass_number=3, origin=ra, reopens=True)

    assert armed not in [take["take_id"] for take in takes_before]
    assert await _approval(client, session.id) is None


async def test_a_hand_recorded_take_sent_twice_is_still_one_take(client, db_session) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)

    sent = await _kept(client, session.id, part=2, audio=A, pass_number=1)
    resent = await _kept(client, session.id, part=2, audio=A, pass_number=1)

    assert resent == sent
    assert len(await _takes_of_part(client, session.id, 2)) == 1


async def test_the_same_rehearsal_joined_under_another_part_is_that_parts_own_take(
    client, db_session
) -> None:
    session, ra, _ = await _two_rehearsals(db_session)
    second = await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)

    third = await _kept(client, session.id, part=3, audio=A, pass_number=1, origin=ra)

    assert third != second, "os mesmos bytes sob outra parte respondiam a tomada da outra parte"
    assert [take["take_id"] for take in await _takes_of_part(client, session.id, 3)] == [third]


async def test_a_resend_of_a_join_already_kept_over_an_approved_draft_is_not_refused(
    client, db_session
) -> None:
    session, ra, rb = await _two_rehearsals(db_session)
    scene_1 = await a_scene_rehearsal(db_session, session, 3)
    one = await _kept(client, session.id, part=1, audio=CENA_1, pass_number=1, origin=scene_1.id)
    await _told_over(db_session, session, one, 1)
    first = await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)
    two = await _kept(client, session.id, part=2, audio=B, pass_number=2, origin=rb)
    await _told_over(db_session, session, two, 2)
    await checked_heard_and_approved(client, db_session, session.id)

    late = await _keep(client, session.id, part=2, audio=A, pass_number=1, origin=ra)

    assert late.status_code == 200, late.text
    assert late.json()["take_id"] == first
    assert (await _approval(client, session.id) or {}).get("version") == 1


async def test_a_hand_recorded_take_with_a_joined_parts_bytes_is_its_own_take(
    client, db_session
) -> None:
    session, ra, _ = await _two_rehearsals(db_session)
    joined = await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)

    by_hand = await _kept(client, session.id, part=3, audio=A, pass_number=1)

    assert by_hand != joined, "a tomada feita à mão respondia a parte juntada de outra cena"
    assert [take["origin"] for take in await _takes_of_part(client, session.id, 3)] == [None]


async def test_a_second_tablet_joining_while_the_first_stores_its_bytes_leaves_one_take(
    db_session, monkeypatch: pytest.MonkeyPatch, store, rival_factory
) -> None:
    lock = the_session_row_locks_as_postgres_does(monkeypatch)
    session, ra, _ = await _two_rehearsals(db_session)
    other = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    tablet_y = other.headers | {"X-Room-Device": "tablet-y"}
    put = store.put
    staged: list[str] = []

    async with room_client(db_session, monkeypatch, per_request=rival_factory) as racing:

        async def y_joins_while_x_stores(key: str, data: bytes, content_type: str) -> Any:
            if not staged:
                staged.append("")
                staged[0] = await _kept(
                    racing,
                    session.id,
                    part=2,
                    audio=A,
                    pass_number=2,
                    origin=ra,
                    headers=tablet_y,
                )
            return await put(key, data, content_type)

        monkeypatch.setattr(store, "put", y_joins_while_x_stores)
        lock.notes_the_calls(monkeypatch, store, "get", "put", "stat")

        from_x = await _kept(racing, session.id, part=2, audio=A, pass_number=1, origin=ra)

        assert from_x == staged[0], "duas tablets juntando ao mesmo tempo deixavam duas tomadas"
        assert len(await _takes_of_part(racing, session.id, 2)) == 1
        assert lock.made_while_held == [], "o bucket trabalhava com a linha da sessão presa"


async def test_a_part_number_below_zero_or_a_pass_below_one_is_refused_at_the_door(
    client, db_session
) -> None:
    session, ra, _ = await _two_rehearsals(db_session)

    below_zero = await _keep(client, session.id, part=-1, audio=A, pass_number=1, origin=ra)
    pass_zero = await _keep(client, session.id, part=2, audio=A, pass_number=0, origin=ra)

    assert (below_zero.status_code, pass_zero.status_code) == (422, 422)
    assert (
        await _keep(client, session.id, part=None, audio=A, pass_number=None, origin=ra)
    ).status_code == 200


async def test_another_rehearsals_join_with_the_standing_parts_bytes_is_its_own_take(
    client, db_session
) -> None:
    session, ra, rb = await _two_rehearsals(db_session)
    standing = await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)

    other = await _kept(client, session.id, part=2, audio=A, pass_number=2, origin=rb)

    assert other != standing
    assert [take["origin"] for take in await _takes_of_part(client, session.id, 2)] == [ra, rb]


async def test_the_standing_parts_rehearsal_joined_with_other_bytes_is_its_own_take(
    client, db_session
) -> None:
    session, ra, _ = await _two_rehearsals(db_session)
    standing = await _kept(client, session.id, part=2, audio=A, pass_number=1, origin=ra)

    other = await _kept(client, session.id, part=2, audio=B, pass_number=2, origin=ra)

    assert other != standing
    assert len(await _takes_of_part(client, session.id, 2)) == 2


async def test_a_retro_kept_with_an_origin_never_answers_the_standing_rehearsal_take(
    client, db_session
) -> None:
    session, ra, _ = await _two_rehearsals(db_session)
    whole = await _kept(client, session.id, part=None, audio=A, pass_number=1, origin=ra)

    retro = await _keep(
        client, session.id, part=None, audio=A, pass_number=1, origin=ra, kind="retro"
    )

    assert retro.status_code == 200, retro.text
    assert (retro.json()["take_id"] == whole, retro.json()["kind"]) == (False, "retro")
