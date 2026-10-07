import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSession, IRSessionStatus
from app.services.internalization_room import prepare_opening as prepare_opening_module
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.run_turn import run_turn
from tests.release_harness import a_claimed_device
from tests.turn_harness import the_room_agent_is

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"

NOTICE = (
    "(This team has not worked this passage yet. If you speak of anything below, tell it as "
    "the story's — 'a história conta que…' (English sessions: 'the story tells that…') — only "
    "what is needed, in a few words; never 'lembrem', never 'na última parte'.)"
)

P01_HEADING = (
    "**Ruth 1:1\N{EN DASH}5** — The famine, the family's sojourn, and the emptying of the household"
)
P02_HEADING = (
    "**Ruth 1:6\N{EN DASH}14** — The return road begins; Naomi urges her daughters-in-law "
    "back; Orpah turns, Ruth clings"
)


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


class _Recording:
    def __init__(self) -> None:
        self.guide: list[str] = []
        self.validator: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide.append(system_prompt)
        return "Vamos ouvir a passagem."


@pytest.fixture
def recording(monkeypatch: pytest.MonkeyPatch) -> _Recording:
    models = _Recording()
    the_room_agent_is(monkeypatch, turn=models)
    return models


async def _turn(earlier_passages: dict[str, str]) -> None:
    await run_turn(
        transcript="",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        language_code="pt",
        opening=True,
        settings=_settings(),
        earlier_passages=earlier_passages,
    )


async def test_the_guide_reads_her_notice_under_the_passage_the_team_never_worked(
    recording: _Recording,
) -> None:
    await _turn({"P01": "approved", "P02": "not_worked"})

    guide = recording.guide[0]
    assert f"{P02_HEADING}\n{NOTICE}\n" in guide, (
        "a voz lia o resumo de uma passagem que a equipe nunca fez sem o aviso dela"
    )
    assert f"{P01_HEADING}\n{NOTICE}" not in guide and guide.count(NOTICE) == 1, (
        "uma passagem aprovada recebia o aviso de não trabalhada"
    )


async def test_the_validator_reads_the_same_notice_under_the_same_passage(
    recording: _Recording,
) -> None:
    await _turn({"P01": "approved", "P02": "not_worked"})

    judged = recording.validator[0]
    assert f"{P02_HEADING}\n{NOTICE}\n" in judged, (
        "o Validador julgava a fala sobre uma passagem não trabalhada sem o aviso que o Guia lia"
    )
    assert f"{P01_HEADING}\n{NOTICE}" not in judged and judged.count(NOTICE) == 1, (
        "uma passagem aprovada recebia o aviso de não trabalhada"
    )


async def test_once_the_team_has_worked_the_passage_its_notice_is_gone(
    recording: _Recording,
) -> None:
    await _turn({"P01": "approved", "P02": "started"})

    assert NOTICE not in recording.guide[0] and NOTICE not in recording.validator[0], (
        "uma passagem que a equipe já começou ainda era dada como não trabalhada"
    )


async def test_a_stamp_missing_an_earlier_passage_puts_no_notice_anywhere(
    recording: _Recording,
) -> None:
    await _turn({"P02": "not_worked"})

    assert NOTICE not in recording.guide[0] and NOTICE not in recording.validator[0], (
        "um carimbo incompleto marcava avisos que a linha das passagens anteriores calava"
    )


def _session(id: str, pericope: str, project_id: str, messages: list[dict[str, str]]) -> IRSession:
    return IRSession(
        id=id,
        pericope=pericope,
        project_id=project_id,
        status=IRSessionStatus.IN_PROGRESS,
        messages=messages,
        coverage_state={},
        kept_takes={},
        back_translation={},
        language="pt",
    )


async def test_an_opening_written_on_the_panorama_reads_her_notice_under_the_unworked_passage(
    db_session: AsyncSession, recording: _Recording, monkeypatch: pytest.MonkeyPatch
) -> None:
    team, _ = await a_claimed_device(db_session)
    db_session.add(_session("p01", "P01", team.id, [{"role": "team", "text": "a fome"}]))
    db_session.add(_session("panorama-1", "OV-Ruth", team.id, []))
    await db_session.commit()

    async def voices(text: str, **_: Any) -> tuple[Any, bool]:
        return (type("Voiced", (), {"key": "abertura-1"})(), False)

    monkeypatch.setattr(prepare_opening_module, "synthesize_facilitator_speech", voices)

    await prepare_opening_module.prepare_opening("panorama-1", pericope=P)

    assert f"{P02_HEADING}\n{NOTICE}\n" in recording.guide[0], (
        "a abertura escrita no panorama contava a passagem que a equipe nunca fez sem o aviso"
    )
