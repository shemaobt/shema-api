import json
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.render import render
from app.services.internalization_room.run_turn import (
    MAX_REDRAFTS,
    OPENING_MOVEMENT_MARK,
    coverage_status_block,
    detects_peer_cue,
    run_turn,
    split_opening_movements,
)

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


class FakeAgent:
    """Stands in for the LLM: alternates Guide draft, Validator verdict, Guide draft…"""

    def __init__(self, verdicts: list[dict[str, Any]], drafts: list[str] | None = None):
        self.verdicts = verdicts
        self.drafts = drafts or [f"rascunho {i}" for i in range(len(verdicts) + 1)]
        self.calls: list[str] = []
        self.guide_inputs: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        is_validator = "corrected_response" in system_prompt
        self.calls.append("validator" if is_validator else "guide")
        if not is_validator:
            self.guide_inputs.append(user_content)
        if is_validator:
            return json.dumps(self.verdicts[len([c for c in self.calls if c == "validator"]) - 1])
        return self.drafts[len([c for c in self.calls if c == "guide"]) - 1]


@pytest.fixture
def patch_agent(monkeypatch: pytest.MonkeyPatch):
    """Swap `call_agent` for a fake inside the turn module.

    The package re-exports the `run_turn` function, which shadows the module of the same
    name, so the dotted-string form of setattr would patch the function object.
    """
    module = sys.modules["app.services.internalization_room.run_turn"]

    def _install(agent: FakeAgent) -> FakeAgent:
        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


def test_a_marked_opening_comes_back_as_two_movements() -> None:
    text, movements = split_opening_movements(
        "O todo da passagem.\n[[CENA]]\nA primeira cena, e o convite."
    )

    assert movements == ["O todo da passagem.", "A primeira cena, e o convite."]
    assert OPENING_MOVEMENT_MARK not in text
    assert text == "O todo da passagem.\n\nA primeira cena, e o convite."


@pytest.mark.parametrize(
    "draft",
    [
        "Uma abertura inteira sem marca nenhuma.",
        "O todo [[CENA]] e a cena na mesma linha.",
        "O todo.\n[[CENA]]\nA cena.\n[[CENA]]\nMais uma.",
        "\n[[CENA]]\nSó a cena, sem o todo.",
        "Só o todo, sem a cena.\n[[CENA]]\n",
    ],
)
def test_a_half_offered_structure_is_no_structure_at_all(draft: str) -> None:
    """Fail-closed: anything but the exact shape reads as an opening told in one breath.

    A structure read wrong would cut the opening in the wrong place, and the mark itself
    must never survive into the text — the synthesiser would say it out loud.
    """
    text, movements = split_opening_movements(draft)

    assert movements == []
    assert "[[" not in text
    assert OPENING_MOVEMENT_MARK not in text


def test_the_channel_policy_is_about_conflation_not_order() -> None:
    """The Validator invented a sequence rule and rejected the Guide in both directions.

    In one session it rejected the Guide for asking the telling-back before the rehearsal
    ("inverte o fluxo") and in the next for asking the rehearsal before the telling-back
    ("a politica exige primeiro o relato"). The second is the inverse of the order the
    Guide actually keeps, so both rejections spent the redrafts and dropped the room to a
    canned line. The policy now says what it is for, and says where the order really lives
    — the Guide's own instructions and the probe contract — so barring it from judging
    order never reads as licence to invite a rehearsal the contract has not authorised.
    """
    policy = VALIDATOR[VALIDATOR.index("Keep the two evidence channels separate") :]
    policy = policy[: policy.index("\n-")]

    assert "conflation, not sequence" in policy
    assert "evidence of the other" in policy
    assert "still governs" in policy


def test_inviting_the_rehearsal_is_not_claiming_to_have_understood_it() -> None:
    """Session 956987cb: the opening itself fell to a fail-safe, on the sentence that ends it.

    The Validator read "When you finish, tell me in English what you said." as an epistemic
    violation and quoted both policies at once — the Guide "must not imply it will understand
    or check the mother-tongue rehearsal itself; it must limit its judgment to the
    bridge-language telling-back". Neither policy carved anything out for a rehearsal in the
    future, and on an opening turn nothing else speaks for the invitation either: the probe is
    None there, so the practice contract that authorises it is never appended. So the one
    sentence the opening is required to end on had no defender in the room that judges it.

    A promise to hear a telling-back is not a claim about a rehearsal, and it cannot be one:
    neither has happened when the sentence is spoken.
    """
    access = VALIDATOR[VALIDATOR.index("Never claim access to mother-tongue meaning") :]
    access = access[: access.index("\n-")]
    judgment = VALIDATOR[VALIDATOR.index("Limit every judgment to the bridge-language") :]
    judgment = judgment[: judgment.index("\n-")]

    assert "An invitation is not a claim" in access
    assert "neither has happened yet" in access
    assert "An invitation makes no judgment" in judgment


def test_render_refuses_a_prompt_with_an_unfilled_placeholder() -> None:
    with pytest.raises(ValidationError) as excinfo:
        render("mapa: {{MEANING_MAP}} lingua: {{SESSION_LANGUAGE}}", SESSION_LANGUAGE="pt")

    assert "MEANING_MAP" in str(excinfo.value)


def test_render_fills_every_placeholder() -> None:
    out = render("{{A_B}} e {{C}}", A_B="um", C="dois")

    assert out == "um e dois"


def test_the_coverage_block_lists_only_what_is_left() -> None:
    state = merge(initial_state(P), pericope_num=P, engaged=["scene:1", "scene:2"])
    block = coverage_status_block(state, P)

    assert "[scene:3]" in block
    assert "[scene:1]" not in block


def test_a_finished_map_says_nothing_remains() -> None:
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    block = coverage_status_block(whole, P)

    assert "nada" in block


def test_peer_cue_is_read_off_the_reply() -> None:
    assert detects_peer_cue("Agora ensaiem essa parte entre vocês, na língua de vocês.")
    assert not detects_peer_cue("Me contem o que aconteceu com a família.")


@pytest.mark.asyncio
async def test_inaudible_audio_never_reaches_a_model(patch_agent) -> None:
    agent = patch_agent(FakeAgent(verdicts=[]))

    outcome = await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="   ",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=_settings(),
    )

    assert outcome.used_fail_safe is True
    assert outcome.degraded is True
    assert outcome.speech in utterances(FailSafe.INAUDIBLE, "pt")
    assert agent.calls == []


@pytest.mark.asyncio
async def test_a_passing_draft_is_what_the_team_hears(patch_agent) -> None:
    agent = patch_agent(
        FakeAgent(
            verdicts=[{"verdict": "pass", "issues": []}],
            drafts=["Ensaiem essa parte entre vocês."],
        )
    )

    outcome = await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="A fome chegou e eles partiram.",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=_settings(),
    )

    assert outcome.speech == "Ensaiem essa parte entre vocês."
    assert outcome.peer_cue is True
    assert outcome.redrafts == 0
    assert agent.calls == ["guide", "validator"]


@pytest.mark.asyncio
async def test_a_corrected_verdict_voices_the_repaired_text(patch_agent) -> None:
    patch_agent(
        FakeAgent(
            verdicts=[
                {
                    "verdict": "correct",
                    "issues": [{"problem": "invented_detail", "claim": "tinha dez filhos"}],
                    "corrected_response": "Vamos ficar com o que a passagem conta.",
                }
            ],
            drafts=["Eles tinha dez filhos."],
        )
    )

    outcome = await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="quantos filhos?",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=_settings(),
    )

    assert outcome.speech == "Vamos ficar com o que a passagem conta."
    assert outcome.used_fail_safe is False
    assert outcome.issues


@pytest.mark.asyncio
async def test_two_regenerations_then_the_fail_safe_line(patch_agent) -> None:
    agent = patch_agent(
        FakeAgent(
            verdicts=[
                {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]},
                {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]},
                {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]},
            ]
        )
    )

    outcome = await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="me conta mais sobre Rute",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=_settings(),
    )

    assert outcome.used_fail_safe is True
    assert outcome.degraded is True
    assert outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")
    assert outcome.redrafts == MAX_REDRAFTS
    assert agent.calls.count("guide") == MAX_REDRAFTS + 1


@pytest.mark.asyncio
async def test_the_guide_straying_out_of_the_bridge_language_is_a_failure_wearing_the_g_line(
    patch_agent,
) -> None:
    """The same pre-approved line answers two opposite situations, and only the branch knows.

    Category G affirms a team that rehearsed in its own language. Here nobody rehearsed:
    the Guide itself could not stay in the room's language across three drafts, and the
    room reaches for G because it is the closest thing it holds. Reading the failure off
    the line name would file this one as healthy."""
    patch_agent(
        FakeAgent(
            verdicts=[{"verdict": "pass", "issues": []}] * (MAX_REDRAFTS + 1),
            drafts=["Tell me what you think happens next in this part of the story."]
            * (MAX_REDRAFTS + 1),
        )
    )

    outcome = await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="me conta mais sobre Rute",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=_settings(),
    )

    assert outcome.speech in utterances(FailSafe.OFF_BRIDGE_LANGUAGE, "pt")
    assert outcome.used_fail_safe is True
    assert outcome.degraded is True


@pytest.mark.asyncio
async def test_unparseable_verdict_is_treated_as_a_rejection(patch_agent) -> None:
    class Garbage(FakeAgent):
        async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            is_validator = "corrected_response" in system_prompt
            self.calls.append("validator" if is_validator else "guide")
            return "desculpe, não consigo" if is_validator else "rascunho"

    patch_agent(Garbage(verdicts=[]))

    outcome = await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="alguma coisa",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=_settings(),
    )

    assert outcome.used_fail_safe is True


@pytest.mark.asyncio
async def test_the_redraft_note_carries_the_rejection_back_to_the_guide(patch_agent) -> None:
    agent = patch_agent(
        FakeAgent(
            verdicts=[
                {
                    "verdict": "regenerate",
                    "issues": [{"problem": "imported_knowledge", "claim": "Rute era moabita"}],
                },
                {"verdict": "pass", "issues": []},
            ]
        )
    )
    await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="pergunta",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=_settings(),
    )

    first_call, second_call = agent.guide_inputs[0], agent.guide_inputs[1]
    assert "Nota de reescrita" not in first_call
    assert "Nota de reescrita" in second_call
    assert "imported_knowledge" in second_call
    assert "Rute era moabita" in second_call
