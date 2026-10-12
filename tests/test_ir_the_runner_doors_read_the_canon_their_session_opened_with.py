"""ENG-1577 — the runner's two doors judge a session by the canon it opened with.

ENG-1219 made a session keep the canon it opened with until its passage is approved, and the
tablet reads it that way. The text seam's round and the golden doors' turn are the same room
driven by text, so a re-pin that lands between a runner's session and its turn must not hand
that session the new map. A canon is re-pinned here the way `the_canon_moves_on` publishes
one: the pre-move canon is kept under its pin, the first scene of its P02 is titled in a way
the vendored one is not, and which map a door read is read off what the models were handed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import internalization_room as room
from tests.canon_harness import the_canon_moves_on
from tests.room_harness import nothing_is_read_ahead, the_analyst_is_scripted
from tests.text_seam_harness import RUNNER_KEY, the_app
from tests.turn_harness import the_room_agent_is

SEAM = "/api/internalization-room/text-seam/back-translation"
NEW_PIN = "a" * 40
VENDORED_ROLE = "Role: hearer of the news; rises and sets out"
KEPT_ROLE = "Role: THE KEPT MAP'S HEARER OF THE NEWS"
VENDORED_FIRST_SCENE = "Hearing and setting out"
KEPT_FIRST_SCENE = "The kept first scene"
CLIPS = [{"key": "S1", "durationMs": 20000}]
FRASES = [
    {
        "clipKey": "S1",
        "coversFrom": 0,
        "coversTo": 10,
        "text": "Noemi ouviu que o Senhor tinha dado pão ao seu povo e decidiu voltar.",
    }
]


def _the_kept_p02_is_told_its_own_way(tree: Path) -> None:
    (page,) = (tree / "vendor" / "meaning-map").glob("P02-*.md")
    told = page.read_text(encoding="utf-8")
    told = told.replace(VENDORED_ROLE, KEPT_ROLE).replace(VENDORED_FIRST_SCENE, KEPT_FIRST_SCENE)
    page.write_text(told, encoding="utf-8")


class Voice:
    def __init__(self) -> None:
        self.seen: list[str] = []
        self.refuses = False

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        self.seen.append(system_prompt)
        if "corrected_response" in system_prompt:
            if self.refuses:
                return json.dumps({"verdict": "regenerate", "issues": [{"problem": "added"}]})
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vocês traduziram bem."


@pytest.fixture()
async def seam(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )

    async def _never_voiced(text: str, **_: Any) -> None:
        raise AssertionError(f"a costura pediu um clipe ao sintetizador: {text!r}")

    monkeypatch.setattr(room, "synthesize_facilitator_speech", _never_voiced)
    nothing_is_read_ahead(monkeypatch)
    transport = ASGITransport(app=the_app(db_session))
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Access-Code": RUNNER_KEY}
    ) as c:
        yield c


async def _a_session(seam: httpx.AsyncClient) -> str:
    declared = await seam.post(
        f"{SEAM}/session", json={"pericopeId": "P02", "language": "English", "clips": CLIPS}
    )
    assert declared.status_code == 200, declared.text
    return str(declared.json()["sessionId"])


async def _a_round(seam: httpx.AsyncClient, session_id: str) -> dict[str, Any]:
    played = await seam.post(f"{SEAM}/round", json={"sessionId": session_id, "frases": FRASES})
    assert played.status_code == 200, played.text
    return dict(played.json())


async def test_a_text_seam_session_open_when_a_new_canon_is_published_is_judged_against_its_own_map(
    seam, monkeypatch, tmp_path
) -> None:
    analyst = the_analyst_is_scripted(monkeypatch)
    the_room_agent_is(monkeypatch, turn=Voice(), analyst=analyst)
    kept_session = await _a_session(seam)
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p02_is_told_its_own_way)
    fresh_session = await _a_session(seam)

    await _a_round(seam, fresh_session)
    await _a_round(seam, kept_session)
    read_by_fresh, read_by_kept = analyst.shown

    assert KEPT_ROLE in read_by_kept, "o analista conferiu a sessão antiga contra o mapa novo"
    assert VENDORED_ROLE not in read_by_kept
    assert VENDORED_ROLE in read_by_fresh, "a sessão aberta depois da troca deixou de ler o novo"
    assert KEPT_ROLE not in read_by_fresh


async def test_a_text_seam_session_open_when_a_new_canon_is_published_is_pointed_at_its_own_scene(
    seam, monkeypatch, tmp_path
) -> None:
    voice = Voice()
    voice.refuses = True
    the_room_agent_is(monkeypatch, turn=voice, analyst=the_analyst_is_scripted(monkeypatch))
    kept_session = await _a_session(seam)
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p02_is_told_its_own_way)
    fresh_session = await _a_session(seam)

    from_fresh = await _a_round(seam, fresh_session)
    from_kept = await _a_round(seam, kept_session)

    assert from_kept["outcome"] == "fail_safe"
    assert from_kept["spoken"].endswith("this is the part about the kept first scene."), (
        "o aviso de segurança apontou para a primeira cena do mapa novo"
    )
    assert from_fresh["spoken"].endswith("this is the part about hearing and setting out."), (
        "a sessão aberta depois da troca perdeu o ponteiro do mapa que serve"
    )
