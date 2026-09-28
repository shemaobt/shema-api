"""The coverage classifier is the first key that reads her prompt, not a hand-kept copy of it.

The live file equalled her body plus one trailing newline, and nothing held it there: the next
sync would have moved her file and left ours behind. A key in `prompt_adaptations.HER_FILES`
reads the vendored file through her loader's extraction, with the table's rows for it and
nothing else; the classifier has none.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room import _default_prompts
from app.services.internalization_room.classify_coverage import (
    _scenes_block,
    _unresolved_block,
    classify_coverage,
)
from app.services.internalization_room.coverage import initial_state, remaining
from app.services.internalization_room.llm import CACHE_BREAK
from app.services.internalization_room.prompt_adaptations import (
    ADAPTATIONS,
    HER_FILES,
    Adaptation,
)
from app.services.internalization_room.prompts import get_prompt_text
from scripts.sync_doctrine import REPO_ROOT
from tests.turn_harness import the_room_agent_is

PROMPTS = REPO_ROOT / "app/services/internalization_room/prompts"


def _her_body(name: str) -> str:
    lines = (PROMPTS / "vendor" / name).read_text(encoding="utf-8").splitlines()
    begin = lines.index("`=== BEGIN SYSTEM PROMPT ===`")
    end = lines.index("`=== END SYSTEM PROMPT ===`")
    return "\n".join(lines[begin + 1 : end]).strip()


async def test_the_room_sends_the_classifier_exactly_her_body_with_its_slots_filled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: dict[str, Any] = {}

    async def agent(*, system_prompt: str, **kwargs: Any) -> str:
        sent["system"] = system_prompt
        return '{"decisions": []}'

    the_room_agent_is(monkeypatch, classifier=agent)
    state = initial_state("P01")

    await classify_coverage(
        coverage_state=state,
        team_utterance="A Noemi voltou para Belém.",
        guide_response="Isso mesmo. O que mais chamou a atenção de vocês?",
        classifier_prompt=get_prompt_text(IRPromptKey.COVERAGE_CLASSIFIER),
        pericope_num="P01",
        session_language="Brazilian Portuguese",
    )

    expected = (
        _her_body("classifier_system_prompt.md")
        .replace("{{SESSION_LANGUAGE}}", "Brazilian Portuguese")
        .replace("{{SCENES}}", _scenes_block("P01"))
        .replace("{{COVERAGE_ELEMENTS}}", _unresolved_block(state, remaining(state, "P01")))
        .replace("{{TEAM_UTTERANCE}}", "A Noemi voltou para Belém.")
        .replace("{{GUIDE_RESPONSE}}", "Isso mesmo. O que mais chamou a atenção de vocês?")
    )
    assert sent["system"].count(CACHE_BREAK) == 1, "a quebra de cache antes dos elementos sumiu"
    assert sent["system"].replace(CACHE_BREAK, "") == expected, (
        "o classificador lia uma cópia nossa, e não o corpo dela vendorizado"
    )


def test_every_key_that_reads_her_body_loads_it_with_exactly_its_rows_and_nothing_else() -> None:
    assert HER_FILES.get(IRPromptKey.COVERAGE_CLASSIFIER) == "classifier_system_prompt.md"
    for key, name in HER_FILES.items():
        expected = _her_body(name)
        for row in ADAPTATIONS:
            if row.key == key:
                expected = expected.replace(row.hers, row.ours, 1)

        assert get_prompt_text(IRPromptKey(key)) == expected, f"{key} is not her body"


def test_no_key_that_reads_her_body_keeps_a_copy_among_the_live_prompts() -> None:
    kept = [name for name in HER_FILES.values() if (PROMPTS / name).exists()]

    assert not kept, f"a hand-kept copy survives beside the vendored one: {kept}"


def test_a_row_that_no_longer_applies_breaks_its_own_key_when_asked_and_no_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    moved = (Adaptation(IRPromptKey.COVERAGE_CLASSIFIER, "a sentence she rewrote", "", "r4:76"),)
    monkeypatch.setattr(_default_prompts, "ADAPTATIONS", moved)
    _default_prompts.load_prompt.cache_clear()
    try:
        assert get_prompt_text(IRPromptKey.GUIDE), "uma linha do classificador derrubava o Guia"
        with pytest.raises(ValueError, match="coverage_classifier: her text occurs 0 times"):
            get_prompt_text(IRPromptKey.COVERAGE_CLASSIFIER)
    finally:
        _default_prompts.load_prompt.cache_clear()
