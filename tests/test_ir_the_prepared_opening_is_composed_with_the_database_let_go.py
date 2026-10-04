"""The opening prepared in the background is composed and voiced with the database let go.

`prepare_opening` runs on a session it opens for itself, so the double wraps the factory that
session comes from and reads `in_transaction()` on it when the models and the voice are called.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room import prepare_opening as prepare_opening_module
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.sessions import get_session

OPENING = "Uma família sai de Belém por falta de comida."


async def test_the_prepared_opening_is_composed_and_voiced_with_its_session_let_go(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_session.add(
        IRSession(
            id="panorama-1",
            pericope="OV-Ruth",
            status=IRSessionStatus.IN_PROGRESS,
            messages=[],
            coverage_state={},
            kept_takes={},
            back_translation={},
            language="pt",
        )
    )
    await db_session.commit()
    opens = prepare_opening_module.AsyncSessionLocal
    of_its_own: list[AsyncSession] = []
    held: dict[str, bool] = {}

    def a_session_of_its_own() -> AsyncSession:
        of_its_own.append(opens())
        return of_its_own[-1]

    async def composes(**_: Any) -> TurnOutcome:
        held["models"] = of_its_own[-1].in_transaction()
        return TurnOutcome(speech=OPENING, transcript="")

    async def voices(text: str, **_: Any):
        held["voice"] = of_its_own[-1].in_transaction()
        return (type("Voiced", (), {"key": "abertura-1"})(), False)

    monkeypatch.setattr(prepare_opening_module, "AsyncSessionLocal", a_session_of_its_own)
    monkeypatch.setattr(prepare_opening_module, "run_turn", composes)
    monkeypatch.setattr(prepare_opening_module, "synthesize_facilitator_speech", voices)

    await prepare_opening_module.prepare_opening("panorama-1")

    prepared = await get_session(db_session, "panorama-1")
    await db_session.refresh(prepared)
    assert prepared.prepared_speech == OPENING
    assert held == {"models": False, "voice": False}, (
        "a abertura preparada compunha e sintetizava com a leitura da sessão ainda aberta"
    )
