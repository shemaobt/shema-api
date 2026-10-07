from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.internalization_room.run_turn import run_turn
from tests.turn_harness import GUIDE, VALIDATOR, settings, the_room_agent_is

NAOMI_DEFINED = "[[B3]] — נָעֳמִי / Naomi"
LAND_DEFINED = "[[PL_LAND_OF_JUDAH]] — הָאָרֶץ / the land"
R6_LINE = (
    "- R6 (STRUCTURAL_ABSENCE_OF_DIVINE_AGENCY): YHWH is not named as agent of any event in "
    "P01. The withholding is structural and intentional; it contrasts with the first divine "
    "action at 1:6 in P02. Reconstructor must not assign divine causation."
)


class FakeAgent:
    def __init__(self) -> None:
        self.systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        self.systems.append(system_prompt)
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vamos ouvir a passagem."


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch) -> FakeAgent:
    fake = FakeAgent()
    the_room_agent_is(monkeypatch, turn=fake)
    return fake


async def _guide_and_validator(agent: FakeAgent, pericope_num: str) -> tuple[str, str]:
    await run_turn(
        transcript="",
        coverage_state={},
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=pericope_num,
        book="Ruth",
        opening=True,
        settings=settings(),
    )
    return agent.systems[0], agent.systems[1]


async def test_a_link_the_map_writes_with_a_name_reaches_both_roles_as_its_code_alone(
    agent: FakeAgent,
) -> None:
    guide, validator = await _guide_and_validator(agent, "P01")

    assert "[[B3-Naomi]]" not in guide
    assert "[[B3-Naomi]]" not in validator
    assert NAOMI_DEFINED in guide
    assert NAOMI_DEFINED in validator


async def test_a_link_the_map_already_writes_as_a_code_alone_reaches_both_roles_as_it_is(
    agent: FakeAgent,
) -> None:
    guide, validator = await _guide_and_validator(agent, "P01")

    assert LAND_DEFINED in guide
    assert LAND_DEFINED in validator


async def test_each_rule_reaches_the_validator_as_her_line_with_no_passage_tag_in_front(
    agent: FakeAgent,
) -> None:
    _, validator = await _guide_and_validator(agent, "P01")

    assert R6_LINE in validator
    assert "[P01]" not in validator
