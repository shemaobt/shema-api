"""What a session leaves behind about what it cost, and what it must never leave behind.

These drive whole turns with the Anthropic client faked rather than with the usual
`run_turn.call_agent` fake. The numbers this file is about — the tokens the provider reported,
the rung that answered, how long the call took — do not exist at the `call_agent` seam, so a
test written there would assert on its own fixture and would go on passing with the whole
accounting deleted.

The expected dollars are worked out by hand from the published list prices and written in as
literals, never recomputed the way the code under test computes them: a test that multiplies
the same table by the same tokens agrees with a wrong table.
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room import llm
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.run_turn import run_turn

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"

#: What the fake provider reports for each of a turn's two calls. The two differ on purpose:
#: a total that reconciles is only visible when the numbers it sums are not one number twice.
GUIDE_USAGE = {
    "input_tokens": 1_000,
    "output_tokens": 500,
    "cache_creation_input_tokens": 100_000,
    "cache_read_input_tokens": 200_000,
}
VALIDATOR_USAGE = {
    "input_tokens": 2_000,
    "output_tokens": 1_000,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 400_000,
}

#: Worked out from Claude Fable 5.1's published prices — US$ 10 / 50 / 12.50 / 0.25 per million
#: input / output / cache-write / cache-read tokens.
#: Guide: 1 000 x 10 + 500 x 50 + 100 000 x 12.50 + 200 000 x 0.25 = 1 335 000 / 1e6.
GUIDE_COST = 1.335
#: Validator: 2 000 x 10 + 1 000 x 50 + 0 + 400 000 x 0.25 = 170 000 / 1e6.
VALIDATOR_COST = 0.17

#: The same two calls with the cache dead: every token the map contributed is billed as fresh
#: input instead. Guide: (1 000 + 100 000 + 200 000) x 10 + 500 x 50 = 3 035 000 / 1e6.
#: Validator: (2 000 + 400 000) x 10 + 1 000 x 50 = 4 070 000 / 1e6.
UNCACHED_TURN_COST = 3.035 + 4.07


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "anthropic_api_key": "sk-ant-fake",
    }
    base.update(overrides)
    return Settings(**base)


def _system_text(call: dict[str, Any]) -> str:
    system = call["system"]
    if isinstance(system, str):
        return system
    return "".join(block["text"] for block in system)


def _is_validator(call: dict[str, Any]) -> bool:
    return "corrected_response" in _system_text(call)


def _uncached(usage: dict[str, int]) -> dict[str, int]:
    """The same call with the cache dead: what was served from it is billed as fresh input.

    Written out rather than zeroing the counters, because zeroed counters alone would leave
    the cost unchanged and the test would prove only that a number moved.
    """
    return {
        "input_tokens": usage["input_tokens"]
        + usage["cache_read_input_tokens"]
        + usage["cache_creation_input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }


class Answers:
    """One fake model for a whole turn, reporting its own usage per role."""

    def __init__(self, draft: str, verdict: dict[str, Any], cached: bool):
        self.draft = draft
        self.verdict = verdict
        self.cached = cached
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        validating = _is_validator(kwargs)
        usage = VALIDATOR_USAGE if validating else GUIDE_USAGE
        if not self.cached:
            usage = _uncached(usage)
        return SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="text", text=json.dumps(self.verdict) if validating else self.draft
                )
            ],
            stop_reason="end_turn",
            model=kwargs["model"],
            usage=SimpleNamespace(**usage),
        )


@pytest.fixture
def spoken_by(monkeypatch: pytest.MonkeyPatch):
    """Install one fake provider behind every client the room builds this test.

    `call_agent` builds a client per call, so the recorder has to outlive the client or a
    two-call turn is seen as one.
    """

    def _install(
        draft: str = "Ensaiem essa parte entre vocês.",
        verdict: dict[str, Any] | None = None,
        cached: bool = True,
    ) -> Answers:
        answers = Answers(draft, verdict or {"verdict": "pass", "issues": []}, cached)
        monkeypatch.setattr(
            llm.anthropic,
            "AsyncAnthropic",
            lambda **options: SimpleNamespace(messages=answers),
        )
        return answers

    return _install


async def _a_turn(transcript: str = "A fome chegou e eles partiram.") -> None:
    await _a_turn_on(_settings(), transcript)


async def _a_turn_on(
    settings: Settings, transcript: str = "A fome chegou e eles partiram."
) -> None:
    await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript=transcript,
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=settings,
        session_id="s-ferro",
    )


def _usage_lines(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if getattr(r, "role", None) is not None]


def _turn_line(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    return next(r for r in caplog.records if getattr(r, "turn_calls", None) is not None)


async def test_every_model_call_leaves_one_line_of_what_it_cost(spoken_by, caplog) -> None:
    spoken_by()

    with caplog.at_level(logging.INFO):
        await _a_turn()

    lines = _usage_lines(caplog)
    assert [line.role for line in lines] == ["guide", "validator"], (
        "as duas chamadas de um turno chegavam ao log sem dizer qual delas era qual, e uma "
        "conta cara não tinha como ser atribuída ao Guia ou ao Validador"
    )
    guide, validator = lines
    assert (guide.rung, guide.rung_number) == ("claude-fable-5-1", 1), (
        "a linha não dizia em que degrau da escada a resposta veio, que é a diferença entre "
        "um turno bom e um turno degradado"
    )
    assert guide.effort == "high"
    assert (guide.input_tokens, guide.output_tokens) == (1_000, 500)
    assert (guide.cache_write_tokens, guide.cache_read_tokens) == (100_000, 200_000)
    assert guide.latency_ms >= 0, (
        "a latência era medida só para o turno inteiro, e uma chamada lenta escondida atrás "
        "de uma rápida ficava invisível"
    )
    assert (guide.cost_usd, validator.cost_usd) == (GUIDE_COST, VALIDATOR_COST), (
        "o custo de tabela não era calculado em lugar nenhum, e o piloto só descobriria o "
        "preço de uma sessão na fatura do mês seguinte"
    )


async def test_a_turn_totals_the_calls_it_made(spoken_by, caplog) -> None:
    spoken_by()

    with caplog.at_level(logging.INFO):
        await _a_turn()

    turn = _turn_line(caplog)
    assert turn.turn_calls == 2
    assert turn.turn_cost_usd == round(GUIDE_COST + VALIDATOR_COST, 6), (
        "o turno não somava as suas próprias chamadas, então o número de referência da "
        "Marcia — US$ 0,14 por turno com o mapa em cache — não tinha com o que ser comparado"
    )
    assert (turn.turn_input_tokens, turn.turn_output_tokens) == (3_000, 1_500)
    assert (turn.turn_cache_read_tokens, turn.turn_cache_write_tokens) == (600_000, 100_000), (
        "o total do turno não repetia o uso que o provedor reportou, e uma conta que não "
        "reconcilia com a fatura não prova nada"
    )
    assert turn.turn_unpriced_calls == 0


async def test_a_turn_on_an_unpriced_rung_says_the_total_is_short(spoken_by, caplog) -> None:
    spoken_by()

    with caplog.at_level(logging.INFO):
        await _a_turn_on(_settings(tripod_voice_model="claude-not-in-the-table"))

    turn = _turn_line(caplog)
    assert turn.turn_unpriced_calls == 2, (
        "um degrau que a tabela não conhece entrava no total como zero dólares, e uma "
        "sessão inteira num modelo novo era relatada como se fosse de graça"
    )


async def test_a_turn_that_lost_the_cache_says_so_and_costs_the_difference(
    spoken_by, caplog
) -> None:
    spoken_by(cached=False)

    with caplog.at_level(logging.INFO):
        await _a_turn()

    turn = _turn_line(caplog)
    assert turn.turn_cache_read_tokens == 0
    assert turn.turn_cost_usd == round(UNCACHED_TURN_COST, 6)
    assert turn.turn_cost_usd > round(GUIDE_COST + VALIDATOR_COST, 6) * 4
    assert turn.cache_missed is True, (
        "um turno que pagou o mapa inteiro de novo chegava ao log como mais um turno com um "
        "zero no meio de oito números, e o cache podia estar desligado a sessão inteira sem "
        "ninguém ler o zero"
    )
