"""ENG-2025 — the Desk hears a Scene rehearsal's recording and each Scene frase's own recording.

A reader gets a short-lived signed address and the instant it dies, the way the turn door hands
it back, so an `<audio>` element can play it. The signer is the boundary: the cases read what it
was asked to sign.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.device_harness import TABLET_TEAM
from tests.hard_stretch_harness import a_session
from tests.scene_rehearsal_harness import (
    IR,
    SCENE,
    P,
    Room,
    a_room,
    key_of,
    recorded,
    recording,
    translate,
    translated,
)
from tests.signer_harness import Signer, the_bucket_signs


@pytest.fixture()
async def room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    async with a_room(db_session, rival_factory, monkeypatch) as built:
        yield built


@pytest.fixture()
def signer(room: Room, monkeypatch: pytest.MonkeyPatch) -> Signer:
    return the_bucket_signs(monkeypatch)


def recording_path(session_id: str, rehearsal_id: str) -> str:
    return f"{IR}/facilitator/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/audio"


def frase_path(session_id: str, rehearsal_id: str, frase_id: str) -> str:
    return f"{recording_path(session_id, rehearsal_id)[: -len('/audio')]}/frases/{frase_id}/audio"


async def desk_hears_the_recording(room: Room, session_id: str, rehearsal_id: str):
    return await room.client.get(recording_path(session_id, rehearsal_id), headers=room.desk)


async def desk_hears_the_frase(room: Room, session_id: str, rehearsal_id: str, frase_id: str):
    return await room.client.get(frase_path(session_id, rehearsal_id, frase_id), headers=room.desk)


async def tablet_hears_the_recording(room: Room, session_id: str, rehearsal_id: str):
    return await room.client.get(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/audio",
        headers=room.tablet_b,
        follow_redirects=False,
    )


async def tablet_hears_the_frase(room: Room, session_id: str, rehearsal_id: str, frase_id: str):
    return await room.client.get(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/frases/{frase_id}/audio",
        headers=room.tablet_b,
        follow_redirects=False,
    )


def dies_in_the_future_with_an_offset(expires_at: str) -> float:
    dies = datetime.fromisoformat(expires_at)
    assert dies.utcoffset() is not None
    left = (dies - datetime.now(UTC)).total_seconds()
    assert left > 0
    return left


async def test_the_desk_hears_a_scene_rehearsals_recording_through_a_signed_address_that_dies_in_the_future_with_an_offset(  # noqa: E501
    room: Room, signer: Signer, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)

    heard = await desk_hears_the_recording(room, session_id, rehearsal_id)

    assert heard.status_code == 200, heard.text
    body = heard.json()
    assert set(body) == {"url", "expires_at"}
    assert [call[0] for call in signer.calls] == [key_of(room, SCENE)]
    assert body["url"] == f"https://signed.example/balde-de-teste/{key_of(room, SCENE)}?grant=1"
    dies_in_the_future_with_an_offset(body["expires_at"])


async def test_the_desk_hears_a_scene_frases_own_recording_not_the_scene_recording(
    room: Room, signer: Signer, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    (frase_id,) = await translated(room, session_id, rehearsal_id, [(0, 5000)], tone=100)

    heard = await desk_hears_the_frase(room, session_id, rehearsal_id, frase_id)

    assert heard.status_code == 200, heard.text
    assert [call[0] for call in signer.calls] == [key_of(room, recording(1, 100))]
    assert key_of(room, recording(1, 100)) != key_of(room, SCENE)
    dies_in_the_future_with_an_offset(heard.json()["expires_at"])


@pytest.mark.parametrize("door", ["recording", "frase"])
async def test_each_desk_address_dies_when_its_signature_does(
    door: str, room: Room, signer: Signer, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    (frase_id,) = await translated(room, session_id, rehearsal_id, [(0, 5000)])

    heard = (
        await desk_hears_the_recording(room, session_id, rehearsal_id)
        if door == "recording"
        else await desk_hears_the_frase(room, session_id, rehearsal_id, frase_id)
    )

    assert heard.status_code == 200, heard.text
    ((_key, minutes, _content_type),) = signer.calls
    left = dies_in_the_future_with_an_offset(heard.json()["expires_at"])
    assert minutes * 60 - 10 < left <= minutes * 60


async def test_the_desk_and_the_tablet_are_signed_the_same_object_for_a_scene_rehearsal_and_its_frase(  # noqa: E501
    room: Room, signer: Signer, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    (frase_id,) = await translated(room, session_id, rehearsal_id, [(0, 5000)])

    tablet_recording = await tablet_hears_the_recording(room, session_id, rehearsal_id)
    tablet_frase = await tablet_hears_the_frase(room, session_id, rehearsal_id, frase_id)
    desk_recording = await desk_hears_the_recording(room, session_id, rehearsal_id)
    desk_frase = await desk_hears_the_frase(room, session_id, rehearsal_id, frase_id)

    assert [tablet_recording.status_code, tablet_frase.status_code] == [307, 307]
    assert [desk_recording.status_code, desk_frase.status_code] == [200, 200]
    tablet_grants, desk_grants = signer.calls[:2], signer.calls[2:]
    assert desk_grants == tablet_grants


async def test_a_replaced_frase_is_still_heard_at_the_desk(
    room: Room, signer: Signer, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    (first,) = await translated(room, session_id, rehearsal_id, [(0, 5000)], tone=100)
    replaced = await translate(
        room, session_id, rehearsal_id, (0, 5000), recording(1, 200), replaces=first
    )
    assert replaced.status_code == 200, replaced.text

    heard = await desk_hears_the_frase(room, session_id, rehearsal_id, first)

    assert heard.status_code == 200, heard.text
    assert [call[0] for call in signer.calls] == [key_of(room, recording(1, 100))]


async def test_a_scene_rehearsal_of_another_session_is_not_found_at_either_desk_door(
    room: Room, signer: Signer, db_session: AsyncSession
) -> None:
    session_a = await a_session(db_session)
    session_b = await a_session(db_session, pericope="P02")
    await recorded(room, session_a)
    rehearsal_b = await recorded(room, session_b, recording(40, 2))
    (frase_b,) = await translated(room, session_b, rehearsal_b, [(0, 5000)])

    recording_door = await desk_hears_the_recording(room, session_a, rehearsal_b)
    frase_door = await desk_hears_the_frase(room, session_a, rehearsal_b, frase_b)

    assert [recording_door.status_code, frase_door.status_code] == [404, 404]
    assert signer.calls == []
    through_its_own = await desk_hears_the_recording(room, session_b, rehearsal_b)
    assert through_its_own.status_code == 200, through_its_own.text


async def test_a_frase_of_another_rehearsal_is_not_found_through_this_one_at_the_desk(
    room: Room, signer: Signer, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_1 = await recorded(room, session_id)
    (frase_of_1,) = await translated(room, session_id, rehearsal_1, [(0, 5000)])
    rehearsal_2 = await recorded(room, session_id, recording(40, 2))
    await translate(room, session_id, rehearsal_2, (0, 5000), recording(1, 300))

    refused = await desk_hears_the_frase(room, session_id, rehearsal_2, frase_of_1)

    assert refused.status_code == 404, refused.text
    assert signer.calls == []
    through_its_own = await desk_hears_the_frase(room, session_id, rehearsal_1, frase_of_1)
    assert through_its_own.status_code == 200, through_its_own.text


async def test_a_zeroed_session_still_hands_the_desk_both_addresses(
    room: Room, signer: Signer, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    (frase_id,) = await translated(room, session_id, rehearsal_id, [(0, 5000)], tone=100)
    zerado = await room.client.post(
        f"{IR}/facilitator/projects/{TABLET_TEAM}/passages/{P}/archive", headers=room.desk
    )
    assert zerado.status_code == 200, zerado.text

    recording_door = await desk_hears_the_recording(room, session_id, rehearsal_id)
    frase_door = await desk_hears_the_frase(room, session_id, rehearsal_id, frase_id)

    assert [recording_door.status_code, frase_door.status_code] == [200, 200]
    assert [call[0] for call in signer.calls] == [
        key_of(room, SCENE),
        key_of(room, recording(1, 100)),
    ]
