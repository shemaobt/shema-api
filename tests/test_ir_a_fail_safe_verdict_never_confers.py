from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.release_harness import a_claimed_device, releases_of, team_headers, team_release
from tests.room_harness import (
    heard_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    stored_telling_back,
    the_analyst_reads,
    the_room_speaks,
)
from tests.turn_harness import the_room_agent_is

NOT_A_VERDICT = "isto não é um veredito"
PASSED = json.dumps({"verdict": "pass", "issues": []})


class Speaker:
    def __init__(self) -> None:
        self.verdicts: list[str] = []
        self.drafts = 0

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return self.verdicts.pop(0) if self.verdicts else PASSED
        self.drafts += 1
        return "Vocês contaram bem."


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> None:
    the_analyst_reads(monkeypatch)


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


async def test_a_clean_round_whose_verdict_falls_to_the_fail_safe_refuses_approval(
    client, speaker, db_session: AsyncSession
) -> None:
    project, credential = await a_claimed_device(db_session)
    client.headers.update(team_headers(credential))
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    speaker.verdicts = [NOT_A_VERDICT] * 3

    pressed = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )

    assert pressed.status_code == 200, pressed.text
    assert pressed.json()["used_fail_safe"] is True
    assert pressed.json()["checked"] is False, "uma linha A dava a passagem por conferida"
    refused = await client.post(team_release(session.id))
    assert refused.status_code == 200, refused.text
    assert refused.json()["blockers"] == ["telling_back_not_checked"], (
        "a equipe chegava à aprovação tendo ouvido só uma linha de segurança"
    )
    assert await releases_of(db_session, session.id) == []
    assert [
        (check.outcome, check.conferida)
        for check in (await stored_telling_back(db_session, session)).checks
    ] == [("fail_safe", False)]


async def test_a_press_after_a_fail_safe_round_checks_again_instead_of_replaying_the_line(
    client, speaker, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    report = await heard_every_part(db_session, session.id)
    speaker.verdicts = [NOT_A_VERDICT] * 3
    first = await press_terminei(client, session.id, report=report)
    assert first.json()["used_fail_safe"] is True
    speaker.verdicts = []

    again = await press_terminei(client, session.id, report=report)

    assert again.status_code == 200, again.text
    assert again.json()["used_fail_safe"] is False, "a segunda pressão repetia a linha A guardada"
    assert again.json()["checked"] is True, "a passagem limpa ficava presa na linha de segurança"
    assert speaker.drafts == 2
    assert [
        (check.outcome, check.conferida)
        for check in (await stored_telling_back(db_session, session)).checks
    ] == [("fail_safe", False), ("pass", True)]
