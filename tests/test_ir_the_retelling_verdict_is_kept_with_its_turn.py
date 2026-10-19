"""ENG-1378 (b) — the retelling verdict the coverage reader returns is kept with its turn.

Her classifier answers a retelling verdict beside its decisions (her classifier.ts:16-20,
46-52); ours asked for it in her prompt and then forbade it in the answer's schema, so
the verdict never came back and no take could ever be kept.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.classify_coverage import classify_coverage
from app.services.internalization_room.coverage import initial_state
from tests.turn_harness import the_room_agent_is

P = "P01"
CLASSIFIER = default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"]
TOLD = "Elimelech foi com Noemi e os dois filhos para Moabe por causa da fome."
AFFIRMED = "Isso. Vocês contaram a cena inteira."


async def test_the_answer_the_classifier_is_bound_to_admits_her_retelling_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schemas: list[dict[str, Any]] = []

    async def reader(*, schema: dict[str, Any], **_: Any) -> str:
        schemas.append(schema)
        return '{"decisions": []}'

    the_room_agent_is(monkeypatch, classifier=reader)

    await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance=TOLD,
        guide_response=AFFIRMED,
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
    )

    assert schemas[0]["required"] == ["decisions"]
    assert schemas[0]["properties"]["retelling"] == {
        "type": "object",
        "properties": {"scope": {"type": "string"}, "approved": {"type": "boolean"}},
        "required": ["scope", "approved"],
        "additionalProperties": False,
    }, (
        "o prompt dela pedia o veredito da recontagem e o esquema da resposta o proibia, "
        "então o veredito nunca voltava"
    )
