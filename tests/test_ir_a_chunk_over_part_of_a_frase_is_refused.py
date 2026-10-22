from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sessions import create_session
from app.services.internalization_room.takes import declare_rehearsal_parts
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.hard_stretch_harness import (
    DEVICE,
    IR,
    MemoryStore,
    a_session,
    current,
    rehearse,
    retro_takes,
    told,
)
from tests.room_harness import (
    nothing_is_read_ahead,
    room_client,
    the_analyst_reads,
    the_room_speaks,
)
from tests.text_seam_harness import RUNNER_KEY

OTHER_AUDIO = b"a equipe contou de novo, de outro jeito"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router as room_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    said: list[str] = []
    asked: list[bytes] = []

    async def _transcribe(audio: bytes, **_: Any) -> str:
        asked.append(audio)
        return said.pop(0) if said else "algo que a equipe contou"

    monkeypatch.setattr(bt_api, "heard", _transcribe)
    nothing_is_read_ahead(monkeypatch)
    bucket = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: bucket)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    tablet = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test", headers=tablet.headers
    ) as c:
        c.said = said  # type: ignore[attr-defined]
        c.asked = asked  # type: ignore[attr-defined]
        yield c


@pytest.fixture()
async def seam(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_analyst_reads(monkeypatch)
    the_room_speaks(monkeypatch)
    async with room_client(db_session, monkeypatch, runner_key=RUNNER_KEY) as door:
        yield door


async def _chunk(
    client: httpx.AsyncClient,
    session_id: str,
    take_id: str,
    starts_ms: int,
    ends_ms: int,
    *,
    retelling: bool,
) -> httpx.Response:
    data = {"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)}
    if retelling:
        data["retelling"] = "true"
    return await client.post(
        f"{IR}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Device": DEVICE},
        data=data,
        files={"file": ("trecho.m4a", OTHER_AUDIO, "audio/mp4")},
    )


async def _slices(db: AsyncSession, session_id: str) -> list[tuple[int, int, int]]:
    return [(one.starts_ms, one.ends_ms, one.tellings) for one in await current(db, session_id)]


@pytest.mark.parametrize(
    ("starts_ms", "ends_ms", "retelling"),
    [
        pytest.param(0, 12000, True, id="a retelling with its end moved"),
        pytest.param(4000, 13000, False, id="a first telling over part of one"),
        pytest.param(0, 27000, False, id="a slice over two"),
    ],
)
async def test_a_chunk_over_part_of_a_standing_frase_is_refused_before_anything_is_kept(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    starts_ms: int,
    ends_ms: int,
    retelling: bool,
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    await told(client, session_id, take_id, 2)
    kept = len(await retro_takes(db_session, session_id))
    client.asked.clear()  # type: ignore[attr-defined]

    refused = await _chunk(client, session_id, take_id, starts_ms, ends_ms, retelling=retelling)

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "OVERLAPS_A_STANDING_FRASE"
    assert client.asked == [], (  # type: ignore[attr-defined]
        "a fala era mandada ao transcritor antes de alguém olhar onde ela caía"
    )
    assert len(await retro_takes(db_session, session_id)) == kept, (
        "a gravação era guardada como mais uma contagem do mesmo áudio"
    )
    assert await _slices(db_session, session_id) == [(0, 9000, 1), (9000, 18000, 1)], (
        "virava uma frase nova por cima da que estava de pé, e as duas iam para a conferência"
    )


async def test_a_retelling_over_a_slice_no_frase_covers_is_still_a_first_telling(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    await told(client, session_id, take_id, 1)

    told_again = await _chunk(client, session_id, take_id, 9000, 18000, retelling=True)

    assert told_again.status_code == 200, told_again.text
    assert await _slices(db_session, session_id) == [(0, 9000, 1), (9000, 18000, 1)], (
        "o trecho que ninguém tinha contado chega com a marca de recontagem e nada a substituir"
    )


async def test_a_slice_that_starts_where_a_frase_ends_is_a_first_telling_not_an_overlap(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    await told(client, session_id, take_id, 1)

    next_one = await _chunk(client, session_id, take_id, 9000, 12000, retelling=False)

    assert next_one.status_code == 200, next_one.text
    assert await _slices(db_session, session_id) == [(0, 9000, 1), (9000, 12000, 1)], (
        "a frase seguinte começa no milissegundo em que a anterior termina, sem cobri-lo duas vezes"
    )


async def test_the_same_milliseconds_of_another_part_are_a_first_telling_not_an_overlap(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    first_part = await rehearse(client, session_id, part=1)
    second = await client.post(
        f"{IR}/sessions/{session_id}/takes",
        headers={"X-Room-Device": DEVICE},
        data={"kind": "ensaio", "scope": "parte-2", "chunk_index": "2"},
        files={"file": ("ensaio.m4a", b"a equipe ensaiou a segunda parte", "audio/mp4")},
    )
    assert second.status_code == 200, second.text
    second_part = str(second.json()["take_id"])
    assert second_part != first_part
    told_first = await _chunk(client, session_id, first_part, 0, 9000, retelling=False)
    assert told_first.status_code == 200, told_first.text

    on_the_second = await _chunk(client, session_id, second_part, 0, 9000, retelling=False)

    assert on_the_second.status_code == 200, on_the_second.text
    assert [
        (one.take_id, one.starts_ms, one.ends_ms) for one in await current(db_session, session_id)
    ] == [(first_part, 0, 9000), (second_part, 0, 9000)], (
        "cada parte é uma gravação, e os mesmos milissegundos de outra não são a mesma fala"
    )


@pytest.mark.parametrize(
    ("starts_ms", "ends_ms"),
    [
        pytest.param(0, 9000, id="the frase that stood first"),
        pytest.param(0, 12000, id="the frase the old door wrote over it"),
    ],
)
async def test_a_retelling_at_the_exact_address_of_one_of_two_overlapping_frases_is_a_version(
    client: httpx.AsyncClient, db_session: AsyncSession, starts_ms: int, ends_ms: int
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    await told(client, session_id, take_id, 1)
    db_session.add(
        IRSegment(
            session_id=session_id,
            ordinal=2,
            take_id=take_id,
            starts_ms=0,
            ends_ms=12000,
            transcript="o trecho 1 com a pausa movida",
        )
    )
    await db_session.commit()

    told_again = await _chunk(client, session_id, take_id, starts_ms, ends_ms, retelling=True)

    assert told_again.status_code == 200, told_again.text
    retold = [
        one for one in await _slices(db_session, session_id) if one[:2] == (starts_ms, ends_ms)
    ]
    assert retold == [(starts_ms, ends_ms, 2)], (
        "o par que a porta antiga deixou recusava a recontagem dos dois endereços exatos"
    )


async def test_the_text_seam_refuses_a_frase_over_part_of_one_it_already_captured(
    seam: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session = await create_session(
        db_session, project_id=TABLET_TEAM, pericope="P03", language="pt"
    )
    await declare_rehearsal_parts(db_session, session, ["S1"])

    refused = await seam.post(
        f"{IR}/text-seam/back-translation/round",
        json={
            "sessionId": session.id,
            "frases": [
                {"clipKey": "S1", "coversFrom": 0, "coversTo": 9, "text": "Noemi voltou"},
                {"clipKey": "S1", "coversFrom": 4, "coversTo": 13, "text": "Noemi e Rute"},
            ],
        },
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "OVERLAPS_A_STANDING_FRASE"
    assert (4000, 13000) not in [
        (one.starts_ms, one.ends_ms) for one in await final_segments(db_session, session.id)
    ], "o runner gravava duas frases sobre os mesmos milissegundos"
