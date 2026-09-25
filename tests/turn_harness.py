"""The draft-and-gate loop's two models, and the doubles a case puts in their place.

Every case about a turn needs the same three things: the prompts the room really ships, a
`Settings` that reaches no network, and a stand-in for the model that answers what the case
decided rather than what a model would. The verdict turn needs one more — a Validator that
judges from the prompt it was handed and from nothing else, which is the whole of the
incident the cases around it record.

Fixtures are not exported, for the reason `room_harness` gives: what travels is the builder,
and each module keeps the three-line fixture that calls it.

The passage is declared here rather than read off `release_harness`, which also names it. A
turn is judged with no release anywhere in sight, and reading it from there would put the
release scaffold behind every case about the draft-and-gate loop.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSegment
from app.services.internalization_room import room_agent as provider
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.room_agent import Agent, CallAgent

P = "P03"

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
SPEAKER = default_prompt(IRPromptKey.BT_VERDICT_SPEAKER)["prompt"]

INVITATION = (
    " Now rehearse this scene together in your own language; when you have finished, come "
    "back and tell me in English what you understood."
)


def settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


def stretch(number: int, text: str) -> IRSegment:
    """One stretch, as far as the analyst is concerned: an address and what was told."""
    return IRSegment(
        id=f"segmento-{number}",
        session_id="sessao-1",
        ordinal=number,
        take_id="ensaio-1",
        starts_ms=(number - 1) * 9000,
        ends_ms=number * 9000,
        transcript=text,
    )


def told_stretches() -> list[IRSegment]:
    return [
        stretch(1, "Noemi mandou Rute voltar."),
        stretch(2, "Rute disse que ia junto."),
    ]


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


def the_room_agent_is(
    monkeypatch: pytest.MonkeyPatch,
    *,
    turn: CallAgent | None = None,
    strays_from: Callable[[str, str], bool] | None = None,
) -> None:
    swapped: dict[str, Any] = {}
    if turn is not None:
        swapped["turn"] = Agent(call_agent=turn)
    if strays_from is not None:
        swapped["strays_from"] = strays_from
    monkeypatch.setattr(provider, "_current", replace(provider.room_agent(), **swapped))


def the_agent_answers(monkeypatch: pytest.MonkeyPatch, agent: FakeAgent) -> FakeAgent:
    """Swap the turn's `call_agent` for a fake."""
    the_room_agent_is(monkeypatch, turn=agent)
    return agent


def the_speaker_answers(monkeypatch: pytest.MonkeyPatch, draft: str):
    """The verdict Speaker saying one fixed line, with the Validator passing behind it."""
    seen: list[str] = []

    async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        seen.append(system_prompt)
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return draft

    agent.seen = seen  # type: ignore[attr-defined]
    the_room_agent_is(monkeypatch, turn=agent)
    return agent


#: What the room's own closings send the team to do, each with the words the Validator's
#: brief has to carry before a draft may say it.
DESTINATIONS = {
    "aqui na tela": "on screen",
    "no microfone daquela": "tap the microphone",
    "gravar o que ainda falta": "record what is still missing",
    "Ouçam a gravação": "listen to their own recording once more",
    "no WhatsApp": "on WhatsApp",
}

#: The words the ordered closing of the checked turn has to carry, named one by one rather
#: than as the whole constant: the case is that the team is invited to *these two things*, and
#: an assertion on the constant would agree with whatever it happened to say. Shared because
#: the service seam and the door both read them off the same closing.
INVITATION_WORDS = ("listen to", "once more", "approve", "final draft")

#: The prompt's own promise of a next round, spliced into every closing but the checked one.
#: That turn has no next round, so this and it may not both reach the Speaker on the same turn.
CONTINUES_TELLING_BACK = "finish the telling-back again"

_ATTRIBUTION = re.compile(r"[Vv]ocê contou que ([^.?!]+)")
_PROPER_NAME = re.compile(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕ][\wáéíóúâêôãõç]+")


class ValidatorReadsOnlyItsOwnPrompt:
    """The loop's two models: the Speaker hands back one fixed draft, the Validator judges it.

    The Validator double decides from the prompt it was handed and from nothing else, which
    is the whole of what the incident was: the real Validator reasoned correctly from
    evidence the room had never given it. A double answering `pass` unconditionally could
    not reproduce that at all, and one answering `regenerate` would be dictating the outcome
    the case claims to observe.

    Three rules, each of them a lookup in its own prompt:

    * a draft that speaks about the telling-back needs the telling-back in front of it;
    * a draft that sends the team somewhere needs its brief to name that destination;
    * a draft that attributes words to the team needs those words in the telling-back.

    The draft under judgment is subtracted from the prompt before any lookup: a draft is
    quoted into `DRAFTED_RESPONSE`, and a rule reading that back would find every claim
    supported by the claim itself.
    """

    def __init__(self, draft: str, told: list[IRSegment]) -> None:
        self.draft = draft
        self.told = told
        #: Each Validator system prompt with the draft taken out — what the room actually
        #: showed it, as opposed to what the Guide wrote.
        self.briefs: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" not in system_prompt:
            return self.draft
        brief = system_prompt.replace(self.draft, "")
        self.briefs.append(brief)
        return json.dumps(self._verdict(brief))

    def _verdict(self, brief: str) -> dict[str, Any]:
        shown = "\n".join(
            segment.transcript for segment in self.told if segment.transcript in brief
        )
        issues: list[dict[str, str]] = []
        if "me contou de volta" in self.draft and not shown:
            issues.append(
                {
                    "claim": "No que você me contou de volta",
                    "problem": "conversational_mismatch",
                    "explanation": "nada aqui mostra que a equipe contou alguma coisa de volta",
                }
            )
        for destination, warrant in DESTINATIONS.items():
            if destination in self.draft and warrant not in brief:
                issues.append(
                    {
                        "claim": destination,
                        "problem": "workflow_policy_violation",
                        "explanation": "essa navegação não foi a que o app mandou dar",
                    }
                )
        for name in self._attributed_names():
            if name not in shown:
                issues.append(
                    {
                        "claim": name,
                        "problem": "conversational_mismatch",
                        "explanation": "a equipe não contou isso",
                    }
                )
        if issues:
            return {"verdict": "regenerate", "issues": issues}
        return {"verdict": "pass", "issues": []}

    def _attributed_names(self) -> list[str]:
        """The people and places the draft says the team told back."""
        attributed = _ATTRIBUTION.search(self.draft)
        return _PROPER_NAME.findall(attributed.group(1)) if attributed else []


def the_loop_answers(
    monkeypatch: pytest.MonkeyPatch, draft: str, told: list[IRSegment]
) -> ValidatorReadsOnlyItsOwnPrompt:
    """Both ends of the draft-and-gate loop, with a Validator that judges by its evidence."""
    agent = ValidatorReadsOnlyItsOwnPrompt(draft, told)
    the_room_agent_is(monkeypatch, turn=agent)
    return agent
