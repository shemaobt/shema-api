"""The bead classifier's own rung, and the shape it is made to answer in.

It runs off the voice path and only moves beads, so it rides the cheaper ladder — but it is
the one call whose reply is parsed as JSON rather than spoken, so it is also the only one that
asks the model to answer in a fixed shape.
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
from app.services.internalization_room.classify_coverage import classify_coverage
from app.services.internalization_room.coverage import initial_state, merge

CLASSIFIER = default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"]
P = "P03"


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "anthropic_api_key": "sk-ant-fake",
    }
    base.update(overrides)
    return Settings(**base)


class RecordingMessages:
    def __init__(self, reply: str):
        self.reply = reply
        self.stop_reason = "end_turn"
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.reply)],
            stop_reason=self.stop_reason,
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            ),
        )


@pytest.fixture
def recording_client(monkeypatch: pytest.MonkeyPatch):
    def _install(reply: str = '{"decisions": []}') -> RecordingMessages:
        messages = RecordingMessages(reply)

        def _build(**options: Any) -> SimpleNamespace:
            return SimpleNamespace(messages=messages, options=options)

        monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", _build)
        return messages

    return _install


async def _settle(settings: Settings | None = None) -> dict[str, str]:
    return await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="A fome chegou e eles partiram.",
        guide_response="E o que aconteceu depois?",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=settings or _settings(),
    )


async def test_the_bead_classifier_runs_a_rung_below_the_voice(recording_client) -> None:
    messages = recording_client()

    await _settle()

    assert messages.calls[0]["model"] == "claude-sonnet-5", (
        "o classificador rodava no mesmo gemini-3-flash-preview da voz, sem escada própria"
    )


async def test_the_bead_classifier_is_made_to_answer_in_the_shape_that_is_parsed(
    recording_client,
) -> None:
    messages = recording_client()

    await _settle()

    fmt = messages.calls[0]["output_config"]["format"]
    assert fmt["type"] == "json_schema", (
        "a resposta vinha como texto livre e o parser caçava uma cerca ```json para achar o "
        "objeto; um turno em que o modelo conversava antes do JSON não movia bead nenhum"
    )
    decisions = fmt["schema"]["properties"]["decisions"]
    entry = decisions["items"]["properties"]
    assert set(entry) == {"element_id", "new_status"}, (
        "o esquema tem de nomear exatamente os dois campos que _parse lê"
    )
    assert entry["new_status"]["enum"] == ["surfaced", "engaged"], (
        "o esquema é o que o modelo pode responder; um quarto valor aqui é uma conta que "
        "o parser descarta e a equipe nunca vê mover"
    )


async def test_a_reply_in_the_promised_shape_still_moves_the_beads(recording_client) -> None:
    elements = list(initial_state(P))
    reply = json.dumps({"decisions": [{"element_id": elements[0], "new_status": "engaged"}]})
    recording_client(reply)

    advanced = await _settle()

    assert advanced[elements[0]] == "engaged", (
        "o esquema mudou a forma da resposta e o parser deixou de reconhecê-la"
    )


async def test_a_ceiling_high_enough_now_leaves_room_for_the_thinking_too(
    recording_client,
) -> None:
    messages = recording_client()

    await _settle()

    call = messages.calls[0]
    assert call["thinking"] == {"type": "adaptive"}, (
        "o classificador pensava desligado; essa era a saída de engenharia para conter o "
        "esvaziamento de 9 de setembro, e desligar o pensamento em vez de dar-lhe teto é o "
        "oposto do que ela quer"
    )
    assert call["max_tokens"] == 6000, (
        "4096 era o teto de antes, onde o pensamento adaptativo comia a saída inteira e "
        "voltava vazio em 9 de setembro; no stack dela 6000 é o que sobra pensamento e "
        "decisão, e o classificador roda fora do voice path, então ninguém espera por isso"
    )


async def test_the_fixed_instructions_ride_cached_and_the_moving_beads_do_not(
    recording_client,
) -> None:
    messages = recording_client()
    elements = list(initial_state(P))
    moved = merge(initial_state(P), pericope_num=P, engaged=[elements[0]])

    await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="A fome chegou e eles partiram.",
        guide_response="E o que aconteceu depois?",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )
    await classify_coverage(
        coverage_state=moved,
        team_utterance="Quem era Noemi?",
        guide_response="E o que ela fez?",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )

    first, second = (call["system"] for call in messages.calls)
    assert isinstance(first, list), (
        "o sistema do classificador ia como um texto só, sem fronteira entre o que repete "
        "e o que muda, e o cache não tinha onde ser marcado"
    )
    assert first[0]["cache_control"] == {"type": "ephemeral"}, (
        "o bloco fixo do classificador não trazia marca de cache"
    )
    assert first[0]["text"] == second[0]["text"], (
        "o bloco fixo mudava de bytes entre dois turnos com contas diferentes, então nada "
        "seria servido do cache"
    )
    assert "cache_control" not in first[1], (
        "as contas do turno entravam no cache e escreviam uma entrada por turno"
    )
    assert "## The coverage elements (current unresolved set)" in first[0]["text"], (
        "o corte ficou antes do heading das contas, cacheando menos do que o fixo"
    )
    assert first[1]["text"] != second[1]["text"], (
        "o bloco que deveria trazer as contas do turno ficou igual entre dois turnos com "
        "estados diferentes, então o corte caiu depois do que muda"
    )


async def test_a_classification_cut_off_at_the_ceiling_says_so(recording_client, caplog) -> None:
    messages = recording_client()
    messages.stop_reason = "max_tokens"
    messages.reply = ""
    before = initial_state(P)

    with caplog.at_level(logging.WARNING):
        after = await _settle()

    assert after == before, "uma classificação cortada não pode mover conta nenhuma"
    assert "max_tokens" in caplog.text, (
        "a chamada voltava vazia e o log só dizia que o JSON era ilegível, então o teto — a "
        "causa — não aparecia em lugar nenhum e a leitura era 'o modelo respondeu mal'"
    )
