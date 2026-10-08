from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.internalization_room import llm
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.run_turn import run_turn
from app.services.internalization_room.verdict_turn import run_verdict_turn
from tests.turn_harness import (
    GUIDE,
    SPEAKER,
    VALIDATOR,
    FakeAgent,
    P,
    settings,
    the_agent_answers,
)

REGENERATE = {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]}
PASS = {"verdict": "pass", "issues": []}


def _is_validator(request: dict[str, Any]) -> bool:
    system = request["system"]
    text = system if isinstance(system, str) else "".join(block["text"] for block in system)
    return "corrected_response" in text


class TheWire:
    """The Anthropic client the room talks to, answering from what each request is."""

    def __init__(self, *, refusing: tuple[str, ...] = (), verdicts: list[dict] | None = None):
        self.refusing = refusing
        self.verdicts = verdicts or [PASS]
        self.requests: list[dict[str, Any]] = []

    @property
    def guide_requests(self) -> list[dict[str, Any]]:
        return [request for request in self.requests if not _is_validator(request)]

    @property
    def validator_requests(self) -> list[dict[str, Any]]:
        return [request for request in self.requests if _is_validator(request)]

    async def create(self, **request: Any) -> SimpleNamespace:
        self.requests.append(request)
        if _is_validator(request):
            asked = len(self.validator_requests)
            text = json.dumps(self.verdicts[min(asked, len(self.verdicts)) - 1])
            stop_reason = "end_turn"
        elif request["model"] in self.refusing:
            text, stop_reason = "", "refusal"
        else:
            text, stop_reason = "Ensaiem essa parte entre vocês.", "end_turn"
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)] if text else [],
            stop_reason=stop_reason,
            model=request["model"],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
                cache_creation=None,
            ),
        )


@pytest.fixture
def the_wire(monkeypatch: pytest.MonkeyPatch):
    def _install(wire: TheWire) -> TheWire:
        monkeypatch.setattr(
            llm.anthropic,
            "AsyncAnthropic",
            lambda **options: SimpleNamespace(messages=wire, options=options),
        )
        return wire

    llm._SETTLED.clear()
    yield _install
    llm._SETTLED.clear()


async def _a_turn():
    return await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="A fome chegou e eles partiram.",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=settings(),
    )


async def _a_turn_on_the_wire():
    return await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="A fome chegou e eles partiram.",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=settings(),
    )


@pytest.mark.parametrize(
    ("drafts", "verdicts", "calls"),
    [
        pytest.param([""] * 3, [PASS] * 3, ["guide"], id="the first draft"),
        pytest.param(["[[CENA]]"] * 3, [PASS] * 3, ["guide"], id="a draft that was only the mark"),
        pytest.param(
            ["rascunho", "", ""],
            [REGENERATE, PASS, PASS],
            ["guide", "validator", "guide"],
            id="the redraft",
        ),
    ],
)
async def test_an_empty_draft_is_the_fail_safe_at_once_and_never_reaches_the_validator(
    monkeypatch: pytest.MonkeyPatch, drafts: list[str], verdicts: list[dict], calls: list[str]
) -> None:
    agent = the_agent_answers(monkeypatch, FakeAgent(verdicts=verdicts, drafts=drafts))

    outcome = await _a_turn()

    assert outcome.used_fail_safe is True, (
        "um rascunho vazio ia ao Validador, que podia aprová-lo como fala vazia ou escrever "
        "uma correção no lugar do Guia"
    )
    assert outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")
    assert agent.calls == calls, (
        "o rascunho vazio ainda custava uma leitura do Validador e outra reescrita antes da "
        "linha de segurança que o app dela dá na hora"
    )
    assert outcome.draft == ""
    assert outcome.verdict == ""


async def test_a_voice_refused_twice_is_rerun_once_then_the_fail_safe_with_no_third_model(
    the_wire,
) -> None:
    wire = the_wire(TheWire(refusing=("claude-fable-5-1", "claude-opus-5")))

    outcome = await _a_turn_on_the_wire()

    assert [request["model"] for request in wire.guide_requests] == [
        "claude-fable-5-1",
        "claude-opus-5",
    ], "a recusa que ficou de pé era redigida de novo, e cada reescrita pedia mais dois modelos"
    assert wire.validator_requests == [], (
        "a resposta vazia da recusa ia ao Validador como se fosse um rascunho"
    )
    assert outcome.used_fail_safe is True
    assert outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")


async def test_a_send_back_with_three_issues_is_one_redraft_with_her_note_as_its_own_message(
    the_wire,
) -> None:
    sent_back = {
        "verdict": "regenerate",
        "issues": [
            {
                "problem": "imported_knowledge",
                "claim": "Rute era moabita",
                "explanation": "o mapa não diz de que povo ela era",
            },
            {
                "problem": "invented_detail",
                "claim": "Noemi chorou",
                "explanation": "não há choro no mapa",
            },
            {
                "problem": "altered_tone",
                "claim": "disse com raiva",
                "explanation": "o mapa a deixa calma",
            },
        ],
    }
    wire = the_wire(TheWire(verdicts=[sent_back, PASS]))

    outcome = await _a_turn_on_the_wire()

    assert outcome.redrafts == 1
    first, redraft = wire.guide_requests
    assert first["messages"] == [
        {"role": "user", "content": "A fome chegou e eles partiram."},
    ]
    assert redraft["messages"] == [
        {"role": "user", "content": "A fome chegou e eles partiram."},
        {
            "role": "user",
            "content": "(internal redraft note — the previous draft carried something the map "
            "does not support: imported_knowledge: Rute era moabita — o mapa não diz de que "
            "povo ela era; invented_detail: Noemi chorou — não há choro no mapa; altered_tone: "
            "disse com raiva — o mapa a deixa calma. Redraft the same answer, as fully as the "
            "team's request deserves, using only what the map contains.)",
        },
    ], (
        "a nota ia colada às palavras da equipe, sob '## Rewrite note', na mesma mensagem; "
        "no app dela é uma mensagem própria, depois do que a equipe disse"
    )


async def test_a_verdict_sent_back_is_redrafted_from_her_kickoff_and_her_note_with_no_history(
    the_wire,
) -> None:
    wire = the_wire(TheWire(verdicts=[{"verdict": "regenerate", "issues": []}, PASS]))

    await run_verdict_turn(
        findings_text='[{"kind": "addition", "frase": 1}]',
        scope="P02",
        pericope_num="P02",
        messages=[{"role": "guide", "text": "Contem de volta o que ouviram."}],
        telling_back="1. Noemi voltou com as noras.",
        speaker_prompt=SPEAKER,
        validator_prompt=VALIDATOR,
        session_language="Brazilian Portuguese",
        language_code="pt",
        settings=settings(),
    )

    _, redraft = wire.guide_requests
    assert redraft["messages"] == [
        {
            "role": "user",
            "content": "(The team heard their whole recording, told it back frase by frase, "
            "and tapped 'terminei'. Speak the verdict now.)",
        },
        {
            "role": "user",
            "content": "(internal redraft note — the previous draft carried something the map "
            "does not support: ungrounded content. Redraft the same answer, as fully as the "
            "team's request deserves, using only what the map contains.)",
        },
    ], "o veredito reescrito levava a nota grudada no pontapé dela, como se fosse um só pedido"
