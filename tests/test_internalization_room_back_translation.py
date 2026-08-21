import json
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Chunk,
    Finding,
    FindingKind,
    analyse_telling_back,
    findings_block,
    segments_block,
)
from app.services.internalization_room.run_turn import run_verdict_turn

ANALYST = default_prompt(IRPromptKey.BT_ANALYST)["prompt"]
SPEAKER = default_prompt(IRPromptKey.BT_VERDICT_SPEAKER)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


def _chunks() -> list[Chunk]:
    return [
        Chunk(index=1, text="Noemi mandou Rute voltar."),
        Chunk(index=2, text="Rute disse que ia junto."),
    ]


@pytest.fixture
def patch_analyst(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.back_translation"]

    def _install(reply: str):
        async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            agent.system = system_prompt
            return reply

        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


@pytest.fixture
def patch_speaker(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.run_turn"]

    def _install(draft: str):
        seen: list[str] = []

        async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            seen.append(system_prompt)
            if "corrected_response" in system_prompt:
                return json.dumps({"verdict": "pass", "issues": []})
            return draft

        agent.seen = seen  # type: ignore[attr-defined]
        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


def test_the_chunks_go_to_the_analyst_in_listening_order() -> None:
    block = segments_block(_chunks())

    assert block.splitlines()[0].startswith("1. Noemi")
    assert block.splitlines()[1].startswith("2. Rute")


def test_an_empty_telling_back_says_so_rather_than_looking_complete() -> None:
    assert "ainda não contou" in segments_block([])


@pytest.mark.asyncio
async def test_a_faithful_telling_back_produces_no_findings(patch_analyst) -> None:
    patch_analyst(json.dumps({"findings": []}))

    findings = await analyse_telling_back(
        chunks=_chunks(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert findings == []


@pytest.mark.asyncio
async def test_findings_are_parsed_with_their_kind(patch_analyst) -> None:
    patch_analyst(
        json.dumps(
            {
                "findings": [
                    {"kind": "missing", "note": "Orfa não apareceu."},
                    {"kind": "addition", "note": "Você falou de Belém."},
                ]
            }
        )
    )

    findings = await analyse_telling_back(
        chunks=_chunks(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert [f.kind for f in findings] == [FindingKind.MISSING, FindingKind.ADDITION]


@pytest.mark.asyncio
async def test_an_unparseable_analysis_raises_nothing_rather_than_inventing(
    patch_analyst,
) -> None:
    """Under-report by design: a broken analysis must not become a finding the team hears."""
    patch_analyst("desculpe, não consigo")

    findings = await analyse_telling_back(
        chunks=_chunks(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert findings == []


def test_only_one_finding_ever_reaches_the_speaker() -> None:
    state = BackTranslationState(
        findings=[
            Finding(kind=FindingKind.MISSING, note="primeiro"),
            Finding(kind=FindingKind.ADDITION, note="segundo"),
        ]
    )

    block = findings_block(state.current_finding)

    assert "primeiro" in block
    assert "segundo" not in block


def test_no_findings_reads_as_complete() -> None:
    assert "nenhum achado" in findings_block(None)


@pytest.mark.asyncio
async def test_the_verdict_is_validated_before_it_is_voiced(patch_speaker) -> None:
    agent = patch_speaker("No que você me contou, Orfa não apareceu.")

    outcome = await run_verdict_turn(
        findings_text=findings_block(Finding(kind=FindingKind.MISSING, note="Orfa")),
        scope=P,
        pericope_num=P,
        messages=[],
        speaker_prompt=SPEAKER,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert outcome.speech == "No que você me contou, Orfa não apareceu."
    assert outcome.used_fail_safe is False
    speaker_system, validator_system = agent.seen[0], agent.seen[1]
    assert "Orfa" in speaker_system
    assert "{{" not in speaker_system
    assert "{{" not in validator_system
