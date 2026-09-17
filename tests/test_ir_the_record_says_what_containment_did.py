"""What a session's own messages say about each turn the Guide took.

A guide message used to be a role and a text. Read back later, nothing in it said whether
the Validator passed the draft, mended it, or refused it and a fixed line spoke instead —
a facilitator export had to infer containment from a coverage projection. Her fail-safe
spec asks for more of every firing: the pericope, the scene, the team's words, the Guide's
draft, the Validator's verdict and issues, and which family answered.
"""

import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.sessions import append_exchange, create_session, get_session
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import KEY, PREFIX, P
from tests.room_harness import room_client

TEAM = "a fome chegou"
DRAFT = "Vamos ficar nesta cena. O que voces contariam?"


class _Model:
    """A Guide that drafts one line; the Validator answers from the script it was given."""

    def __init__(self, verdicts: list[str]) -> None:
        self.verdicts = verdicts
        self.judged = 0

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" not in system_prompt:
            return DRAFT
        self.judged += 1
        return self.verdicts[self.judged - 1]


async def _heard(*_: Any, **__: Any) -> HeardSpeech:
    return HeardSpeech(text=TEAM)


async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    entry = SynthesizedSpeech(
        audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/voice/t.mp3"
    )
    return entry, False


async def _noop_settle(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(db_session, monkeypatch):
    async with room_client(db_session, monkeypatch) as c:
        yield c


@pytest.fixture()
def the_room_hears(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sessions_api, "heard_speech", _heard)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", _noop_settle)

    def _install(verdicts: list[str]) -> None:
        turn_module = sys.modules["app.services.internalization_room.run_turn"]
        monkeypatch.setattr(turn_module, "call_agent", _Model(verdicts))

    return _install


async def _post_a_turn(client, session_id: str):
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )


async def test_a_passing_turn_is_recorded_as_a_pass_with_its_redrafts(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    outcome = TurnOutcome(speech="isso mesmo", transcript=TEAM, draft="isso mesmo", verdict="pass")

    session = await append_exchange(
        db_session, session, team_utterance=TEAM, guide_response="isso mesmo", outcome=outcome
    )

    assert session.messages[-1] == {
        "role": "guide",
        "text": "isso mesmo",
        "outcome": "pass",
        "redrafts": 0,
    }


async def test_a_mended_turn_is_recorded_as_corrected(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)
    outcome = TurnOutcome(
        speech="isso mesmo",
        transcript=TEAM,
        redrafts=1,
        issues=[{"problem": "imported_knowledge"}],
        draft="isso mesmo, e Rute casou com Malom",
        verdict="correct",
    )

    session = await append_exchange(
        db_session, session, team_utterance=TEAM, guide_response="isso mesmo", outcome=outcome
    )

    assert session.messages[-1] == {
        "role": "guide",
        "text": "isso mesmo",
        "outcome": "corrected",
        "redrafts": 1,
    }


async def test_a_fail_safe_is_recorded_with_everything_her_spec_asks_for(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    outcome = TurnOutcome(
        speech="Vamos com calma.",
        transcript=TEAM,
        used_fail_safe=True,
        degraded=True,
        redrafts=2,
        issues=[{"problem": "imported_knowledge", "claim": "Rute casou com Malom"}],
        fixed_line="A1",
        draft="Rute casou com Malom",
        verdict="regenerate",
    )

    session = await append_exchange(
        db_session,
        session,
        team_utterance=TEAM,
        guide_response="Vamos com calma.",
        outcome=outcome,
        scene="S1",
    )

    assert session.messages[-1] == {
        "role": "guide",
        "text": "Vamos com calma.",
        "outcome": "fail_safe",
        "redrafts": 2,
        "category": "A",
        "fixed_line": "A1",
        "pericope": P,
        "scene": "S1",
        "team_utterance": TEAM,
        "draft": "Rute casou com Malom",
        "verdict": "regenerate",
        "issues": [{"problem": "imported_knowledge", "claim": "Rute casou com Malom"}],
    }


async def test_a_firing_in_the_telling_back_round_keeps_what_was_told_back(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    outcome = TurnOutcome(
        speech="Vamos com calma.",
        transcript="",
        used_fail_safe=True,
        degraded=True,
        redrafts=2,
        fixed_line="A0",
        draft="Rute casou com Malom",
        verdict="regenerate",
    )

    session = await append_exchange(
        db_session,
        session,
        team_utterance="",
        guide_response="Vamos com calma.",
        outcome=outcome,
        told_back="1. Noemi mandou Rute voltar.\n2. Rute disse que ia junto.",
    )

    assert [m["role"] for m in session.messages] == ["guide"]
    assert session.messages[-1]["team_utterance"] == (
        "1. Noemi mandou Rute voltar.\n2. Rute disse que ia junto."
    )
    assert session.messages[-1]["scene"] is None


async def test_a_turn_taken_through_the_route_leaves_its_outcome_in_the_record(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    the_room_hears([json.dumps({"verdict": "pass", "issues": []})])
    session = await create_session(db_session, language="pt", pericope=P)

    answered = await _post_a_turn(client, session.id)
    assert answered.status_code == 200, answered.text[:300]

    reread = await get_session(db_session, session.id)
    assert reread.messages[-1] == {
        "role": "guide",
        "text": DRAFT,
        "outcome": "pass",
        "redrafts": 0,
    }


async def test_a_fixed_line_spoken_through_the_route_is_recorded_with_its_scene(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    the_room_hears(["desculpe, não consigo", "desculpe, não consigo"])
    session = await create_session(db_session, language="pt", pericope=P)

    answered = await _post_a_turn(client, session.id)
    assert answered.status_code == 200, answered.text[:300]
    assert answered.json()["used_fail_safe"] is True

    recorded = (await get_session(db_session, session.id)).messages[-1]
    assert recorded["outcome"] == "fail_safe"
    assert recorded["category"] == "A"
    assert recorded["pericope"] == P
    assert recorded["scene"] == "S1"
    assert recorded["team_utterance"] == TEAM
    assert recorded["draft"] == DRAFT
    assert recorded["redrafts"] == 0
