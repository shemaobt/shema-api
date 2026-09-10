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

import anthropic
import httpx2
import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room import llm, usage
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.llm import call_agent, classifier_ladder
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

    def __init__(self, draft: str, verdict: dict[str, Any], cached: bool, refuses: str = ""):
        self.draft = draft
        self.verdict = verdict
        self.cached = cached
        self.refuses = refuses
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        if kwargs["model"] == self.refuses:
            raise anthropic.NotFoundError(
                "nope",
                response=httpx2.Response(
                    status_code=404,
                    request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"),
                ),
                body=None,
            )
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


@pytest.fixture(autouse=True)
def _forget_which_rung_answered():
    """The settled rung outlives a test, so a step-down here would steer a later file."""
    llm._SETTLED.clear()
    usage.forget_sessions()
    yield
    llm._SETTLED.clear()
    usage.forget_sessions()


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
        refuses: str = "",
    ) -> Answers:
        answers = Answers(draft, verdict or {"verdict": "pass", "issues": []}, cached, refuses)
        monkeypatch.setattr(
            llm.anthropic,
            "AsyncAnthropic",
            lambda **options: SimpleNamespace(messages=answers),
        )
        return answers

    return _install


async def _a_turn(
    transcript: str = "A fome chegou e eles partiram.", session_id: str = "s-ferro"
) -> None:
    await _a_turn_on(_settings(), transcript, session_id)


async def _a_turn_on(
    settings: Settings,
    transcript: str = "A fome chegou e eles partiram.",
    session_id: str = "s-ferro",
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
        session_id=session_id,
    )


def _usage_lines(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if getattr(r, "role", None) is not None]


def _turn_line(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    return next(r for r in caplog.records if getattr(r, "turn_calls", None) is not None)


def _session_lines(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if getattr(r, "session_turns", None) is not None]


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


async def test_a_session_that_lost_the_cache_says_so_and_costs_the_difference(
    spoken_by, caplog
) -> None:
    spoken_by(cached=False)

    with caplog.at_level(logging.INFO):
        await _a_turn()
        await _a_turn("E depois, o que aconteceu?")

    turn = _turn_line(caplog)
    assert turn.turn_cache_read_tokens == 0
    assert turn.turn_cost_usd == round(UNCACHED_TURN_COST, 6)
    assert turn.turn_cost_usd > round(GUIDE_COST + VALIDATOR_COST, 6) * 4
    assert _session_lines(caplog)[-1].cache_missed is True, (
        "uma sessão que pagou o mapa inteiro em todo turno chegava ao log como mais uma "
        "sessão com um zero no meio de oito números, e o cache podia estar desligado a "
        "sessão inteira sem ninguém ler o zero"
    )


async def test_one_turn_is_not_enough_to_call_the_cache_broken(spoken_by, caplog) -> None:
    """A session's opening turn writes the entry every turn after it reads.

    Its cache-read counter is zero because there was nothing there to read yet. A run of the
    real room raised the alarm on the first turn of the session and cleared it on the second,
    which is how an alarm stops being read at all.
    """
    spoken_by(cached=False)

    with caplog.at_level(logging.INFO):
        await _a_turn()

    assert _session_lines(caplog)[-1].cache_missed is False


async def test_a_rung_the_key_cannot_use_shows_the_one_below_it_and_why(spoken_by, caplog) -> None:
    spoken_by(refuses="claude-fable-5-1")

    with caplog.at_level(logging.INFO):
        await _a_turn()

    guide = _usage_lines(caplog)[0]
    assert (guide.rung, guide.rung_number) == ("claude-opus-5", 2)
    assert guide.rung_fell_because == "the key cannot use claude-fable-5-1"
    turn = _turn_line(caplog)
    assert turn.turn_rung_number == 2, (
        "uma sessão inteira podia rodar um degrau abaixo do que a doutrina manda e o resumo "
        "do turno não dizia nada; a queda só aparecia numa linha de aviso solta"
    )
    assert turn.turn_rung_fell_because == "the key cannot use claude-fable-5-1"


async def test_a_session_carries_its_running_total_from_the_first_turn(spoken_by, caplog) -> None:
    spoken_by()

    with caplog.at_level(logging.INFO):
        await _a_turn()
        await _a_turn("E depois, o que aconteceu?")

    first, second = _session_lines(caplog)
    assert (first.session_turns, first.session_calls) == (1, 2)
    assert (second.session_turns, second.session_calls) == (2, 4), (
        "nada somava a sessão inteira, e o custo de um piloto de cinco sessões só existia "
        "se alguém somasse 57 turnos à mão"
    )
    assert second.session_cost_usd == round(2 * (GUIDE_COST + VALIDATOR_COST), 6)
    assert second.session_cache_read_tokens == 1_200_000


async def test_two_sessions_at_once_do_not_add_to_each_other(spoken_by, caplog) -> None:
    spoken_by()

    with caplog.at_level(logging.INFO):
        await _a_turn(session_id="s-uma")
        await _a_turn(session_id="s-outra")

    lines = {line.session_id: line for line in _session_lines(caplog)}
    assert [lines["s-uma"].session_turns, lines["s-outra"].session_turns] == [1, 1], (
        "duas equipes traduzindo ao mesmo tempo entravam no mesmo total, e nenhuma das duas "
        "sessões tinha um número que pudesse ser levado ao contrato"
    )


#: What the team says and what the Guide answers, in words that appear nowhere else — so a
#: line that leaked either of them is found by looking for the words themselves.
TEAM_SAID = "a fome levou Elimeleque e Noemi para os campos de Moabe"
GUIDE_SAID = "Elimeleque morreu e Noemi ficou com os dois filhos em Moabe."


def _everything_written(caplog: pytest.LogCaptureFixture) -> str:
    """Every record of the run, message and structured fields alike.

    The fields as well as the message: a leak that rides in `extra` never appears in the
    formatted line and is exactly the kind a review would not catch.
    """
    written = []
    for record in caplog.records:
        written.append(record.getMessage())
        written.extend(str(value) for value in record.__dict__.values())
    return "\n".join(written)


async def test_a_whole_session_leaves_no_word_of_the_passage_behind(spoken_by, caplog) -> None:
    spoken_by(draft=GUIDE_SAID)

    with caplog.at_level(logging.DEBUG):
        await _a_turn(TEAM_SAID)
        await _a_turn("e depois Noemi voltou sozinha para Belém")

    written = _everything_written(caplog)
    for said in (TEAM_SAID, GUIDE_SAID, "Noemi", "Elimeleque", "Belém", "Moabe"):
        assert said not in written, (
            f"o registro do que a sessão custou carregava {said!r} junto; um log operacional "
            f"que repete a passagem entrega a tradução inteira a quem só devia ver números"
        )


def _one_call() -> None:
    usage.record(
        cost_usd=1.0,
        input_tokens=1,
        output_tokens=1,
        cache_read_tokens=1,
        cache_write_tokens=1,
        latency_ms=1,
        rung_number=1,
        rung_fell_because="",
    )


def test_a_ledger_that_has_been_read_takes_no_more_calls() -> None:
    """The turn is answered, its total is written, and the request keeps running.

    Starlette runs a `BackgroundTask` inside the request's own context rather than a new one,
    so the classifier settling the beads behind the reply reaches this code with the finished
    turn's ledger still in scope. Left open, it takes the call — silently, into a total that
    was already logged, where the money is neither reported nor lost but written to a dead
    object.
    """
    spend = usage.open_ledger()
    _one_call()
    usage.close_ledger()

    _one_call()

    assert (spend.calls, spend.cost_usd) == (1, 1.0), (
        "uma chamada depois do turno fechado ainda mutava o livro-caixa do turno já "
        "encerrado, e o contrato escrito no docstring dizia o contrário"
    )


async def test_work_behind_the_turn_is_counted_into_the_session(spoken_by, caplog) -> None:
    """The beads settle after the reply has shipped, and that is still the session's money.

    Marcia's own reading of a pilot names the two apart and adds them: US$ 7.07 on the
    frontier for the Guide, the Validator and the judge, US$ 0.90 on the classifier, about
    US$ 8 in total. A session total that leaves the second out is not the number she read.
    """
    spoken_by()

    with caplog.at_level(logging.INFO):
        await _a_turn()
        with usage.counted_for("s-ferro"):
            await call_agent(
                role="classifier",
                system_prompt="classifique",
                user_content="a troca",
                ladder=classifier_ladder(_settings()),
                settings=_settings(),
            )

    last = _session_lines(caplog)[-1]
    assert (last.session_turns, last.session_calls) == (1, 3), (
        "o classificador rodava fora de qualquer total: a linha dele existia, e o custo "
        "dele não estava em nenhum resumo de sessão"
    )


def test_the_oldest_session_falls_off_and_the_ones_still_running_do_not() -> None:
    """A process answers turns for months; it must not hold a row per session it ever saw.

    What may be dropped is the session nobody is adding to any more, which already has its
    last line in the log. What may not is a session still being answered — so a session
    touched again goes back to the end of the queue rather than ageing where it first landed.
    """
    for number in range(usage._SESSIONS_KEPT):
        usage.session_total(f"s-{number}", usage.Spend(calls=1))
    usage.session_total("s-0", usage.Spend(calls=1))

    usage.session_total("s-nova", usage.Spend(calls=1))

    assert "s-1" not in usage._SESSIONS, (
        "o teto não descartava nada e um processo de meses carregava uma linha por sessão "
        "que já tinha atendido"
    )
    assert usage._SESSIONS["s-0"].turns == 2, (
        "a sessão mais antiga caía mesmo estando viva: quem foi tocado de novo envelhecia "
        "no lugar onde entrou, e a sessão em andamento era a primeira a ser esquecida"
    )
    assert len(usage._SESSIONS) == usage._SESSIONS_KEPT
