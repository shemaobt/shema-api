"""The Golden doors that keep a scene rehearsal from its pieces and send it as a rehearsal turn.

Her golden scripts carry a scene rehearsal as the words the team translated, frase by frase.
These two doors keep that rehearsal from the pieces as text and send it through the same
function the tablet's send door calls, so a golden run reaches the voice the way a tablet's
«terminei» does. Like the other Golden doors they exist only where a runner key is
configured.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.internalization_room import IRSceneFrase, IRSceneRehearsal
from app.services.internalization_room import hearing, takes
from tests.hearing_harness import nothing_settles
from tests.text_seam_harness import BEARER, GOLDEN, RUNNER_KEY, the_app, the_models_answer

PIECES = ["Noemi disse: voltem.", "Rute ficou com ela."]


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
