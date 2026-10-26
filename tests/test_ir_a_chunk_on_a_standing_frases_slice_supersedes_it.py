from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment
from app.services.internalization_room.sessions import (
    back_translation_of,
    save_back_translation,
)
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.hard_stretch_harness import (
    AUDIO,
    DEVICE,
    IR,
    MemoryStore,
    a_session,
    current,
    marks,
    rehearse,
    retro_takes,
    row,
    tell,
    told,
)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router as room_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    said: list[str] = []

    async def _transcribe(audio: bytes, **_: Any) -> str:
        return said.pop(0) if said else "algo que a equipe contou"

    monkeypatch.setattr(bt_api, "heard", _transcribe)
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
        yield c


async def _history(
    db: AsyncSession, session_id: str, starts_ms: int, ends_ms: int
) -> list[IRSegment]:
    result = await db.execute(
        select(IRSegment)
        .where(
            IRSegment.session_id == session_id,
            IRSegment.starts_ms == starts_ms,
            IRSegment.ends_ms == ends_ms,
        )
        .order_by(IRSegment.tellings)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars().all())


async def test_a_telling_on_a_standing_frases_slice_under_a_new_key_is_that_frase_told_again(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    await told(client, session_id, take_id, 2)

    again = await tell(client, session_id, take_id, 2, saying="o trecho 2 de novo")

    assert again.status_code == 200, again.text
    assert again.json()["frase"] == 2, (
        "a frase contada de novo ganhava o número seguinte em vez de ficar com o seu"
    )
    assert [
        (one.starts_ms, one.ends_ms, one.tellings) for one in await current(db_session, session_id)
    ] == [
        (0, 9000, 1),
        (9000, 18000, 2),
    ], "duas frases de pé sobre a mesma fatia, as duas lidas pelo analista"
    history = await _history(db_session, session_id, 9000, 18000)
    assert [one.transcript for one in history] == ["o trecho 2", "o trecho 2 de novo"], (
        "a primeira contada sumia da história da frase"
    )
    assert history[0].superseded_by_id == history[1].id, (
        "a contada antes não dizia qual contada tomou o seu lugar"
    )


async def test_the_second_telling_of_a_slice_keeps_the_frases_place_in_its_recording_too(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    await told(client, session_id, take_id, 2)

    again = await tell(client, session_id, take_id, 2, saying="o trecho 2, de outro jeito")

    assert again.status_code == 200, again.text
    assert sorted(one.ordinal for one in await retro_takes(db_session, session_id)) == [1, 2, 2], (
        "a gravação da recontagem ganhava o lugar seguinte em vez do lugar da frase"
    )


async def test_the_third_telling_of_one_slice_under_new_keys_asks_for_a_person_once(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    await told(client, session_id, take_id, 1)

    second = await tell(client, session_id, take_id, 1, saying="de novo")
    third = await tell(client, session_id, take_id, 1, saying="mais uma vez")

    assert [second.json()["needs_person"], third.json()["needs_person"]] == [False, True], (
        "a frase contada três vezes no mesmo lugar não chamava ninguém"
    )
    assert [one.tellings for one in await current(db_session, session_id)] == [3]
    assert len(await marks(db_session, session_id)) == 1


async def test_a_frase_told_again_after_a_check_is_the_second_pass_in_its_row_and_answer(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    await told(client, session_id, take_id, 1)
    session = await row(db_session, session_id)
    state = back_translation_of(session)
    state.analysed_segment_ids = [one.id for one in await current(db_session, session_id)]
    await save_back_translation(db_session, session, state)

    again = await tell(client, session_id, take_id, 1, saying="depois da conferência")

    assert again.json()["pass_number"] == 2
    assert [(one.pass_number, one.tellings) for one in await current(db_session, session_id)] == [
        (2, 2)
    ], "a frase contada de novo depois da conferência não seguia a regra da segunda passada"


async def test_a_telling_at_an_untold_pieces_slice_tells_the_piece_and_leaves_no_second_row(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    await told(client, session_id, take_id, 1)
    whole = (await current(db_session, session_id))[0]
    divided = await client.post(
        f"{IR}/sessions/{session_id}/segments/{whole.id}/divide",
        headers={"X-Room-Device": DEVICE},
        json={"at_ms": 4500},
    )
    assert divided.status_code == 200, divided.text
    client.said.append("a metade que faltava")  # type: ignore[attr-defined]
    head = await client.post(
        f"{IR}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Device": DEVICE},
        data={"take_id": take_id, "starts_ms": "0", "ends_ms": "4500"},
        files={"file": ("trecho.m4a", AUDIO, "audio/mp4")},
    )

    assert head.status_code == 200, head.text
    assert [
        (one.starts_ms, one.ends_ms, one.transcript)
        for one in await current(db_session, session_id)
        if one.parent_id is not None
    ] == [(0, 4500, "a metade que faltava"), (4500, 9000, None)], (
        "o trecho por contar ficava de pé ao lado de uma cópia contada do mesmo lugar"
    )


async def test_a_telling_on_another_slice_is_a_new_frase_beside_the_one_standing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    await told(client, session_id, take_id, 1)

    next_one = await tell(client, session_id, take_id, 2, saying="o trecho 2")

    assert next_one.status_code == 200, next_one.text
    assert next_one.json()["frase"] == 2
    assert [
        (one.starts_ms, one.ends_ms, one.tellings) for one in await current(db_session, session_id)
    ] == [(0, 9000, 1), (9000, 18000, 1)], (
        "a frase de outro lugar tomava o lugar da que estava de pé"
    )


async def test_a_request_carrying_the_old_retelling_flag_is_answered_like_one_without_it(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    answers = []
    rows = []
    for flag in (False, True):
        session_id = await a_session(db_session)
        take_id = await rehearse(client, session_id)
        await tell(client, session_id, take_id, 1, saying="o trecho 1")
        again = await tell(client, session_id, take_id, 1, saying="o trecho 1 de novo", again=flag)
        assert again.status_code == 200, again.text
        answers.append({k: v for k, v in again.json().items() if k != "session_id"})
        rows.append(
            [
                (one.starts_ms, one.ends_ms, one.ordinal, one.tellings)
                for one in await current(db_session, session_id)
            ]
        )

    assert answers[0] == answers[1], "a bandeira antiga mudava a resposta da porta"
    assert rows[0] == rows[1] == [(0, 9000, 1, 2)], (
        "a bandeira antiga mudava o que a porta guardava"
    )


async def test_the_same_recording_sent_again_under_a_new_key_is_a_resend_not_a_telling(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    first = await tell(client, session_id, take_id, 1, saying="o trecho 1", audio=b"a gravacao")

    resent = await tell(
        client, session_id, take_id, 1, saying="outra coisa", audio=b"a gravacao", queued=False
    )

    assert resent.status_code == 200, resent.text
    assert resent.json() == first.json(), "o reenvio da mesma gravação respondia como outra fala"
    assert [(one.tellings, one.transcript) for one in await current(db_session, session_id)] == [
        (1, "o trecho 1")
    ], "a mesma gravação de volta, depois de a resposta se perder, contava como mais uma fala"


async def test_the_chunks_door_asks_the_one_function_that_says_what_a_resend_is(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import internalization_room as room

    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    first = await tell(client, session_id, take_id, 1, saying="o trecho 1", audio=b"uma gravacao")
    monkeypatch.setattr(room, "is_a_resend", lambda *_: True, raising=False)

    resent = await tell(
        client, session_id, take_id, 1, saying="outra coisa", audio=b"outra gravacao diferente"
    )

    assert resent.status_code == 200, resent.text
    assert resent.json() == first.json(), "a porta dos trechos decidia o reenvio por conta própria"
    assert [(one.tellings, one.transcript) for one in await current(db_session, session_id)] == [
        (1, "o trecho 1")
    ], "a porta dos trechos não perguntava à função que diz o que é um reenvio"


async def test_a_resend_of_the_telling_that_made_a_hard_stretch_still_asks_for_a_person(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    take_id = await rehearse(client, session_id)
    await tell(client, session_id, take_id, 1, saying="o trecho 1", audio=b"a primeira")
    await tell(client, session_id, take_id, 1, saying="o trecho 1, outra vez", audio=b"a segunda")
    crossing = await tell(
        client, session_id, take_id, 1, saying="o trecho 1, a terceira", audio=b"a terceira"
    )
    assert crossing.json()["needs_person"] is True, crossing.text

    resent = await tell(
        client, session_id, take_id, 1, saying="outra coisa", audio=b"a terceira", queued=False
    )

    assert resent.status_code == 200, resent.text
    assert resent.json() == crossing.json(), (
        "a resposta que pedia uma pessoa se perdeu e o reenvio dizia que ninguém era preciso"
    )
