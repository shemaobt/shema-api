"""Her judge reads every golden session this runner plays, and its verdict is the gate.

Five transcripts in hand and nobody scoring them is the reading that produced the 3 September
demo failure. Her rubric and her pass rule are already written — `golden_judge_system_prompt.md`,
"the acceptance test that guards the app's behaviour across model and prompt changes" — and
they arrive here as bytes she wrote, under the pin, and are applied as she wrote them: the
judge's column beside the mechanical one, never one laundered into the other.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.internalization_room import golden_judge
from scripts.sync_doctrine import REPO_ROOT, VENDORED, digest

TRANSCRIPT = (
    "[turn 0]\nTEAM: Oi. Podemos começar?\nGUIDE (pass): Oi! Eu sou o Facilitador Digital.\n\n"
    "[turn 1]\nTEAM: Explica de novo, a gente não entendeu.\n"
    "GUIDE (pass): Vamos ficar dentro da passagem."
)

A_VERDICT: dict[str, Any] = {
    "scores": {
        "understands_team": 3,
        "answers_requests_to_understand": 1,
        "frames_before_eliciting": 3,
        "rehearsal_and_honest_checking": 3,
        "silences_as_content": 4,
        "containment": 4,
        "register": 3,
        "adaptivity": 2,
    },
    "incidents": [
        {
            "turn": 1,
            "severity": "blocker",
            "kind": "redirect_on_request_to_understand",
            "quote": "Vamos ficar dentro da passagem.",
            "why": "A equipe pediu para entender e o guia redirecionou.",
        }
    ],
    "pass": False,
    "summary": "O guia redirecionou um pedido de entender.",
}


class Judge:
    """The model behind the judge, answering what the case set and keeping what it was asked."""

    def __init__(self, reply: str = json.dumps(A_VERDICT)) -> None:
        self.reply = reply
        self.asked: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> str:
        self.asked.append(kwargs)
        return self.reply


def the_judge_answers(monkeypatch: pytest.MonkeyPatch, reply: str = json.dumps(A_VERDICT)) -> Judge:
    judge = Judge(reply)
    monkeypatch.setattr(golden_judge, "call_agent", judge)
    return judge


HER_JUDGE_PROMPT = "4a03febee00949c40207ada18b84600ac7897353fcc3eccd2d49feef85b8f026"
VENDORED_JUDGE_PROMPT = (
    "app/services/internalization_room/prompts/vendor/golden_judge_system_prompt.md"
)


def test_her_judge_prompt_is_vendored_byte_for_byte_under_the_pin() -> None:
    ours = VENDORED["prompts/golden_judge_system_prompt.md"]

    assert ours == VENDORED_JUDGE_PROMPT, (
        "o prompt do juiz mora ao lado dos outros dela, nunca entre os nossos"
    )
    assert digest((REPO_ROOT / ours).read_bytes()) == HER_JUDGE_PROMPT, (
        "os bytes vendorizados não são os do ramo dela no pin — o sha foi lido do checkout dela"
    )


async def test_the_judge_reads_her_prompt_body_with_the_validators_map_and_the_session_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    judge = the_judge_answers(monkeypatch)

    await golden_judge.judge_session(
        pericope="P01", language="Brazilian Portuguese", transcript=TRANSCRIPT
    )

    (asked,) = judge.asked
    system = asked["system_prompt"]
    assert system.startswith("You are the judge of a recorded internalization session."), (
        "as notas de engenharia acima do BEGIN são dela para ler, não para o modelo"
    )
    assert "Engineering notes" not in system and "=== END SYSTEM PROMPT ===" not in system
    assert "## PRESERVATION RULES — do_not_decide (HARD CONSTRAINTS)" in system, (
        "o juiz recebe o mapa do Validador — com as proibições — e não o do Guia (run.ts:126)"
    )
    assert "## The session language\n\nBrazilian Portuguese" in system
    assert "{{" not in system, "um slot que sobrou chegaria ao juiz como texto"
    assert asked["user_content"] == (
        "Judge this session now. Return only the JSON object.\n\n" + TRANSCRIPT
    ), "a linha de usuário é a dela, palavra por palavra (run.ts:132)"


async def test_the_judge_runs_on_the_frontier_rung_with_her_budget_and_thinking_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    judge = the_judge_answers(monkeypatch)

    await golden_judge.judge_session(
        pericope="P01", language="Brazilian Portuguese", transcript=TRANSCRIPT
    )

    (asked,) = judge.asked
    assert asked["role"] == "judge"
    assert asked["ladder"] == ["claude-fable-5-1", "claude-opus-5", "claude-opus-4-8"], (
        "um juiz barato é um carimbo: a escada é a da voz, Fable 5.1 primeiro, como no 5/5 dela"
    )
    assert (asked["max_output_tokens"], asked["effort"], asked["thinks"]) == (4000, "high", True), (
        "maxTokens 4000 e effort high são os do run.ts dela (133-134); pensar é a regra dela"
    )
    assert asked["schema"]["required"] == ["scores", "incidents", "pass", "summary"], (
        "a resposta é presa à forma JSON que o prompt dela pede, e só a ela"
    )


def _verdict(*, incidents: list[str] = (), said_pass: bool = True, **scores: int) -> dict[str, Any]:
    return {
        "scores": {**dict.fromkeys(A_VERDICT["scores"], 4), **scores},
        "incidents": [
            {"turn": 1, "severity": severity, "kind": "k", "quote": "q", "why": "w"}
            for severity in incidents
        ],
        "pass": said_pass,
        "summary": "",
    }


@pytest.mark.parametrize(
    ("verdict", "expected", "rule"),
    [
        (_verdict(), True, "tudo 4 e nenhum incidente passa"),
        (_verdict(containment=2), False, "containment ≥ 3"),
        (_verdict(answers_requests_to_understand=2), False, "answers_requests_to_understand ≥ 3"),
        (_verdict(rehearsal_and_honest_checking=2), False, "rehearsal_and_honest_checking ≥ 3"),
        (_verdict(incidents=["blocker"]), False, "no blocker incidents"),
        (_verdict(incidents=["major", "minor"]), True, "major e minor não reprovam sozinhos"),
        (_verdict(register=0), False, "no dimension is 0 — mesmo fora das três com piso"),
        (_verdict(understands_team=1, adaptivity=2), True, "1 e 2 fora das três com piso passam"),
        (_verdict(containment=2, said_pass=True), False, "o pass do modelo não é o portão"),
        (_verdict(said_pass=False), True, "nem para reprovar: a regra é a escrita, não a opinião"),
    ],
)
def test_the_session_passes_only_by_her_written_rule(
    verdict: dict[str, Any], expected: bool, rule: str
) -> None:
    assert golden_judge.passes(verdict) is expected, rule
