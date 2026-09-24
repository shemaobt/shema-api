"""The Validator the room sends is her body, filled with exactly the slots her code fills.

Her `buildValidatorSystem` (`src/turn/prompts.ts:83-108` at a3f3c69) fills four slots and puts
the cache break before `{{TEAM_EVIDENCE}}`; the evidence is her heading and one sentence over
this turn's team-side text, or nothing when the turn has none. The strings below are typed
from her file, never read off ours.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRPromptKey, IRSession, IRSessionStatus
from app.services.internalization_room import prepare_opening as prepare_opening_module
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.llm import CACHE_BREAK
from app.services.internalization_room.panorama_turn import run_panorama_turn
from app.services.internalization_room.passage_turn import run_turn
from app.services.internalization_room.prompt_blocks import validator_map_block
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.turn_instructions import OPENING_INSTRUCTION
from app.services.internalization_room.verdict_turn import run_verdict_turn
from scripts.sync_doctrine import REPO_ROOT
from tests.text_seam_harness import RUNNER_KEY, the_app
from tests.turn_harness import GUIDE, SPEAKER, settings

PROMPTS = REPO_ROOT / "app/services/internalization_room/prompts"
SEAM = "/api/internalization-room/text-seam"
P = "P01"

TEAM_JUST_SAID = (
    "## WHAT THE TEAM JUST SAID (evidence — NEVER truth about the passage)\n\n"
    "The drafted response answers this. Referring to these words is not a claim about the "
    "passage.\n\n"
)
TEAM_REPORTED = (
    "\n\n---\n\n# WHAT THE TEAM REPORTED (their back-translation of their own recording)\n"
    "Evidence of what the team told back — NEVER truth about the passage. The drafted response "
    "may quote from it to name something reported that the passage does not tell; quoting this "
    "material is not a claim about the passage and must not be treated as ungrounded.\n\n"
)
DRAFT = "Vocês disseram que a Rute casou com o Malom. Isso a história não conta."
PORTUGUESE = "Brazilian Portuguese"
NOTE_PT_40 = "[A equipe falou na língua materna por cerca de 40 segundos; sem transcrição]"


def _her_body() -> str:
    lines = (PROMPTS / "vendor/validator_system_prompt.md").read_text(encoding="utf-8").splitlines()
    begin = lines.index("`=== BEGIN SYSTEM PROMPT ===`")
    end = lines.index("`=== END SYSTEM PROMPT ===`")
    return "\n".join(lines[begin + 1 : end]).strip()


def _as_she_builds_it(meaning_map: str, evidence: str, language: str = PORTUGUESE) -> str:
    return (
        _her_body()
        .replace("{{MEANING_MAP}}", meaning_map)
        .replace("{{TEAM_EVIDENCE}}", evidence)
        .replace("{{DRAFTED_RESPONSE}}", DRAFT)
        .replace("{{SESSION_LANGUAGE}}", language)
    )


class _Validators:
    """The Guide says DRAFT; every Validator prompt is kept, and passes."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            self.seen.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        return DRAFT


@pytest.fixture
def validators(monkeypatch: pytest.MonkeyPatch) -> _Validators:
    recorded = _Validators()
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", recorded
    )
    return recorded


@pytest.fixture
async def seam(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    transport = ASGITransport(app=the_app(db_session))
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Access-Code": RUNNER_KEY}
    ) as client:
        yield client


async def _opened(client: httpx.AsyncClient) -> str:
    created = await client.post(f"{SEAM}/session", json={"pericopeId": P, "language": PORTUGUESE})
    session_id = created.json()["sessionId"]
    await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "kickoff": True})
    return session_id


def _sent_as_hers(sent: str, expected: str, evidence: str) -> None:
    assert sent.count(CACHE_BREAK) == 1, "a quebra de cache não estava lá, ou estava duas vezes"
    assert sent.split(CACHE_BREAK)[1].startswith(
        f"{evidence}\n\n## The drafted response to validate"
    ), "a quebra de cache não ficava logo antes da evidência da equipe, como no dela"
    assert sent.replace(CACHE_BREAK, "") == expected, (
        "o Validador recebia outra coisa que não o corpo dela com os quatro slots dela"
    )


def test_the_validator_the_room_loads_is_her_body_and_no_copy_of_ours_is_left() -> None:
    assert get_prompt_text(IRPromptKey.VALIDATOR) == _her_body(), (
        "o Validador carregado era o nosso arquivo de agosto, e não o corpo dela"
    )
    assert not (PROMPTS / "validator_system_prompt.md").exists(), (
        "a cópia viva de agosto continuava ao lado da dela"
    )


async def test_a_spoken_turn_hands_her_validator_the_teams_words_as_her_evidence(
    seam: httpx.AsyncClient, validators: _Validators
) -> None:
    session_id = await _opened(seam)
    said = "A Rute casou com o Malom, né?"

    await seam.post(f"{SEAM}/turn", json={"sessionId": session_id, "text": said})

    evidence = TEAM_JUST_SAID + said
    _sent_as_hers(
        validators.seen[-1], _as_she_builds_it(validator_map_block(P, "Ruth"), evidence), evidence
    )


async def test_a_turn_in_the_mother_tongue_quotes_the_rooms_note_as_her_evidence(
    seam: httpx.AsyncClient, validators: _Validators
) -> None:
    session_id = await _opened(seam)

    await seam.post(
        f"{SEAM}/turn",
        json={"sessionId": session_id, "text": "koeti yoko vitukeovo", "motherTongue": 40},
    )

    evidence = TEAM_JUST_SAID + NOTE_PT_40
    _sent_as_hers(
        validators.seen[-1], _as_she_builds_it(validator_map_block(P, "Ruth"), evidence), evidence
    )


async def test_the_opening_quotes_the_rooms_opening_note_as_her_evidence(
    seam: httpx.AsyncClient, validators: _Validators
) -> None:
    await _opened(seam)

    evidence = TEAM_JUST_SAID + OPENING_INSTRUCTION
    _sent_as_hers(
        validators.seen[0], _as_she_builds_it(validator_map_block(P, "Ruth"), evidence), evidence
    )


async def test_the_opening_prepared_behind_the_panorama_is_judged_the_same_way(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, validators: _Validators
) -> None:
    db_session.add(
        IRSession(
            id="panorama-1",
            pericope="OV-Ruth",
            status=IRSessionStatus.IN_PROGRESS,
            messages=[],
            coverage_state={},
            kept_takes={},
            back_translation={},
            language="pt",
        )
    )
    await db_session.commit()

    async def voices(text: str, **_: Any):
        return (type("Voiced", (), {"key": "abertura-1"})(), False)

    monkeypatch.setattr(prepare_opening_module, "synthesize_facilitator_speech", voices)

    await prepare_opening_module.prepare_opening("panorama-1", pericope=P)

    evidence = TEAM_JUST_SAID + OPENING_INSTRUCTION
    _sent_as_hers(
        validators.seen[0], _as_she_builds_it(validator_map_block(P, "Ruth"), evidence), evidence
    )


@pytest.mark.parametrize(
    ("opening", "transcript", "team_side"),
    [
        (
            True,
            "",
            "[A sessão acabou de começar. A equipe abriu o Panorama do Livro de Ruth e está à "
            "mesa, pronta para conversar. Fale primeiro.]",
        ),
        (False, "o que é esse livro?", "o que é esse livro?"),
    ],
)
async def test_a_panorama_turn_is_judged_against_the_book_with_her_evidence(
    validators: _Validators, opening: bool, transcript: str, team_side: str
) -> None:
    material = build_book_material("Ruth")

    await run_panorama_turn(
        transcript=transcript,
        messages=[{"role": "guide", "text": "Vamos conhecer o livro."}],
        panorama_prompt=get_prompt_text(IRPromptKey.BOOK_PANORAMA),
        validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
        book="Ruth",
        book_material=material,
        session_language=PORTUGUESE,
        language_code="pt",
        opening=opening,
        settings=settings(),
    )

    evidence = TEAM_JUST_SAID + team_side
    _sent_as_hers(validators.seen[0], _as_she_builds_it(material, evidence), evidence)


async def test_the_verdict_is_judged_with_what_the_team_reported_under_her_heading(
    validators: _Validators,
) -> None:
    told = "1. Noemi mandou Rute voltar.\n2. Rute disse que ia junto."

    await run_verdict_turn(
        findings_text="(nenhum achado — a tradução está completa)",
        closing="\nPeça o próximo trecho.",
        scope=P,
        pericope_num=P,
        messages=[{"role": "guide", "text": "Contem de volta o que vocês gravaram."}],
        speaker_prompt=SPEAKER,
        validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
        telling_back=told,
        session_language=PORTUGUESE,
        language_code="pt",
        settings=settings(),
    )

    reported = validator_map_block(P, "Ruth") + TEAM_REPORTED + told
    _sent_as_hers(validators.seen[0], _as_she_builds_it(reported, ""), "")


@pytest.mark.parametrize(
    "slot",
    ["{{MEANING_MAP}}", "{{TEAM_EVIDENCE}}", "{{DRAFTED_RESPONSE}}", "{{SESSION_LANGUAGE}}"],
)
async def test_a_validator_without_one_of_her_slots_is_refused_before_a_team_hears_it(
    validators: _Validators, slot: str
) -> None:
    with pytest.raises(ValidationError, match=slot.strip("{}")):
        await run_turn(
            transcript="A Rute casou com o Malom, né?",
            coverage_state={},
            messages=[],
            guide_prompt=GUIDE,
            validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR).replace(slot, ""),
            pericope_num=P,
            session_language=PORTUGUESE,
            language_code="pt",
            settings=settings(),
        )

    assert validators.seen == [], "o Validador era chamado sem o slot que o render descarta"
