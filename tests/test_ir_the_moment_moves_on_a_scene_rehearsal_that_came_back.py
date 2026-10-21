from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.internalization_room import MomentView
from app.services import internalization_room as room_service
from app.services.internalization_room.moment import moment_view
from tests.golden_rehearsal_harness import (
    a_golden_client,
    a_sent_rehearsal,
    after_the_break,
    an_open_session,
    the_room_stands_in,
)
from tests.text_seam_harness import GOLDEN, the_models_answer

CLOSING = (
    "O que chamou a atenção de vocês nessa cena? Conversem entre vocês. Essa cena ficou clara? "
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio."
)
SCENE_TWO_FENCED = {"at": "articulation", "part": 2, "fenced": True}


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with a_golden_client(db_session, monkeypatch) as c:
        yield c


async def _the_last_step(db: AsyncSession, session_id: str) -> dict[str, Any]:
    stored = await room_service.get_session(db, session_id)
    await db.refresh(stored)
    *_, guide = stored.messages
    return dict(guide["moment"])


async def test_a_marked_rehearsal_of_scene_2_arriving_as_the_turn_her_closing_ends_opens_scene_3(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client, "P02")
    await the_room_stands_in(db_session, session_id, SCENE_TWO_FENCED)
    the_models_answer(monkeypatch, f"A cena dois ficou inteira. {CLOSING}")

    sent = await a_sent_rehearsal(client, session_id, "S2")

    assert sent.status_code == 200, sent.text
    step = await _the_last_step(db_session, session_id)
    assert step["after"] == {"at": "internalization", "part": 3}, (
        "o ensaio marcado da cena 2 chegou neste turno e o fechamento não abriu a cena 3"
    )


async def test_a_golden_turn_carrying_scene_2_as_rehearsed_lets_her_closing_open_scene_3(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client, "P02")
    await the_room_stands_in(db_session, session_id, SCENE_TWO_FENCED)
    the_models_answer(monkeypatch, f"Vocês já contaram a cena dois. {CLOSING}")

    answered = await client.post(
        f"{GOLDEN}/turn",
        json={"sessionId": session_id, "teamText": "Já entendemos.", "sceneRehearsals": ["S2"]},
    )

    assert answered.status_code == 200, answered.text
    step = await _the_last_step(db_session, session_id)
    assert step["after"] == {"at": "internalization", "part": 3}, (
        "o roteiro dizia que a cena 2 tinha voltado e o fechamento não abriu a cena 3"
    )


async def test_a_marked_rehearsal_of_the_open_scene_moves_the_screens_label_to_its_articulation(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client, "P02")
    await the_room_stands_in(db_session, session_id, {"at": "internalization", "part": 2})
    the_models_answer(monkeypatch, "Obrigado. Vamos ver essa cena juntos.")

    sent = await a_sent_rehearsal(client, session_id, "S2")

    assert sent.status_code == 200, sent.text
    step = await _the_last_step(db_session, session_id)
    assert (step["after"], step["by"]) == (
        {"at": "articulation", "part": 2, "fenced": False},
        ["scene_rehearsal"],
    ), "o ensaio marcado da cena aberta chegou e a resposta neutra deixou a sala na Internalização"
    stored = await room_service.get_session(db_session, session_id)
    assert moment_view(stored) == MomentView(at="articulation", part=2, parts=3), (
        "a tela continuava na Internalização da cena que a equipe acabou de ensaiar"
    )


async def test_the_step_begins_in_the_moment_the_guide_was_told_after_the_rehearsal_arrived(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client, "P02")
    await the_room_stands_in(db_session, session_id, {"at": "internalization", "part": 2})
    agent = the_models_answer(monkeypatch, "Obrigado. Vamos ver essa cena juntos.")

    sent = await a_sent_rehearsal(client, session_id, "S2")

    assert sent.status_code == 200, sent.text
    told = after_the_break(agent.guide_systems[-1])
    assert "MOMENT: Articulation of part 2 of 3" in told, "a voz não leu o momento depois do ensaio"
    step = await _the_last_step(db_session, session_id)
    assert (step["before"], step["after"], step["by"]) == (
        {"at": "articulation", "part": 2, "fenced": False},
        {"at": "articulation", "part": 2, "fenced": False},
        ["scene_rehearsal"],
    ), "o passo guardou como início do turno um momento que não era o que a voz leu"
