from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.internalization_room import IRSceneFrase, IRSceneRehearsal
from app.services import internalization_room as room_service
from app.services.internalization_room import hearing, takes
from tests.hearing_harness import nothing_settles
from tests.text_seam_harness import (
    BEARER,
    GOLDEN,
    GUIDE_LINE,
    RUNNER_KEY,
    the_app,
    the_models_answer,
)

PIECES = ["Noemi disse: voltem.", "Rute ficou com ela."]
TWO_PT = (
    "[A equipe ensaiou esta cena na língua materna e traduziu o ensaio da cena frase por frase "
    "(2 frases). Segue a tradução, na ordem:]"
)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    the_models_answer(monkeypatch)
    nothing_settles(monkeypatch)

    async def _never_heard(*_: Any, **__: Any) -> Any:
        raise AssertionError("a porta dourada pediu ao reconhecedor que ouvisse uma frase")

    def _never_stored(*_: Any, **__: Any) -> Any:
        raise AssertionError("a porta dourada tocou o balde")

    monkeypatch.setattr(hearing, "transcribe_audio", _never_heard)
    monkeypatch.setattr(hearing, "transcribe_audio_detailed", _never_heard)
    monkeypatch.setattr(takes, "_store", _never_stored)
    transport = ASGITransport(app=the_app(db_session))
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=BEARER) as c:
        yield c


async def an_open_session(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{GOLDEN}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )
    assert created.status_code == 200, created.text
    session_id = str(created.json()["sessionId"])
    opened = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "session_start"}
    )
    assert opened.status_code == 200, opened.text
    return session_id


async def a_kept_rehearsal(
    client: httpx.AsyncClient,
    session_id: str,
    pieces: list[str] = PIECES,
    scene: str | None = "S2",
) -> httpx.Response:
    return await client.post(
        f"{GOLDEN}/rehearsal", json={"sessionId": session_id, "sceneId": scene, "pieces": pieces}
    )


async def test_a_rehearsal_kept_from_her_pieces_has_one_frase_for_each_in_her_order(
    client, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client)

    kept = await a_kept_rehearsal(client, session_id)

    assert kept.status_code == 200, kept.text
    rehearsal_id = kept.json()["rehearsalId"]
    words = await db_session.scalars(
        select(IRSceneFrase.transcript)
        .where(IRSceneFrase.rehearsal_id == rehearsal_id)
        .order_by(IRSceneFrase.starts_ms)
    )
    assert list(words) == ["Noemi disse: voltem.", "Rute ficou com ela."]
    scene = await db_session.scalar(
        select(IRSceneRehearsal.scene).where(IRSceneRehearsal.id == rehearsal_id)
    )
    assert scene == "S2"


async def test_a_golden_rehearsal_is_marked_as_no_tablets_and_reached_neither_the_recognizer_nor_the_bucket(  # noqa: E501
    client, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client)

    kept = await a_kept_rehearsal(client, session_id)

    assert kept.status_code == 200, kept.text
    rehearsal_id = kept.json()["rehearsalId"]
    rehearsal = await db_session.scalar(
        select(IRSceneRehearsal).where(IRSceneRehearsal.id == rehearsal_id)
    )
    assert rehearsal is not None
    assert (rehearsal.device_id, rehearsal.verified_at) == ("golden-runner", None)
    frases = await db_session.scalars(
        select(IRSceneFrase.verified_at).where(IRSceneFrase.rehearsal_id == rehearsal_id)
    )
    assert list(frases) == [None, None]


async def a_sent_rehearsal(
    client: httpx.AsyncClient,
    session_id: str,
    rehearsal_id: str,
    turn_id: str = "turno-1",
    **more: Any,
) -> httpx.Response:
    return await client.post(
        f"{GOLDEN}/rehearsal/send",
        json={"sessionId": session_id, "rehearsalId": rehearsal_id, "turnId": turn_id, **more},
    )


async def test_a_golden_rehearsal_sent_hands_the_guide_her_note_with_the_count_then_the_pieces(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client)
    rehearsal_id = (await a_kept_rehearsal(client, session_id)).json()["rehearsalId"]
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, rehearsal_id)

    assert sent.status_code == 200, sent.text
    handed = f"{TWO_PT} Noemi disse: voltem. Rute ficou com ela."
    assert agent.guide_inputs == [handed]
    body = sent.json()
    assert (body["guideText"], body["outcome"], body["transcript"]) == (GUIDE_LINE, "pass", handed)


async def test_the_turn_a_golden_rehearsal_leaves_is_a_checking_turn_by_the_servers_mark(
    client, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client)
    rehearsal_id = (await a_kept_rehearsal(client, session_id)).json()["rehearsalId"]

    sent = await a_sent_rehearsal(client, session_id, rehearsal_id)

    assert sent.status_code == 200, sent.text
    stored = await room_service.get_session(db_session, session_id)
    await db_session.refresh(stored)
    note, words, guide = stored.messages[-3:]
    assert (note["text"], note.get("room_note")) == (TWO_PT, True)
    assert (words["text"], words.get("room_note")) == (
        "Noemi disse: voltem. Rute ficou com ela.",
        None,
    )
    assert guide["scene_rehearsal"] == {
        "rehearsal_id": rehearsal_id,
        "n": 1,
        "frases": 2,
        "scene": "S2",
    }


async def test_a_golden_rehearsal_sent_again_under_another_turn_id_is_refused_as_sent(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client)
    rehearsal_id = (await a_kept_rehearsal(client, session_id)).json()["rehearsalId"]
    first = await a_sent_rehearsal(client, session_id, rehearsal_id, "turno-a")
    assert first.status_code == 200, first.text
    agent = the_models_answer(monkeypatch)

    again = await a_sent_rehearsal(client, session_id, rehearsal_id, "turno-b")

    assert again.status_code == 409, again.text
    assert again.json()["code"] == "SCENE_REHEARSAL_SENT"
    assert agent.guide_inputs == []


async def test_a_golden_rehearsal_sent_while_another_send_stands_is_told_it_is_being_sent(
    client, db_session: AsyncSession, monkeypatch
) -> None:
    session_id = await an_open_session(client)
    rehearsal_id = (await a_kept_rehearsal(client, session_id)).json()["rehearsalId"]
    await db_session.execute(
        update(IRSceneRehearsal)
        .where(IRSceneRehearsal.id == rehearsal_id)
        .values(sent_at=datetime.now(UTC), sent_turn_id="turno-em-voo")
    )
    await db_session.commit()
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, rehearsal_id, "turno-novo")

    assert sent.status_code == 409, sent.text
    assert sent.json()["code"] == "SCENE_REHEARSAL_SENDING"
    assert agent.guide_inputs == []


async def test_a_golden_send_closing_an_attempt_that_is_not_the_current_one_is_refused_and_unheard(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client)
    rehearsal_id = (await a_kept_rehearsal(client, session_id)).json()["rehearsalId"]
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(
        client, session_id, rehearsal_id, closes="5f0c0f0e-7b0a-4a52-9c0e-2f5d3c1b9a11"
    )

    assert sent.status_code == 409, sent.text
    assert sent.json()["code"] == "RESTART_OUT_OF_ORDER"
    assert agent.guide_inputs == []


async def test_a_golden_rehearsal_with_no_frase_is_refused_and_stays_unsent(
    client, db_session: AsyncSession, monkeypatch
) -> None:
    session_id = await an_open_session(client)
    rehearsal_id = (await a_kept_rehearsal(client, session_id, pieces=[])).json()["rehearsalId"]
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, rehearsal_id)

    assert sent.status_code == 422, sent.text
    assert agent.guide_inputs == []
    claimed = await db_session.scalar(
        select(IRSceneRehearsal.sent_turn_id).where(IRSceneRehearsal.id == rehearsal_id)
    )
    assert claimed is None
