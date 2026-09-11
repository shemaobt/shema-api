"""Which rung reads the telling-back, and which one checks a correction against a finding.

Neither is spoken and neither is on the voice path, but both judge what the team said against
the Meaning Map — the hardest reading the room does — so they run the analysis ladder rather
than the classifier's.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSegment
from app.services.internalization_room import llm
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.back_translation import (
    Finding,
    FindingKind,
    analyse_telling_back,
    verify_correction,
)

ANALYST = default_prompt(IRPromptKey.BT_ANALYST)["prompt"]
CORRECTION = default_prompt(IRPromptKey.BT_CORRECTION)["prompt"]
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
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.reply)],
            stop_reason="end_turn",
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
    def _install(reply: str) -> RecordingMessages:
        messages = RecordingMessages(reply)

        def _build(**options: Any) -> SimpleNamespace:
            return SimpleNamespace(messages=messages, options=options)

        monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", _build)
        return messages

    return _install


def _segment(number: int, text: str) -> IRSegment:
    return IRSegment(
        id=f"segmento-{number}",
        session_id="sessao-1",
        ordinal=number,
        take_id="ensaio-1",
        starts_ms=(number - 1) * 9000,
        ends_ms=number * 9000,
        transcript=text,
    )


async def test_the_analyst_reads_the_telling_back_on_the_analysis_ladder(
    recording_client,
) -> None:
    messages = recording_client(json.dumps({"evidence_sufficient": True, "findings": []}))

    await analyse_telling_back(
        segments=[_segment(1, "A fome chegou e eles partiram.")],
        scope="1-5",
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(tripod_analysis_model="modelo-de-analise-sob-teste"),
    )

    assert messages.calls[0]["model"] == "modelo-de-analise-sob-teste", (
        "o analista lia o contado de volta contra o mapa no modelo da VOZ e TRIPOD_ANALYSIS_"
        "MODEL não tinha consumidor nenhum: mudar a variável não mudava nada"
    )


async def test_the_correction_check_reads_on_the_analysis_ladder(recording_client) -> None:
    messages = recording_client(json.dumps({"resolved": True, "findings": []}))

    await verify_correction(
        findings=[Finding(kind=FindingKind.MISSING, note="a fome nao foi contada")],
        earlier=_segment(1, "Eles partiram."),
        corrected=_segment(2, "A fome chegou e eles partiram."),
        chunk=1,
        scope="1-5",
        pericope_num=P,
        correction_prompt=CORRECTION,
        settings=_settings(tripod_analysis_model="modelo-de-analise-sob-teste"),
    )

    assert messages.calls[0]["model"] == "modelo-de-analise-sob-teste", (
        "a checagem de correção decide se um trecho regravado responde ao achado, e lia isso "
        "no modelo da voz em vez do papel de análise"
    )


async def test_the_analysis_ladder_starts_where_the_voice_ladder_does(recording_client) -> None:
    """The ladder shipped for analysis, with nothing overridden.

    Marcia's own stack runs the telling-back analysis on the voice ladder — `anthropicLlm()`
    with no argument — so ours starts there too rather than inventing a cheaper rung for the
    reading the whole verdict rests on.
    """
    messages = recording_client(json.dumps({"evidence_sufficient": True, "findings": []}))

    await analyse_telling_back(
        segments=[_segment(1, "A fome chegou e eles partiram.")],
        scope="1-5",
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert messages.calls[0]["model"] == "claude-fable-5-1", (
        "o padrão do papel de análise saiu de baixo da escada da voz sem ela ter dito isso"
    )


async def test_the_analysts_ceiling_holds_a_reading_and_the_thinking_that_reaches_it(
    recording_client,
) -> None:
    messages = recording_client(json.dumps({"evidence_sufficient": True, "findings": []}))

    await analyse_telling_back(
        segments=[_segment(1, "A fome chegou e eles partiram.")],
        scope="1-5",
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )

    assert messages.calls[0]["max_tokens"] >= 4096, (
        "2000 era o teto do Gemini, onde o pensamento não saía de dentro dele; aqui sai, e "
        "uma leitura vazia vira UnreadableReply — o 'terminei' da equipe dá erro, não veredito"
    )


async def test_the_correction_checks_ceiling_holds_the_thinking_too(recording_client) -> None:
    messages = recording_client(json.dumps({"resolved": True, "findings": []}))

    await verify_correction(
        findings=[Finding(kind=FindingKind.MISSING, note="a fome nao foi contada")],
        earlier=_segment(1, "Eles partiram."),
        corrected=_segment(2, "A fome chegou e eles partiram."),
        chunk=1,
        scope="1-5",
        pericope_num=P,
        correction_prompt=CORRECTION,
        settings=_settings(),
    )

    assert messages.calls[0]["max_tokens"] >= 4096, (
        "1500 deixava a checagem voltar vazia, e uma correção que ninguém conseguiu ler "
        "conta como não resolvida — a equipe regrava o trecho que já tinha consertado"
    )
