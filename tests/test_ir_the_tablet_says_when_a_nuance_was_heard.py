from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.room_harness import (
    PREFIX,
    heard_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    stored_telling_back,
    the_analyst_is_scripted,
    the_room_speaks,
)
from tests.turn_harness import the_room_agent_is

ON_FRASE_2 = {
    "kind": "nuance",
    "note": "O jeito de contar mudou.",
    "frase": 2,
    "quote": "contada de volta",
    "story": "a história conta de outro jeito",
}
NAMES_FRASE_2 = "Só um detalhe, na frase 2: vocês traduziram «contada de volta»."


class Speaker:
    def __init__(self) -> None:
        self.line = "Vocês contaram bem."
        self.briefs: list[str] = []

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.briefs.append(system_prompt)
        return self.line


async def _heard(client: Any, session_id: str, at: Any, **headers: str) -> Any:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/heard",
        json={"at": at},
        **({"headers": headers} if headers else {}),
    )


def _stamp(answer: Any) -> datetime | None:
    at = answer.json()["check_at"]
    return datetime.fromisoformat(at) if at else None


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch):
    return the_analyst_is_scripted(monkeypatch)


@pytest.fixture()
def speaker(monkeypatch: pytest.MonkeyPatch) -> Speaker:
    the_room_speaks(monkeypatch)
    voice = Speaker()
    the_room_agent_is(monkeypatch, turn=voice)
    return voice


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def test_the_verdict_answer_carries_the_stamp_of_the_round_that_gave_it(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    report = await heard_every_part(db_session, session.id)
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2

    first = await press_terminei(client, session.id, report=report)
    again = await press_terminei(client, session.id, report=report)

    assert first.status_code == 200, first.text
    rounds = (await stored_telling_back(db_session, session)).checks
    assert len(rounds) == 1
    assert _stamp(first) == rounds[0].at, (
        "o tablet não tinha como dizer qual veredito tocou até o fim"
    )
    assert _stamp(again) == rounds[0].at, (
        "o veredito guardado voltava sem a marca da rodada que o deu"
    )


async def test_a_verdict_the_tablet_played_to_its_end_is_kept_heard_on_the_servers_clock(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    pressed = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )
    before = datetime.now(UTC)

    heard = await _heard(client, session.id, pressed.json()["check_at"])

    assert heard.status_code == 200, heard.text
    assert heard.json() == {"marked": True}
    [kept] = (await stored_telling_back(db_session, session)).checks
    assert kept.heard_at is not None, "o tablet não tinha onde dizer que o veredito tocou até o fim"
    assert kept.heard_at >= before, "a hora era a do tablet, não a do servidor"
