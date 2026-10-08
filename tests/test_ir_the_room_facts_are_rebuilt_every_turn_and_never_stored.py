import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.llm import CACHE_BREAK
from app.services.internalization_room.prompt_blocks import coverage_status_block
from app.services.internalization_room.run_turn import run_turn
from app.services.internalization_room.sessions import get_session
from tests.release_harness import (
    PREFIX,
    a_claimed_device,
    ready_session,
    team_headers,
    team_release,
)
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.tablet_turn_harness import the_room_opens, the_team_says, the_turn_is_scripted
from tests.text_seam_harness import ScriptedAgent
from tests.turn_harness import the_room_agent_is

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"

EN = "\N{EN DASH}"
EARLIER_APPROVED_STARTED = (
    f"EARLIER PASSAGES FOR THIS TEAM: Approved: Ruth 1:1{EN}5. "
    f"Started, not approved yet: Ruth 1:6{EN}14."
)
EARLIER_BOTH_APPROVED = f"EARLIER PASSAGES FOR THIS TEAM: Approved: Ruth 1:1{EN}5, Ruth 1:6{EN}14."
FAMILIARIZATION = (
    "MOMENT: Familiarization \N{EM DASH} the whole passage; no part has been opened yet."
)
LEDGER_MARKERS = ("EARLIER PASSAGES FOR THIS TEAM", "COVERED (engaged)", "REMAINING", "MOMENT:")


class _Recording:
    def __init__(self) -> None:
        self.guide: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide.append(system_prompt)
        return "Vamos ouvir a passagem."


@pytest.fixture
def recording(monkeypatch: pytest.MonkeyPatch) -> _Recording:
    models = _Recording()
    the_room_agent_is(monkeypatch, turn=models)
    return models


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


async def _turn(coverage_state: dict[str, str], earlier_passages: dict[str, str]) -> None:
    await run_turn(
        transcript="e a fome, por que ela veio?",
        coverage_state=coverage_state,
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        language_code="pt",
        settings=_settings(),
        earlier_passages=earlier_passages,
    )


async def test_the_earlier_passages_line_follows_the_ledger_and_the_moment_comes_after_it(
    recording: _Recording,
) -> None:
    await _turn(initial_state(P), {"P01": "approved", "P02": "started"})

    after_the_break = recording.guide[0].partition(CACHE_BREAK)[2]
    assert after_the_break == (
        f"{coverage_status_block(initial_state(P), P)}\n\n{EARLIER_APPROVED_STARTED}"
        f"\n\n{FAMILIARIZATION}"
    ), "a linha das passagens anteriores não vinha logo depois do ledger, no fim do que o Guia lê"


async def test_what_the_guide_reads_before_the_ledger_is_the_same_on_two_turns_of_a_session(
    recording: _Recording,
) -> None:
    await _turn(initial_state(P), {"P01": "approved", "P02": "started"})
    await _turn(
        merge(initial_state(P), pericope_num=P, engaged=["scene:1"]),
        {"P01": "approved", "P02": "approved"},
    )

    first, second = recording.guide
    assert EARLIER_BOTH_APPROVED in second.partition(CACHE_BREAK)[2]
    assert first.partition(CACHE_BREAK)[2] != second.partition(CACHE_BREAK)[2]
    assert first.partition(CACHE_BREAK)[0] == second.partition(CACHE_BREAK)[0], (
        "o que vem antes do ledger mudava de um turno para o outro, e o cache se perdia"
    )


@pytest.fixture()
def agent(monkeypatch: pytest.MonkeyPatch) -> ScriptedAgent:
    guide = ScriptedAgent([])

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Noemi voltou para Belem com Rute")

    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    the_turn_is_scripted(monkeypatch, heard=heard, model=guide)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    return guide


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, agent, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


async def test_the_stored_conversation_of_a_session_holds_no_room_fact_text(
    client, db_session, per_request, agent
) -> None:
    team, tablet = await a_claimed_device(db_session)
    first = await ready_session(db_session, pericope="P01", project_id=team.id)
    released = await client.post(team_release(first.id), headers=team_headers(tablet))
    assert released.status_code == 200, released.text[:300]
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"language": "pt", "pericope": "P02"},
    )
    session_id = opened.json()["session_id"]

    await the_room_opens(client, tablet, session_id)
    await the_team_says(client, tablet, session_id, "turno-1")

    assert all("EARLIER PASSAGES FOR THIS TEAM" in system for system in agent.guide_systems)
    assert all("MOMENT: " in system for system in agent.guide_systems)
    async with per_request() as fresh:
        stored = (await get_session(fresh, session_id)).messages
    assert len(stored) >= 3
    for marker in LEDGER_MARKERS:
        assert not any(marker in str(entry) for entry in stored), (
            f"o texto {marker!r}, que o Guia lê a cada turno, ficou guardado na conversa"
        )
