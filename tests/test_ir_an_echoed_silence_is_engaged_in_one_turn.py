"""The other half of the reversal: the echo of an absence is the engagement.

Marcia's classifier says it in one line — *the Guide raising "notice the story never says
God did this" = surfaced; the team responding to or echoing that noticing = engaged*. Ours
had it inverted, so the five silences of Ruth 1 were beads a team could only fill by
noticing the silence before the Guide did. What is pinned here is the plumbing under her
rule: a verdict of `engaged` on an absence the Guide raised last turn lands the bead on
`engaged` in that one settle, with nothing between.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import ElementKind, elements_for
from app.services.internalization_room.classify_coverage import classify_coverage
from app.services.internalization_room.coverage import (
    CoverageStatus,
    initial_state,
    merge,
)

P = "P01"


@pytest.fixture
def the_classifier_answers(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.classify_coverage"]

    def _install(reply: str) -> None:
        async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            return reply

        monkeypatch.setattr(module, "call_agent", agent)

    return _install


async def test_a_team_that_takes_up_the_guides_noticing_of_a_silence_engages_it(
    the_classifier_answers,
) -> None:
    silence = next(e for e in elements_for(P) if e.kind is ElementKind.ABSENCE)
    raised_last_turn = merge(initial_state(P), pericope_num=P, surfaced=[silence.key])
    the_classifier_answers(
        json.dumps(
            {
                "decisions": [
                    {
                        "element_id": silence.key,
                        "new_status": "engaged",
                        "evidence": "é, não diz que foi Deus",
                    }
                ]
            }
        )
    )

    settled = await classify_coverage(
        coverage_state=raised_last_turn,
        team_utterance="é verdade, a história não diz que foi Deus que mandou a fome",
        guide_response="isso mesmo — a história não conta por quê",
        classifier_prompt=default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"],
        pericope_num=P,
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )

    assert settled[silence.key] == CoverageStatus.ENGAGED.value, (
        "o eco do silêncio parava em partially_engaged e a conta da ausência nunca enchia"
    )
