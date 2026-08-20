"""The comprehension-aware turn as a whole: probes persist only when voiced, practice is
spoken as fixed process speech, and mother-tongue speech meets the fixed boundary."""

import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.comprehension.practice import (
    MOTHER_TONGUE_PRACTICE_PROMPT,
)
from app.services.internalization_room.comprehension.probe import ProbePurpose
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.sessions import (
    append_exchange,
    comprehension_of,
    create_session,
    save_comprehension,
)

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


class ApprovingAgent:
    """A Guide that drafts something short and a Validator that passes it."""

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vamos começar pela primeira cena. O que vocês acham?"


@pytest.fixture
def approve_all(monkeypatch: pytest.MonkeyPatch) -> None:
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", ApprovingAgent())


class LongWindedAgent:
    """A Guide that opens at length — introduce, give the whole, invite — and is approved."""

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return (
            "Olá, eu sou o Facilitador Digital. Esta história começa nos dias em que os "
            "juízes julgavam, quando falta comida na terra e uma família sai de Belém "
            "para peregrinar em Moabe. Ali ela perde quase tudo ao longo de dez anos, e "
            "é desse começo que vamos falar. Como vocês contariam essa primeira parte?"
        )


@pytest.mark.asyncio
async def test_the_opening_may_give_the_whole_before_the_parts(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The oral pacing budget is for the back-and-forth, never for the opening.

    Enforcing 45 words on the turn that has to introduce the Guide, give the whole before
    the parts and invite meant every passage opening busted the budget, redrafted twice and
    fell back to a canned line — so the room never introduced itself and never walked the
    team into the scenes, and the team waited six model calls for it. The panorama opening
    was already exempt; the passage opening was not.
    """
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", LongWindedAgent())
    session = await create_session(db_session, pericope=P, bridge_mode="adaptive")

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(),
        opening=True,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert not turn.outcome.used_fail_safe
    assert turn.outcome.speech.startswith("Olá, eu sou o Facilitador Digital.")
    assert len(turn.outcome.speech.split()) > 45


@pytest.mark.asyncio
async def test_a_turn_after_the_opening_still_answers_to_the_budget(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", LongWindedAgent())
    session = await create_session(db_session, pericope=P, bridge_mode="adaptive")
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(transcript="a fome chegou", is_substantial=True),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.outcome.used_fail_safe
    assert turn.outcome.fixed_line


@pytest.mark.asyncio
async def test_the_opening_turn_belongs_to_the_guide(
    db_session: AsyncSession, approve_all: None
) -> None:
    """The session's first line opens the passage; it is never an app-owned prompt.

    The Terena field test heard 'ensaiem juntos esta cena' as the very first utterance of
    a passage nobody had opened yet — instant, unframed, and with no thinking. Frame
    first, elicit second: the opening always goes through the Guide.
    """
    session = await create_session(db_session, pericope=P, bridge_mode="guided_microchecks")

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(),
        opening=True,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.bridge_mode == "guided_microchecks"
    assert turn.outcome.speech == "Vamos começar pela primeira cena. O que vocês acham?"
    assert turn.outcome.speech != MOTHER_TONGUE_PRACTICE_PROMPT
    assert not turn.outcome.used_fail_safe
    assert turn.state.active_probe is None


@pytest.mark.asyncio
async def test_the_practice_invitation_is_fixed_speech_with_a_peer_cue(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(db_session, pericope=P, bridge_mode="guided_microchecks")
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )
    first_scene_element = next(e for e in elements_for(P) if e.scene == 1)
    session.coverage_state = {
        **(session.coverage_state or {}),
        first_scene_element.key: "surfaced",
    }
    await db_session.commit()

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="podemos começar"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.outcome.speech == MOTHER_TONGUE_PRACTICE_PROMPT
    assert turn.outcome.peer_cue
    assert not turn.outcome.used_fail_safe


@pytest.mark.asyncio
async def test_practice_is_not_invited_before_the_voice_opens_the_scene(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(db_session, pericope=P, bridge_mode="guided_microchecks")
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="podemos começar"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.outcome.speech != MOTHER_TONGUE_PRACTICE_PROMPT
    assert turn.state.active_probe is not None
    assert turn.state.active_probe.purpose is not ProbePurpose.MOTHER_TONGUE_PRACTICE


@pytest.mark.asyncio
async def test_pronto_after_the_practice_prompt_marks_the_scene(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(db_session, pericope=P, bridge_mode="guided_microchecks")
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response=MOTHER_TONGUE_PRACTICE_PROMPT
    )
    seeded = ComprehensionState.model_validate(
        {
            "active_probe": {
                "id": "practice-1",
                "checkpoint_ids": [],
                "method": "micro_tellback",
                "purpose": "mother_tongue_practice",
                "practice_scene_ids": ["S1"],
            }
        }
    )
    session = await save_comprehension(db_session, session, seeded)

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="pronto"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert "S1" in turn.state.practiced_scene_ids
    assert turn.state.active_probe is not None
    assert turn.state.active_probe.purpose is ProbePurpose.INITIAL_CHECK


@pytest.mark.asyncio
async def test_mother_tongue_speech_meets_the_fixed_boundary_and_keeps_the_probe(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(db_session, pericope=P, bridge_mode="guided_microchecks")
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="quem aparece nesta parte?"
    )
    from app.services.internalization_room.comprehension.checkpoints import checkpoints_for

    target = next(c for c in checkpoints_for(P) if c.critical)
    seeded = ComprehensionState.model_validate(
        {
            "active_probe": {
                "id": "semantic-1",
                "checkpoint_ids": [target.id],
                "method": "micro_tellback",
                "purpose": "initial_check",
                "practice_scene_ids": [],
            }
        }
    )
    session = await save_comprehension(db_session, session, seeded)

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(
            text="koeti yoko vitukeovo enepone itukovo",
            language_code="und",
            language_probability=0.99,
        ),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.outcome.used_fail_safe
    assert turn.outcome.fixed_line.startswith("G")
    assert turn.state.active_probe is not None
    assert turn.state.active_probe.id == "semantic-1"
    assert all(event.kind != "evidence" for event in turn.state.ledger)


@pytest.mark.asyncio
async def test_a_turn_without_a_prior_probe_mints_no_evidence(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(db_session, pericope=P, bridge_mode="full_retell")
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="Noemi voltou para Belém com Rute"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.state.ledger == []
    assert comprehension_of(session).ledger == []
