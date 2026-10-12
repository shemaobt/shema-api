"""ENG-1360 — the team's statuses are read within her budgets; a slow read errs toward unworked.

Her app gives the read 3 s when a session is created (`EARLIER_READ_BUDGET_MS`,
`src/turn/earlierPassagesRead.ts:55`) and 1.5 s before a turn whose session has no stamp
(`TURN_EARLIER_BUDGET_MS`, `app/api/turn/route.ts:33`). A passage not read in time reads
«not worked yet», so the stamp stays complete and the voice tells that passage as the story's.
The budget is passed on the loop's clock, never on the wall's.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSession, IRSessionStatus
from app.services.internalization_room import earlier_passages as statuses
from app.services.internalization_room import prepare_opening as prepare_opening_module
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.run_turn import run_turn
from app.services.internalization_room.sessions import get_session
from tests.hearing_harness import the_loop_clock_passes
from tests.release_harness import (
    PREFIX,
    a_claimed_device,
    ready_session,
    team_headers,
    team_release,
)
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.tablet_turn_harness import the_room_opens, the_turn_is_scripted
from tests.text_seam_harness import ScriptedAgent
from tests.turn_harness import the_room_agent_is

EARLIER = "EARLIER PASSAGES FOR THIS TEAM:"
ALL_THREE_NOT_WORKED = (
    "EARLIER PASSAGES FOR THIS TEAM: Not worked yet: Ruth 1:1\N{EN DASH}5, "
    "Ruth 1:6\N{EN DASH}14, Ruth 1:15\N{EN DASH}18."
)
ALL_THREE_UNREAD = {
    "P01": "not_worked",
    "P02": "not_worked",
    "P03": "not_worked",
    "unread": "P01, P02, P03",
}
P01_UNDER_HER_NOTICE = (
    "**Ruth 1:1\N{EN DASH}5** — The famine, the family's sojourn, and the emptying of the "
    "household\n"
    "(This team has not worked this passage yet. If you speak of anything below, tell it as "
    "the story's — 'a história conta que…' (English sessions: 'the story tells that…') — only "
    "what is needed, in a few words; never 'lembrem', never 'na última parte'.)"
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


async def opened(client: httpx.AsyncClient, tablet: str, pericope: str) -> dict[str, Any]:
    answered = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"language": "pt", "pericope": pericope},
    )
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()


async def stored_stamp(per_request: async_sessionmaker[AsyncSession], session_id: str):
    async with per_request() as fresh:
        stamp = (await get_session(fresh, session_id)).earlier_passages
    return None if stamp is None else {key: value for key, value in stamp.items() if key != "at"}


async def p01_approved(client: httpx.AsyncClient, db: AsyncSession, team: Any, tablet: str) -> None:
    p01 = await ready_session(db, pericope="P01", project_id=team.id)
    approval = await client.post(team_release(p01.id), headers=team_headers(tablet))
    assert approval.status_code == 200, approval.text[:300]


async def minted_before_the_stamp(
    client: httpx.AsyncClient, per_request: async_sessionmaker[AsyncSession], tablet: str
) -> str:
    session_id = (await opened(client, tablet, "P04"))["session_id"]
    async with per_request() as fresh:
        await fresh.execute(
            update(IRSession).where(IRSession.id == session_id).values(earlier_passages=None)
        )
        await fresh.commit()
    return session_id


def earlier_line(system_prompt: str) -> str | None:
    lines = [line for line in system_prompt.splitlines() if line.startswith(EARLIER)]
    return lines[0] if lines else None


async def the_stamp_is_left_alone(**_: Any) -> None:
    return None


def the_statuses_never_answer(monkeypatch: pytest.MonkeyPatch) -> asyncio.Event:
    started = asyncio.Event()

    async def never(*_: Any, **__: Any) -> dict[str, str]:
        started.set()
        await asyncio.Event().wait()
        return {}

    monkeypatch.setattr(statuses, "read_statuses", never)
    return started


async def the_read_begins(started: asyncio.Event, request: asyncio.Task[Any]) -> None:
    reading = asyncio.ensure_future(started.wait())
    await asyncio.wait({reading, request}, return_when=asyncio.FIRST_COMPLETED)
    reading.cancel()
    assert not request.done(), f"the request ended before the read began: {request.result()!r}"


async def answered_once_the_clock_passes(
    monkeypatch: pytest.MonkeyPatch, request: asyncio.Task[Any], seconds: float, reason: str
) -> Any:
    the_loop_clock_passes(monkeypatch, seconds)
    try:
        done, _ = await asyncio.wait({request}, timeout=5)
        assert done, reason
    finally:
        request.cancel()
        await asyncio.wait({request})
    return request.result()


def test_her_budgets_are_three_seconds_at_the_open_and_one_and_a_half_before_a_turn() -> None:
    assert (statuses.OPEN_READ_BOUND_S, statuses.TURN_READ_BOUND_S) == (3.0, 1.5)


async def test_an_open_whose_statuses_miss_three_seconds_stamps_each_not_worked_and_unread(
    client, db_session, per_request, monkeypatch
) -> None:
    team, tablet = await a_claimed_device(db_session)
    await p01_approved(client, db_session, team, tablet)
    started = the_statuses_never_answer(monkeypatch)
    opening = asyncio.create_task(opened(client, tablet, "P04"))

    await the_read_begins(started, opening)
    session = await answered_once_the_clock_passes(
        monkeypatch,
        opening,
        statuses.OPEN_READ_BOUND_S + 0.5,
        "uma leitura dos estados que não respondia segurava a abertura da passagem sem fim",
    )

    assert await stored_stamp(per_request, session["session_id"]) == ALL_THREE_UNREAD, (
        "o carimbo de uma leitura que estourou o prazo não dizia quais passagens não foram lidas"
    )


async def test_an_opening_prepared_on_the_panorama_reads_each_not_worked_yet_past_three_seconds(
    db_session, agent, monkeypatch
) -> None:
    team, _ = await a_claimed_device(db_session)
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

    async def voices(text: str, **_: Any) -> tuple[Any, bool]:
        return (type("Voiced", (), {"key": "abertura-1"})(), False)

    monkeypatch.setattr(prepare_opening_module, "synthesize_facilitator_speech", voices)
    started = the_statuses_never_answer(monkeypatch)
    preparing = asyncio.create_task(prepare_opening_module.prepare_opening("panorama-1", "P04"))

    await the_read_begins(started, preparing)
    await answered_once_the_clock_passes(
        monkeypatch,
        preparing,
        statuses.OPEN_READ_BOUND_S + 0.5,
        "uma leitura dos estados que não respondia segurava a abertura preparada no panorama",
    )

    assert earlier_line(agent.guide_systems[0]) == ALL_THREE_NOT_WORKED


async def test_a_turn_whose_session_has_no_stamp_goes_on_past_its_budget_telling_each_as_the_storys(
    client, db_session, per_request, agent, monkeypatch
) -> None:
    monkeypatch.setattr(statuses, "OPEN_READ_BOUND_S", 100.0)
    monkeypatch.setattr(statuses, "TURN_READ_BOUND_S", 50.0)
    monkeypatch.setattr(sessions_api, "read_the_earlier_passages_again", the_stamp_is_left_alone)
    team, tablet = await a_claimed_device(db_session)
    await p01_approved(client, db_session, team, tablet)
    session_id = await minted_before_the_stamp(client, per_request, tablet)
    started = the_statuses_never_answer(monkeypatch)

    speaking = asyncio.create_task(the_room_opens(client, tablet, session_id))
    await the_read_begins(started, speaking)
    await answered_once_the_clock_passes(
        monkeypatch,
        speaking,
        statuses.TURN_READ_BOUND_S + 0.5,
        "uma leitura dos estados que não respondia segurava o turno além do seu prazo",
    )

    assert earlier_line(agent.guide_systems[-1]) == ALL_THREE_NOT_WORKED, (
        "um turno cuja leitura não respondia ficava sem a linha das passagens anteriores"
    )
    assert P01_UNDER_HER_NOTICE in agent.guide_systems[-1], (
        "a passagem que não se pôde ler chegava à voz sem o aviso dela"
    )


async def test_a_turn_whose_session_has_no_stamp_tells_the_guide_what_it_read_and_keeps_it(
    client, db_session, per_request, agent, monkeypatch
) -> None:
    team, tablet = await a_claimed_device(db_session)
    await p01_approved(client, db_session, team, tablet)
    session_id = await minted_before_the_stamp(client, per_request, tablet)

    await the_room_opens(client, tablet, session_id)

    assert earlier_line(agent.guide_systems[-1]) == (
        "EARLIER PASSAGES FOR THIS TEAM: Approved: Ruth 1:1\N{EN DASH}5. "
        "Not worked yet: Ruth 1:6\N{EN DASH}14, Ruth 1:15\N{EN DASH}18."
    ), "um turno sem carimbo nunca lia os estados, e a voz não sabia o que a equipe fez"
    assert await stored_stamp(per_request, session_id) == {
        "P01": "approved",
        "P02": "not_worked",
        "P03": "not_worked",
    }, "o carimbo lido antes do turno se perdia e cada turno lia de novo"


async def test_a_stamp_naming_its_unread_passages_gives_the_validator_the_line_and_her_notices(
    monkeypatch,
) -> None:
    validator: list[str] = []

    async def answers(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            validator.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vamos ouvir a passagem."

    the_room_agent_is(monkeypatch, turn=answers)

    await run_turn(
        transcript="",
        coverage_state=initial_state("P04"),
        messages=[],
        guide_prompt=default_prompt(IRPromptKey.GUIDE)["prompt"],
        validator_prompt=default_prompt(IRPromptKey.VALIDATOR)["prompt"],
        pericope_num="P04",
        language_code="pt",
        opening=True,
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
        earlier_passages=ALL_THREE_UNREAD,
    )

    assert earlier_line(validator[0]) == ALL_THREE_NOT_WORKED, (
        "um carimbo com as passagens não lidas tirava do Validador a linha das passagens anteriores"
    )
    assert P01_UNDER_HER_NOTICE in validator[0], (
        "um carimbo com as passagens não lidas tirava do Validador o aviso dela"
    )
