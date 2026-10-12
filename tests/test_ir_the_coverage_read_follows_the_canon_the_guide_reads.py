"""ENG-1333 — the ledger the consultant reads is the one the voice reads, after a re-pin.

A session keeps the canon it opened with until its passage is approved, and the Guide's turn
reads its ledger under that pin. The consultant's read has to name the same beads, so this plays
a real tablet turn on a session whose canon has been replaced since it opened and holds the
ledger the Desk was served before that turn against the one the Guide was handed in it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.llm import CACHE_BREAK
from tests.baker import make_app, make_role
from tests.canon_harness import the_canon_moves_on
from tests.opening_harness import the_tablet_opens
from tests.release_harness import PREFIX, a_claimed_device, at_the_desk
from tests.room_harness import room_client, the_bucket_is_in_memory, the_room_speaks
from tests.tablet_turn_harness import the_team_says, the_turn_is_scripted

P = "P03"
NEW_PIN = "a" * 40
BEINGS = "**3A — Beings**\n"
ELIMELECH = "[[B2-Elimelech]] — אֱלִימֶלֶךְ / Elimelech\n\n"


def _the_kept_p03_names_elimelech(tree: Path) -> None:
    (page,) = (tree / "vendor" / "meaning-map").glob("P03-*.md")
    page.write_text(page.read_text(encoding="utf-8").replace(BEINGS, BEINGS + ELIMELECH))


class Prompts:
    def __init__(self) -> None:
        self.read: list[str] = []


@pytest.fixture()
def prompts(monkeypatch: pytest.MonkeyPatch) -> Prompts:
    handed = Prompts()

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Rute disse que ia junto com Noemi")

    async def model(*, system_prompt: str, user_content: str, **_: Any) -> str:
        handed.read.append(system_prompt)
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "O que mais voces lembram da estrada?"

    the_turn_is_scripted(monkeypatch, heard=heard, model=model)
    return handed


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    the_room_speaks(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def test_the_ledger_served_is_the_one_the_guide_is_handed_after_the_canon_is_replaced(
    client, db_session, room_app, prompts, monkeypatch, tmp_path
) -> None:
    project, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, project)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_names_elimelech)

    served = await client.get(
        f"{PREFIX}/facilitator/sessions/{opened['session_id']}/coverage", headers=desk
    )
    await the_team_says(client, tablet, opened["session_id"], "depois")

    ledger = served.json()["ledger"]
    (guide,) = [system for system in prompts.read if "corrected_response" not in system]
    assert served.status_code == 200, served.text[:300]
    assert "being: Elimelech, " in ledger
    assert guide.partition(CACHE_BREAK)[2].lstrip("\n").startswith(ledger)
