"""Her planted drafts, B6 to B13, put to the Validator the room sends and judged by her bar.

The bar is the ticket's and hers (`src/turn/runM2.ts:153-190` at a3f3c69): B6, B7, B8 and B13
must not pass, B9, B10 and B11 must, and B12 is observed, never counted. The model here is a
double; the real run is the script's own, once, outside the suite.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.internalization_room.llm import CACHE_BREAK
from scripts import validator_planted_drafts as planted_drafts

TEAM_JUST_SAID = (
    "## WHAT THE TEAM JUST SAID (evidence — NEVER truth about the passage)\n\n"
    "The drafted response answers this. Referring to these words is not a claim about the "
    "passage.\n\n"
)


class _Validator:
    """Refuses the drafts it was told to refuse, passes the rest, and keeps every prompt."""

    def __init__(self, refuses: set[str], reply: str | None = None) -> None:
        self.refuses = refuses
        self.reply = reply
        self.systems: list[str] = []

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        self.systems.append(system_prompt)
        if self.reply is not None:
            return self.reply
        drafted = next(p for p in planted_drafts.PLANTED if p.draft in system_prompt)
        if drafted.id.split()[0] in self.refuses:
            return json.dumps({"verdict": "regenerate", "issues": [{"problem": "invented_detail"}]})
        return json.dumps({"verdict": "pass", "issues": []})


def _answers(monkeypatch: pytest.MonkeyPatch, validator: _Validator) -> _Validator:
    monkeypatch.setattr(planted_drafts, "call_agent", validator)
    return validator


def test_the_drafts_are_her_b6_to_b13_with_the_bar_she_set() -> None:
    assert [(p.id.split()[0], p.must_pass, bool(p.uncounted)) for p in planted_drafts.PLANTED] == [
        ("B6", False, False),
        ("B7", False, False),
        ("B8", False, False),
        ("B9", True, False),
        ("B10", True, False),
        ("B11", True, False),
        ("B12", True, True),
        ("B13", False, False),
    ]
    teams = {p.id.split()[0]: p.team for p in planted_drafts.PLANTED if p.team}
    assert teams == {
        "B8": "A Rute casou com o Malom, né?",
        "B9": "A Rute casou com o Malom, né?",
        "B12": "Tá bom. Pode continuar.",
    }


async def test_a_validator_that_passes_every_draft_fails_her_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _answers(monkeypatch, _Validator(refuses=set()))

    assert await planted_drafts.run() == 1, (
        "um Validador que deixava passar o casamento com Malom dentro de uma pergunta passava"
    )


async def test_a_validator_that_holds_her_line_meets_it_even_with_b12_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _answers(monkeypatch, _Validator(refuses={"B6", "B7", "B8", "B12", "B13"}))

    assert await planted_drafts.run() == 0, "o B12, que ela só observa, derrubava a barra"


async def test_a_validator_that_refuses_a_legitimate_quote_back_fails_her_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _answers(monkeypatch, _Validator(refuses={"B6", "B7", "B8", "B9", "B13"}))

    assert await planted_drafts.run() == 1, (
        "a fala da equipe devolvida como dela era recusada e a barra passava assim mesmo"
    )


async def test_an_unreadable_reply_is_a_failure_never_a_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _answers(monkeypatch, _Validator(refuses=set(), reply="não sei"))

    assert await planted_drafts.run() == 1


async def test_each_draft_meets_her_validator_with_the_teams_words_as_her_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validator = _answers(monkeypatch, _Validator(refuses={"B6", "B7", "B8", "B12", "B13"}))

    await planted_drafts.run()

    by_draft = {
        p.id.split()[0]: s
        for p in planted_drafts.PLANTED
        for s in validator.systems
        if p.draft in s
    }
    assert len(by_draft) == 8
    for system in by_draft.values():
        assert system.count(CACHE_BREAK) == 1
        assert "## PRESERVATION RULES" in system, "o rascunho não era julgado contra Rute 1:1-5"
        assert "Your one job is to check a drafted spoken response" in system
    assert f"{TEAM_JUST_SAID}A Rute casou com o Malom, né?" in by_draft["B8"]
    assert f"{TEAM_JUST_SAID}Tá bom. Pode continuar." in by_draft["B12"]
    assert "## WHAT THE TEAM JUST SAID" not in by_draft["B6"], (
        "um rascunho sem fala da equipe ganhava um bloco de evidência vazio de cabeçalho"
    )
