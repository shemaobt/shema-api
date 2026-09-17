"""The room runs for free: Ruth 1:1-5 from the opening to `done`, with no provider call.

The Guide and the Validator answer a script, the way every turn test here has them answer,
and the beads move on her keyword classifier instead of on a model. What that buys is the
whole loop — the pointer walking the scenes, the settle narrowing the list to the scene
the team is in, the practice credited off the invitation, the floor closing the passage —
exercised on every commit rather than paid for by hand.
"""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.internalization_room import IRSessionStatus
from app.services import internalization_room as room
from app.services.internalization_room import background, llm
from app.services.internalization_room.classify_coverage import classify_coverage_by_keywords
from tests.text_seam_harness import RUNNER_KEY, the_app

SEAM = "/api/internalization-room/text-seam"

INVITATION = (
    " Now rehearse this scene together in your own language; when you have finished, come "
    "back and tell me in English what you understood."
)

THE_GUIDE_SAYS = [
    "Welcome. Let me tell you the whole passage first, from the famine to the empty house.",
    "In the days of the judges a famine came over the land, and a family from Bethlehem of "
    "Judah went to sojourn in the fields of Moab. The passage opens on that loss, told plain, "
    "and the book begins here." + INVITATION,
    "Then Elimelech, the husband of Naomi, died, and she was left with her two sons." + INVITATION,
    "The sons married women of Moab, Orpah and Ruth, and they lived there about ten years."
    + INVITATION,
    "Then Mahlon and Chilion also died, and the woman was left alone." + INVITATION,
    "You have told the whole passage. Record the rehearsal in your own language.",
]

THE_TEAM_SAYS = [
    "We are here and ready, tell us the story.",
    "In the days of the judges there was a famine in the land, so Elimelech and Naomi with "
    "their sons Mahlon and Chilion, Ephrathites from Bethlehem of Judah, went sojourning in "
    "the fields of Moab. The narrator just tells it, the family left because of the famine.",
    "Elimelech died there in the fields of Moab, and Naomi was left with Mahlon and Chilion. "
    "The narrator tells of the death in a single clause, with the same plain image kept "
    "from before.",
    "Mahlon and Chilion took wives from the women of Moab, Orpah and Ruth, and Naomi stayed "
    "there with them about ten years, the marriages and the time passing. The narrator tells "
    "how long they lived there and speaks of the children only by their absence, and the "
    "source text keeps the wives apart from their husbands.",
    "Then Mahlon and Chilion died too there in the fields of Moab, and the woman Naomi was "
    "left alone, with her two sons gone and her husband gone. The narrator reports the "
    "deaths in one line and stops, the losses simply listed.",
]


class ScriptedRoom:
    """The Guide reads its lines in order; the Validator passes every one of them."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self._lines.pop(0) if self._lines else THE_GUIDE_SAYS[-1]


@asynccontextmanager
async def _handed(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield db_session


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )

    async def _never_voiced(text: str, **_: Any) -> None:
        raise AssertionError(f"a costura pediu um clipe ao sintetizador: {text!r}")

    def _no_wire(**_: Any) -> None:
        raise AssertionError("a sala abriu um cliente do provedor")

    monkeypatch.setattr(room, "synthesize_facilitator_speech", _never_voiced)
    monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", _no_wire)
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    transport = ASGITransport(app=the_app(db_session))
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Access-Code": RUNNER_KEY}
    ) as c:
        yield c


async def test_ruth_one_runs_to_done_on_the_keyword_classifier_and_no_provider(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted = ScriptedRoom(THE_GUIDE_SAYS)
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", scripted
    )
    pointers: list[str | None] = []

    async def by_keywords(**kwargs: Any) -> dict[str, str]:
        pointers.append(kwargs["scene_pointer"])
        return await classify_coverage_by_keywords(**kwargs)

    monkeypatch.setattr(background, "classify_coverage", by_keywords)

    created = await client.post(f"{SEAM}/session", json={"pericopeId": "P01", "language": "en"})
    assert created.status_code == 200, created.text
    session_id = created.json()["sessionId"]
    kickoff = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "kickoff": True})
    assert kickoff.status_code == 200, kickoff.text

    for said in THE_TEAM_SAYS:
        answered = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "text": said})
        assert answered.status_code == 200, answered.text
        assert answered.json()["outcome"] == "pass", answered.json()

    session = await room.get_session(db_session, session_id)
    assert session.status is IRSessionStatus.DONE, (
        "ninguém conseguia rodar a sala inteira sem pagar por ela; a passagem tem de chegar a "
        "done com o classificador por palavras e nenhuma chamada a provedor"
    )
    assert pointers == ["S1", "S1", "S2", "S3", "S4"], (
        "as contas avançam cena a cena: o ponteiro só anda quando a cena inteira engaja"
    )
