"""ENG-1333 — the consultant reads a session's coverage in her kinds and the ledger the voice reads.

Every case drives the real application through the door the Desk reads by, as a consultant
who belongs to no team.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSession
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.classify_coverage import classify_coverage
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.llm import CACHE_BREAK
from app.services.internalization_room.sessions import append_exchange, apply_coverage
from tests.baker import (
    grant_room_app_role,
    make_language,
    make_project,
    make_user,
    open_ir_session,
)
from tests.turn_harness import the_room_agent_is

IR = "/api/internalization-room"
P = "P01"
HER_KINDS = [
    "arc",
    "context",
    "tone",
    "function",
    "scene",
    "being",
    "place",
    "object",
    "time",
    "absence",
    "preserved",
]


@pytest.fixture()
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    from app.core.database import get_db
    from app.main import app

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
async def consultant(db_session: AsyncSession) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db_session, email="consultora@example.com")
    await grant_room_app_role(db_session, user.id, "consultant")
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


@pytest.fixture()
async def session(db_session: AsyncSession) -> IRSession:
    language = await make_language(db_session, name="Lang a", code="la")
    project = await make_project(db_session, language.id, name="Team a")
    return await open_ir_session(db_session, pericope=P, project_id=project.id)


async def _coverage(
    client: httpx.AsyncClient, headers: dict[str, str], session_id: str
) -> dict[str, Any]:
    answer = await client.get(f"{IR}/facilitator/sessions/{session_id}/coverage", headers=headers)
    assert answer.status_code == 200, answer.text
    return answer.json()


def _labels(body: dict[str, Any]) -> dict[str, str]:
    return {bead["key"]: bead["label"] for group in body["groups"] for bead in group["beads"]}


async def test_the_beads_come_grouped_by_kind_in_her_order_each_with_the_maps_label(
    client: httpx.AsyncClient, consultant: dict[str, str], session: IRSession
) -> None:
    body = await _coverage(client, consultant, session.id)

    assert [group["kind"] for group in body["groups"]] == HER_KINDS
    labels = _labels(body)
    assert labels["arc"] == "Level-1 arc"
    assert labels["scene:1"] == "Famine and exile to Moab"
    assert labels["being:S1:B2"] == "Elimelech"
    assert labels["place:S1:PL1"] == "Bethlehem"


def _states(body: dict[str, Any]) -> dict[str, str]:
    return {bead["key"]: bead["state"] for group in body["groups"] for bead in group["beads"]}


async def test_each_bead_carries_one_of_her_three_states(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session.coverage_state = {"scene:1": "engaged", "being:S1:B3": "surfaced"}
    await db_session.commit()

    states = _states(await _coverage(client, consultant, session.id))

    assert states["scene:1"] == "engaged"
    assert states["being:S1:B3"] == "surfaced"
    assert states["being:S1:B2"] == "untouched"
    assert set(states.values()) == {"engaged", "surfaced", "untouched"}


async def test_a_bead_stored_at_the_retired_partial_state_reads_mentioned_and_no_old_word_appears(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    session.coverage_state = {"scene:1": "partially_engaged", "scene:2": "engaged"}
    await db_session.commit()

    answer = await client.get(
        f"{IR}/facilitator/sessions/{session.id}/coverage", headers=consultant
    )

    assert answer.status_code == 200, answer.text
    assert _states(answer.json())["scene:1"] == "surfaced"
    for word in ("partially_engaged", "partial", "aflorado", "parcialmente", "not_encountered"):
        assert word not in answer.text


class _RecordingGuide:
    def __init__(self) -> None:
        self.systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.systems.append(system_prompt)
        return "A famine comes, and a family leaves Bethlehem. How would you tell that part?"


async def test_the_ledger_served_is_byte_for_byte_the_one_the_guide_reads_next(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session.coverage_state = {
        "scene:1": "engaged",
        "being:S1:B3": "surfaced",
        "place:S1:PL1": "partially_engaged",
    }
    await db_session.commit()
    guide = _RecordingGuide()
    the_room_agent_is(monkeypatch, turn=guide)

    ledger = (await _coverage(client, consultant, session.id))["ledger"]
    session = await append_exchange(db_session, session, team_utterance="", guide_response="hi")
    await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="we can start"),
        opening=False,
        guide_prompt=default_prompt(IRPromptKey.GUIDE)["prompt"],
        validator_prompt=default_prompt(IRPromptKey.VALIDATOR)["prompt"],
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )

    heard = guide.systems[0].partition(CACHE_BREAK)[2].lstrip("\n")
    assert heard.startswith(ledger)
    assert heard[len(ledger) :].startswith("\n\nMOMENT:")
    assert "WORKED WITH BY THE TEAM (engaged): S1 (v.1\u20132)" in ledger
    assert (
        "RAISED BY YOU, NOT YET TAKEN UP BY THE TEAM:\n  being: Naomi\n  place: Bethlehem\n"
        in ledger
    )


async def test_a_turn_that_engaged_an_element_shows_it_engaged_on_the_next_read(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = await _coverage(client, consultant, session.id)

    async def classifier(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        decision = {"element_id": "scene:1", "new_status": "engaged", "evidence": "a fome"}
        return json.dumps({"decisions": [decision]})

    the_room_agent_is(monkeypatch, classifier=classifier)
    settled = await classify_coverage(
        coverage_state=session.coverage_state or {},
        team_utterance="a fome levou a família de Belém para Moabe",
        guide_response="isso mesmo",
        classifier_prompt=default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"],
        pericope_num=P,
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )
    await apply_coverage(db_session, session.id, settled)
    after = await _coverage(client, consultant, session.id)

    assert _states(before)["scene:1"] == "untouched"
    assert "WORKED WITH BY THE TEAM (engaged): (nothing yet" in before["ledger"]
    assert _states(after)["scene:1"] == "engaged"
    assert "WORKED WITH BY THE TEAM (engaged): S1 (v.1\u20132)\n" in after["ledger"]
