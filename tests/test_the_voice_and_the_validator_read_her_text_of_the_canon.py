from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.back_translation import (
    Finding,
    FindingKind,
    analyse_telling_back,
    verify_correction,
)
from app.services.internalization_room.canon import parse_map
from app.services.internalization_room.part_names import Addresses
from app.services.internalization_room.run_turn import run_turn, run_verdict_turn
from tests.turn_harness import (
    GUIDE,
    SPEAKER,
    VALIDATOR,
    settings,
    stretch,
    the_room_agent_is,
    told_stretches,
)

ANALYST = default_prompt(IRPromptKey.BT_ANALYST)["prompt"]
CORRECTION = default_prompt(IRPromptKey.BT_CORRECTION)["prompt"]

NAOMI_DEFINED = "[[B3]] — נָעֳמִי / Naomi"
LAND_DEFINED = "[[PL_LAND_OF_JUDAH]] — הָאָרֶץ / the land"
R6_LINE = (
    "- R6 (STRUCTURAL_ABSENCE_OF_DIVINE_AGENCY): YHWH is not named as agent of any event in "
    "P01. The withholding is structural and intentional; it contrasts with the first divine "
    "action at 1:6 in P02. Reconstructor must not assign divine causation."
)
SCENE_1_SILENCE = (
    "- S1 (1:1-2): Narrator never says YHWH sent the famine or drove the family out; the book "
    "opens with no word of God acting."
)
STORY_SO_FAR_OPENS = (
    "---\n\n# THE STORY SO FAR (earlier passages of this book — map-authored)\n"
    "Digests of this book's earlier passages, extracted verbatim from their own Meaning Maps. "
    "Grounded material: it may be used to answer the team's questions about the story so far "
    "and to situate the current passage in the book. Nothing beyond these passages and the "
    "current map exists.\n\n**Ruth 1:1"
)

NAOMI_IN_THE_DIGEST = "narrows down, loss by loss, to [[B3]] Naomi, alone in a foreign land"

P03_FIRST_RULE = "- R1 (VOW_AND_BINDING_BEYOND_DEATH): First oath-scene in the pilot."
P03_LAST_SILENCE = (
    "- S3 (1:18): Narrator tells us Naomi sees and stops speaking, but nothing of what is going "
    "on inside her. No agreement, no blessing, no further word from Naomi in this passage. We "
    "are let into Ruth's resolve, but not into how Naomi takes it."
)


def _reads_her_validator_material(system: str) -> None:
    assert NAOMI_DEFINED in system
    assert P03_FIRST_RULE in system
    assert P03_LAST_SILENCE in system
    assert STORY_SO_FAR_OPENS in system


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


async def test_the_first_scenes_silence_reaches_the_validator_as_her_coordinates_sentence(
    agent: FakeAgent,
) -> None:
    _, validator = await _guide_and_validator(agent, "P01")

    assert SCENE_1_SILENCE in validator
    assert "- S1 (v.1\u20132):" not in validator


async def test_the_story_so_far_opens_with_her_separator_and_header_and_never_names_the_passage(
    agent: FakeAgent,
) -> None:
    guide, validator = await _guide_and_validator(agent, "P03")

    assert STORY_SO_FAR_OPENS in guide
    assert STORY_SO_FAR_OPENS in validator


@pytest.fixture
def an_earlier_arc_with_a_slugged_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    maps = tmp_path / "meaning-map"
    maps.mkdir()
    for name in ("P01-Ruth-1-1-5.md", "P02-Ruth-1-6-14.md"):
        text = (parse_map.MAPS_DIR / name).read_text(encoding="utf-8")
        (maps / name).write_text(
            text.replace("to one grieving woman, alone", "to [[B3-Naomi]] Naomi, alone"),
            encoding="utf-8",
        )
    monkeypatch.setattr(parse_map, "MAPS_DIR", maps)
    parse_map.load_map.cache_clear()
    parse_map.load_book.cache_clear()
    yield "P02"
    parse_map.load_map.cache_clear()
    parse_map.load_book.cache_clear()


async def test_an_earlier_digest_with_a_slugged_link_reaches_both_roles_as_its_code_alone(
    agent: FakeAgent, an_earlier_arc_with_a_slugged_link: str
) -> None:
    guide, validator = await _guide_and_validator(agent, an_earlier_arc_with_a_slugged_link)

    assert NAOMI_IN_THE_DIGEST in guide
    assert NAOMI_IN_THE_DIGEST in validator


async def test_the_ensaio_final_analyst_reads_the_validators_whole_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    systems: list[str] = []

    async def analyst(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        systems.append(system_prompt)
        return json.dumps({"findings": []})

    the_room_agent_is(monkeypatch, analyst=analyst)

    await analyse_telling_back(
        segments=told_stretches(),
        scope="P03",
        pericope_num="P03",
        analyst_prompt=ANALYST,
        settings=settings(),
    )

    _reads_her_validator_material(systems[0])


async def test_the_correction_check_reads_the_validators_whole_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    systems: list[str] = []

    async def check(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        systems.append(system_prompt)
        return json.dumps({"resolved": True, "findings": []})

    the_room_agent_is(monkeypatch, analyst=check)

    await verify_correction(
        findings=[Finding(kind=FindingKind.MISSING, note="Noemi parou de falar")],
        earlier=stretch(1, "Rute disse que ia junto."),
        corrected=stretch(2, "Rute disse que ia junto, e Noemi parou de falar."),
        chunk=1,
        scope="P03",
        pericope_num="P03",
        correction_prompt=CORRECTION,
        addresses=Addresses(),
        settings=settings(),
    )

    _reads_her_validator_material(systems[0])


async def test_the_voiced_verdicts_speaker_reads_the_validators_whole_material(
    agent: FakeAgent,
) -> None:
    await run_verdict_turn(
        findings_text="No que vocês me contaram, Noemi não parou de falar.",
        scope="P03",
        pericope_num="P03",
        messages=[],
        speaker_prompt=SPEAKER,
        validator_prompt=VALIDATOR,
        book="Ruth",
        settings=settings(),
    )

    _reads_her_validator_material(agent.systems[0])
