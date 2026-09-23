"""The room runs for free: Ruth 1:1-5 from the opening to `done`, with no provider call.

The Guide and the Validator answer a script, the way every turn test here has them answer,
and the beads move on her keyword classifier instead of on a model. What that buys is the
whole loop — the settle offering every bead the team has not yet engaged, the practice
credited off the team's own report that it rehearsed (never
off the telling-back itself — ENG-788), the floor closing the passage — exercised on every
commit rather than paid for by hand.
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
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.classify_coverage import (
    _shown_label,
    _words,
    classify_coverage_by_keywords,
)
from app.services.internalization_room.coverage import CoverageStatus, floor_met
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
    "Tell me once more how the sons died and the woman was left alone." + INVITATION,
    "You have told the whole passage. Record the rehearsal in your own language.",
]

#: The team's own word that the rehearsal happened. Only this marks a scene practiced;
#: the telling that follows is for the Guide to check, and the app never grades it.
REPORTED = "We have rehearsed it in our own language. "

THE_TEAM_SAYS = [
    "We are here and ready, tell us the story.",
    REPORTED
    + "In the days of the judges there was a famine in the land, so Elimelech and Naomi with "
    "their sons Mahlon and Chilion, Ephrathites from Bethlehem of Judah, went sojourning in "
    "the fields of Moab. The narrator just tells it, the family left because of the famine.",
    REPORTED
    + "Elimelech died there in the fields of Moab, and Naomi was left with Mahlon and Chilion. "
    "The narrator tells of the death in a single clause, with the same plain image kept "
    "from before.",
    REPORTED
    + "Mahlon and Chilion took wives from the women of Moab, Orpah and Ruth, and Naomi stayed "
    "there with them about ten years, the marriages and the time passing. The narrator tells "
    "how long they lived there and speaks of the children only by their absence, and the "
    "source text keeps the wives apart from their husbands.",
    REPORTED
    + "Then Mahlon and Chilion died too there in the fields of Moab, and the woman Naomi was "
    "left alone, with her two sons gone and her husband gone. The narrator reports the "
    "deaths in one line and stops, the losses simply listed.",
    REPORTED + "Mahlon and Chilion died, the deaths of the sons, and Naomi was left alone.",
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
    monkeypatch.setattr(background, "classify_coverage", classify_coverage_by_keywords)

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


#: The four scenes told in the team's words, and never a word of scene one's silence: the
#: Guide names the famine, so that silence is only ever mentioned.
THE_TEAM_LEAVES_THE_SILENCE_UNTOLD = [
    "We are here and ready, tell us the story.",
    "Elimelech and Naomi and their sons Mahlon and Chilion lived in Bethlehem of Judah.",
    "Then Elimelech died, and his death left Naomi alone and the two sons.",
    "The sons married Orpah and Ruth, women of Moab, and lived there about ten years.",
    "Then Mahlon and Chilion died too, the deaths of the sons, and the woman Naomi was alone.",
]


async def test_a_silence_only_mentioned_in_scene_one_does_not_hold_back_the_later_scenes(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    beads = elements_for("P01")
    silence = next(element for element in beads if element.key == "absence:1")
    for said in THE_TEAM_LEAVES_THE_SILENCE_UNTOLD:
        assert not _words(said) & _words(_shown_label(silence)), said
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"],
        "call_agent",
        ScriptedRoom(THE_GUIDE_SAYS),
    )
    monkeypatch.setattr(background, "classify_coverage", classify_coverage_by_keywords)

    created = await client.post(f"{SEAM}/session", json={"pericopeId": "P01", "language": "en"})
    assert created.status_code == 200, created.text
    session_id = created.json()["sessionId"]
    kickoff = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "kickoff": True})
    assert kickoff.status_code == 200, kickoff.text
    for said in THE_TEAM_LEAVES_THE_SILENCE_UNTOLD:
        answered = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "text": said})
        assert answered.status_code == 200, answered.text

    session = await room.get_session(db_session, session_id)
    await db_session.refresh(session)
    ledger = session.coverage_state
    engaged_scenes = {
        element.scene
        for element in beads
        if element.scene is not None and ledger[element.key] == CoverageStatus.ENGAGED.value
    }
    assert engaged_scenes == {1, 2, 3, 4}, (
        "um silêncio da cena 1 só levantado segurava a oferta na cena 1 pelo resto da sessão: "
        "a equipe contava as cenas 2, 3 e 4 e nenhuma conta delas se movia"
    )
    assert ledger["absence:1"] == CoverageStatus.SURFACED.value, (
        "o Guia falou da fome e a equipe nunca tocou o silêncio: levantado, não engajado"
    )
    assert not floor_met(ledger, "P01"), (
        "o piso pede toda conta concreta engajada; um silêncio só mencionado deixa a sala aberta"
    )
