from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import internalization_room as room
from app.services.internalization_room.llm import CACHE_BREAK
from tests.text_seam_harness import RUNNER_KEY, the_app
from tests.turn_harness import the_room_agent_is

SEAM = "/api/internalization-room/text-seam/back-translation"
CLIPS = [
    {"key": "S1", "durationMs": 20000},
    {"key": "S2", "durationMs": 25000},
    {"key": "S3", "durationMs": 45000},
]
TELLING = [
    {
        "clipKey": "S1",
        "coversFrom": 0,
        "coversTo": 20,
        "text": "Noemi ouviu que o Senhor tinha dado pão ao seu povo e voltou com as noras.",
    },
    {
        "clipKey": "S2",
        "coversFrom": 0,
        "coversTo": 25,
        "text": "No caminho ela mandou as noras de volta, beijou as duas, e elas choraram alto.",
    },
    {
        "clipKey": "S3",
        "coversFrom": 0,
        "coversTo": 45,
        "text": "Orfa beijou a sogra e voltou, mas Rute se agarrou a Noemi à noite.",
    },
]
CLEAN = "No que vocês me traduziram, tem tudo o que a história conta — e nada a mais."
ON_FRASE_3 = {
    "kind": "nuance",
    "note": "O tempo ficou solto.",
    "frase": 3,
    "quote": "à noite",
    "story": "foi naquela mesma noite",
}
NAMES_FRASE_3 = (
    "Só um detalhe, na frase 3: vocês traduziram «à noite»; a história conta que foi naquela "
    "mesma noite."
)


class Analyst:
    def __init__(self) -> None:
        self.readings: list[dict[str, Any]] = []

    async def __call__(self, **_: Any) -> str:
        return json.dumps(self.readings.pop(0) if self.readings else {"findings": []})


class Speaker:
    def __init__(self) -> None:
        self.line = CLEAN
        self.drafts: list[str] = []

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.drafts.append(system_prompt.replace(CACHE_BREAK, ""))
        return self.line


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    reader = Analyst()
    the_room_agent_is(monkeypatch, analyst=reader)
    return reader


@pytest.fixture()
def speaker(monkeypatch: pytest.MonkeyPatch) -> Speaker:
    voice = Speaker()
    the_room_agent_is(monkeypatch, turn=voice)
    return voice


@pytest.fixture()
async def client(
    db_session: AsyncSession, analyst: Analyst, speaker: Speaker, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    async with httpx.AsyncClient(
        transport=ASGITransport(app=the_app(db_session)),
        base_url="http://test",
        headers={"X-Access-Code": RUNNER_KEY},
    ) as c:
        yield c


async def _a_round(client: httpx.AsyncClient, frases: list[dict], session_id: str = "") -> dict:
    if not session_id:
        declared = await client.post(
            f"{SEAM}/session",
            json={"pericopeId": "P02", "language": "Brazilian Portuguese", "clips": CLIPS},
        )
        assert declared.status_code == 200, declared.text
        session_id = str(declared.json()["sessionId"])
    played = await client.post(f"{SEAM}/round", json={"sessionId": session_id, "frases": frases})
    assert played.status_code == 200, played.text
    return dict(played.json())


async def _the_kept_rounds(db_session: AsyncSession, session_id: str) -> list:
    return room.back_translation_of(await room.get_session(db_session, session_id)).checks


async def test_a_round_that_names_a_nuance_keeps_its_frase_words_story_and_that_it_was_said(
    client, analyst, speaker, db_session
) -> None:
    analyst.readings = [{"findings": [ON_FRASE_3]}]
    speaker.line = NAMES_FRASE_3

    result = await _a_round(client, TELLING)

    kept = await _the_kept_rounds(db_session, result["sessionId"])
    assert [
        [(one.chunk, one.quote, one.story, one.voiced) for one in check.nuances] for check in kept
    ] == [[(3, "à noite", "foi naquela mesma noite", "now")]], (
        "a nuance da rodada só existia na memória do pedido e sumia com a resposta"
    )
