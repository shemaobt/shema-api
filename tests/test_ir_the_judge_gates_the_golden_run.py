"""Her judge reads every golden session this runner plays, and its verdict is the gate.

Five transcripts in hand and nobody scoring them is the reading that produced the 3 September
demo failure. Her rubric and her pass rule are already written — `golden_judge_system_prompt.md`,
"the acceptance test that guards the app's behaviour across model and prompt changes" — and
they arrive here as bytes she wrote, under the pin, and are applied as she wrote them: the
judge's column beside the mechanical one, never one laundered into the other.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.internalization_room import golden_judge, llm
from scripts.sync_doctrine import FROZEN, REPO_ROOT, digest
from tests.text_seam_harness import A_VERDICT, the_judge_answers

TRANSCRIPT = (
    "[turn 0]\nTEAM: Oi. Podemos começar?\nGUIDE (pass): Oi! Eu sou o Facilitador Digital.\n\n"
    "[turn 1]\nTEAM: Explica de novo, a gente não entendeu.\n"
    "GUIDE (pass): Vamos ficar dentro da passagem."
)


HER_JUDGE_PROMPT = "394a36339a91ad7c3c1ab2da23d96a7b27a16a67e883b03efee1fa77f8b90dc1"
FROZEN_JUDGE_PROMPT = "app/services/internalization_room/prompts/golden_judge_system_prompt.md"


def test_the_judge_reads_her_prompt_at_the_freeze_by_its_fingerprint() -> None:
    ours = FROZEN["prompts/golden_judge_system_prompt.md"]

    assert ours == FROZEN_JUDGE_PROMPT, "o juiz dela mora entre os nove prompts dela"
    assert REPO_ROOT / ours == golden_judge.HER_PROMPT, (
        "o juiz lia a cópia de 533b6e3, de 103 linhas, sem as decisões de setembro"
    )
    assert digest((REPO_ROOT / ours).read_bytes()) == HER_JUDGE_PROMPT, (
        "os bytes não são os do apêndice A do PRD — o sha foi lido de lá"
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
    assert "Her word:" not in system, "as decisões datadas acima do BEGIN não chegam ao juiz"
    assert "kind `team_reading_confirmed`" in system, (
        "o juiz antigo não conhecia a leitura da equipe confirmada como incidente"
    )
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
    assert (asked["max_output_tokens"], asked["effort"], asked["thinks"]) == (
        16000,
        "high",
        True,
    ), (
        "effort high é o do run.ts dela (134); pensar é a regra dela; o teto é um que o juiz não "
        "alcança — os 4000 dela cortaram um veredito em quatro nesta sala"
    )
    assert asked["schema"]["required"] == ["scores", "incidents", "pass", "summary"], (
        "a resposta é presa à forma JSON que o prompt dela pede, e só a ela"
    )


async def test_a_judge_call_that_nothing_follows_is_sent_without_a_cache_mark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    judge = the_judge_answers(monkeypatch)

    await golden_judge.judge_session(
        pericope="P01", language="Brazilian Portuguese", transcript=TRANSCRIPT
    )

    (asked,) = judge.asked
    assert llm.CACHE_BREAK not in asked["system_prompt"], (
        "um script sozinho na passagem escrevia ~19,6k tokens no cache a 1,25x e ninguém lia"
    )


async def test_a_judge_prompt_another_script_repeats_is_marked_whole_and_is_the_same_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    judge = the_judge_answers(monkeypatch)

    await golden_judge.judge_session(
        pericope="P01",
        language="Brazilian Portuguese",
        transcript=TRANSCRIPT,
        prompt_repeats=True,
    )
    await golden_judge.judge_session(
        pericope="P01", language="Brazilian Portuguese", transcript=TRANSCRIPT
    )

    marked, alone = judge.asked
    assert marked["system_prompt"].endswith(llm.CACHE_BREAK), (
        "o segundo script da passagem não leria nada: sem a marca no fim o prompt inteiro não é "
        "cacheado"
    )
    assert marked["system_prompt"].removesuffix(llm.CACHE_BREAK) == alone["system_prompt"], (
        "a marca é só o fim do prompt: o texto dela, o mapa e a língua são os mesmos com ou sem ela"
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
