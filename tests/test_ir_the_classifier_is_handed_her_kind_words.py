"""The kind word each bead carries in the classifier's material is the one her coverage.ts writes.

Her `buildCoverageElements` (`src/ingest/coverage.ts:74`, `:90`) spells a scene's silence
`significant_absence` and a rule to keep `preserved_element`; her classifier prompt shows the
first in its own example (`prompts/classifier_system_prompt.md:156`). The expected kinds here
come from her code run by node, never from a table of ours.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.classify_coverage import classify_coverage
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.llm import CACHE_BREAK
from tests.her_spine_harness import her_spine
from tests.turn_harness import the_room_agent_is

P = "P01"
CLASSIFIER = default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"]
HER_TWO_WORDS = {"significant_absence", "preserved_element"}


@pytest.fixture
def the_systems_the_classifier_was_handed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    systems: list[str] = []

    async def agent(*, system_prompt: str, **kwargs: Any) -> str:
        systems.append(system_prompt)
        return json.dumps({"decisions": []})

    the_room_agent_is(monkeypatch, classifier=agent)
    return systems


async def _kinds_sent_for(systems: list[str]) -> dict[str, str]:
    await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="a famine came and the family left Bethlehem",
        guide_response="and then Elimelech died there",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )
    heading = "## The coverage elements (current unresolved set)"
    blocks = [
        system.split(heading, 1)[1].split("## This turn's exchange", 1)[0] for system in systems
    ]
    return {
        entry["id"]: entry["kind"]
        for block in blocks
        for entry in json.loads(block.replace(CACHE_BREAK, ""))
    }


async def test_a_silence_and_a_rule_to_keep_reach_the_classifier_under_her_two_words(
    the_systems_the_classifier_was_handed: list[str],
) -> None:
    hers = dict(her_spine([P])[P])
    sent = await _kinds_sent_for(the_systems_the_classifier_was_handed)

    her_two = {key: kind for key, kind in hers.items() if kind in HER_TWO_WORDS}

    assert set(her_two.values()) == HER_TWO_WORDS
    assert {key: sent[key] for key in her_two} == her_two, (
        "the classifier was shown `absence` and `preserved`, words her prompt never names, "
        "beside the `significant_absence` its own example uses"
    )


async def test_every_other_kind_reaches_the_classifier_as_she_spells_it_and_as_we_did(
    the_systems_the_classifier_was_handed: list[str],
) -> None:
    hers = dict(her_spine([P])[P])
    sent = await _kinds_sent_for(the_systems_the_classifier_was_handed)

    her_other = {key: kind for key, kind in hers.items() if kind not in HER_TWO_WORDS}

    assert set(her_other.values()) == {
        "arc",
        "context",
        "tone",
        "function",
        "scene",
        "being",
        "place",
        "object",
        "time",
    }
    assert {key: sent[key] for key in her_other} == her_other, (
        "a kind she spells the way we do was renamed on its way to the classifier"
    )
