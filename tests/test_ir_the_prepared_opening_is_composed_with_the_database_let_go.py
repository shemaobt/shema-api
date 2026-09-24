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
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.sessions import get_session
from tests.baker import make_language, make_project

OPENING = "Uma família sai de Belém por falta de comida."


async def test_the_prepared_opening_is_composed_and_voiced_with_its_session_let_go(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The necklace read the ticket ENG-1085 fix added is a query of its own: staged with no
    team behind it, `necklace_coverage_state` never touches the database and this test would
    hold with or without where that read sits — a team with a necklace to carry is what makes
    the read real and the ordering around it worth pinning.
    """
    language = await make_language(db_session, name="Solta o banco", code="dbg")
    team = await make_project(db_session, language.id, name="Solta o banco")
    keys = element_keys("P01")
    earlier = await room.create_session(db_session, pericope="P01", project_id=team.id)
    await room.apply_coverage(db_session, earlier.id, {keys[0]: CoverageStatus.ENGAGED.value})

    db_session.add(
        IRSession(
            id="panorama-1",
            pericope="OV-Ruth",
            project_id=team.id,
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
