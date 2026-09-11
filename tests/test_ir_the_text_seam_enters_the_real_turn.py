"""The text seam: her golden runner reaches our turn loop with a sentence, not a microphone.

Every path into a turn started at audio, so the question that matters most — does our voice
behave like the one that passed five golden sessions — had no cheap answer. The seam takes
the team's words as text, runs the real Guide, the real Validator and the real ladder, and
hands back what the judge reads: the Guide's spoken words and the outcome tag. Only STT and
TTS sit outside it. It exists only where a runner key is configured, and it never reaches a
tablet.
"""

from __future__ import annotations

import json
import logging
import sys
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import router
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.services import internalization_room as room
from app.services.internalization_room import llm

SEAM = "/api/internalization-room/text-seam"
RUNNER_KEY = "runner-de-teste"
GUIDE_LINE = "Olá, eu sou o Facilitador Digital. Vamos começar pelo todo."
TEAM_LINE = "Bom dia. Somos a equipe Terena. Pode continuar."
CORRECTED_LINE = "Vamos ficar com o que a passagem conta."
UNREPAIRABLE_LINE = "Quero que a gente fique perto da passagem. Vamos voltar juntos a esta cena."


class _Agent:
    """The Guide and the Validator answering as this test's script says, one entry per call."""

    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.guide_inputs: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        validating = "corrected_response" in system_prompt
        if not validating:
            self.guide_inputs.append(user_content)
        planned = self._script.pop(0) if self._script else None
        if planned is not None:
            return planned
        if validating:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


def _the_models_answer(monkeypatch: pytest.MonkeyPatch, *script: Any) -> _Agent:
    module = sys.modules["app.services.internalization_room.run_turn"]
    agent = _Agent(list(script))
    monkeypatch.setattr(module, "call_agent", agent)
    return agent


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    _the_models_answer(monkeypatch)

    async def _never_voiced(text: str, **_: Any) -> None:
        raise AssertionError(f"a costura pediu um clipe ao sintetizador: {text!r}")

    monkeypatch.setattr(room, "synthesize_facilitator_speech", _never_voiced)

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/internalization-room")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Access-Code": RUNNER_KEY}
    ) as c:
        yield c


async def _a_session(client: httpx.AsyncClient, language: str = "Brazilian Portuguese") -> str:
    created = await client.post(f"{SEAM}/session", json={"pericopeId": "P01", "language": language})
    assert created.status_code == 200, created.text
    return created.json()["sessionId"]


async def test_a_runner_with_the_key_opens_a_session_on_the_passage(client) -> None:
    created = await client.post(
        f"{SEAM}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )

    assert created.status_code == 200, created.text
    body = created.json()
    assert body["pericopeId"] == "P01"
    assert body["sessionId"], "a sessão abriu sem um id que o runner pudesse guardar"
    assert body["language"] == "pt", (
        "o roteiro dela nomeia a língua por extenso e a sala só falava em códigos, então "
        "'Brazilian Portuguese' era recusado como uma língua que a sala não fala"
    )


async def test_a_language_the_room_does_not_speak_is_refused_not_answered_in_another(
    client,
) -> None:
    created = await client.post(f"{SEAM}/session", json={"pericopeId": "P01", "language": "Terena"})

    assert created.status_code == 400, created.text


async def test_without_a_runner_key_the_seam_does_not_exist(client, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "internalization_room_runner_key", "")

    created = await client.post(
        f"{SEAM}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )

    assert created.status_code == 404, (
        "em produção a chave do runner não existe; a costura tem de responder como uma rota "
        "que não existe, nunca pedir uma credencial que ninguém recebeu"
    )


async def test_a_runner_with_the_wrong_key_is_refused(client) -> None:
    created = await client.post(
        f"{SEAM}/session",
        json={"pericopeId": "P01", "language": "Brazilian Portuguese"},
        headers={"X-Access-Code": "outra-chave"},
    )

    assert created.status_code == 401, created.text


async def test_a_kickoff_is_the_guides_opening_and_no_clip_is_asked_for(client, db_session) -> None:
    session_id = await _a_session(client)

    answered = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "kickoff": True})

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["guideText"] == GUIDE_LINE
    assert body["transcript"] == ""
    assert body["outcome"] == "pass"
    session = await room.get_session(db_session, session_id)
    assert session.messages == [{"role": "guide", "text": GUIDE_LINE}], (
        "a abertura era dita e não ficava na conversa, então o turno seguinte abria de novo"
    )


async def test_a_second_kickoff_on_an_open_session_is_a_conflict(client) -> None:
    session_id = await _a_session(client)
    await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "kickoff": True})

    again = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "kickoff": True})

    assert again.status_code == 409, again.text


async def test_the_teams_words_enter_where_the_transcriber_would_have_put_them(
    client, monkeypatch
) -> None:
    agent = _the_models_answer(monkeypatch)
    session_id = await _a_session(client)
    await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "kickoff": True})

    answered = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "text": TEAM_LINE})

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["transcript"] == TEAM_LINE
    assert body["guideText"] == GUIDE_LINE
    assert body["outcome"] == "pass"
    assert TEAM_LINE in agent.guide_inputs[-1], (
        "as palavras chegavam à costura e o Guia respondia a um turno vazio"
    )


async def test_a_turn_with_neither_words_nor_kickoff_is_refused(client) -> None:
    session_id = await _a_session(client)

    answered = await client.post(f"{SEAM}/turn", json={"sessionId": session_id})

    assert answered.status_code == 400, answered.text


async def _an_open_session(client: httpx.AsyncClient) -> str:
    session_id = await _a_session(client)
    kicked = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "kickoff": True})
    assert kicked.status_code == 200, kicked.text
    return session_id


async def test_a_turn_the_validator_mended_is_tagged_corrected(client, monkeypatch) -> None:
    session_id = await _an_open_session(client)
    _the_models_answer(
        monkeypatch,
        "Eles tinha dez filhos.",
        json.dumps(
            {
                "verdict": "correct",
                "issues": [{"problem": "invented_detail", "claim": "tinha dez filhos"}],
                "corrected_response": CORRECTED_LINE,
            }
        ),
    )

    answered = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "text": TEAM_LINE})

    body = answered.json()
    assert body["guideText"] == CORRECTED_LINE
    assert body["outcome"] == "corrected", (
        "o juiz é definido contra pass/corrected/fail_safe e a costura dizia pass para a "
        "versão emendada pelo Validador"
    )


async def test_a_turn_that_fell_to_a_canned_line_is_tagged_fail_safe(client, monkeypatch) -> None:
    session_id = await _an_open_session(client)
    regenerate = json.dumps(
        {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]}
    )
    _the_models_answer(monkeypatch, None, regenerate, None, regenerate, None, regenerate)

    answered = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "text": TEAM_LINE})

    body = answered.json()
    assert body["guideText"] == UNREPAIRABLE_LINE
    assert body["outcome"] == "fail_safe"


MOTHER_TONGUE_NOTE = "[A equipe falou na língua materna por cerca de 40 segundos; sem transcrição]"
OFF_BRIDGE_LINE = (
    "Que bom — vocês experimentaram na língua de vocês. Eu não consigo conferir essas "
    "palavras diretamente. Agora, alguém pode me contar em português o que vocês disseram?"
)


async def test_mother_tongue_enters_where_the_recognizer_would_have_flagged_it(
    client, monkeypatch
) -> None:
    session_id = await _an_open_session(client)
    agent = _the_models_answer(monkeypatch)

    answered = await client.post(
        f"{SEAM}/turn",
        json={"sessionId": session_id, "text": MOTHER_TONGUE_NOTE, "motherTongue": 40},
    )

    body = answered.json()
    assert body["guideText"] == OFF_BRIDGE_LINE, (
        "a nota chegava como palavras da equipe e o Guia respondia a ela em vez de a sala "
        "tomar o caminho que já tem para uma fala fora da língua-ponte"
    )
    assert body["outcome"] == "fail_safe"
    assert agent.guide_inputs == [], "nenhum modelo é chamado numa fala em língua materna"


async def test_the_fourth_turn_is_run_over_every_earlier_exchange_not_a_window(
    client, monkeypatch
) -> None:
    seen: list[list[dict[str, str]]] = []
    real_turn = room.run_comprehension_turn

    async def _watching(db: Any, session: Any, **kwargs: Any) -> Any:
        seen.append(list(session.messages or []))
        return await real_turn(db, session, **kwargs)

    monkeypatch.setattr(room, "run_comprehension_turn", _watching)
    session_id = await _an_open_session(client)
    said = ["Primeira fala.", "Segunda fala.", "Terceira fala.", "Quarta fala."]
    for words in said:
        answered = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "text": words})
        assert answered.status_code == 200, answered.text

    assert seen[-1] == [
        {"role": "guide", "text": GUIDE_LINE},
        {"role": "team", "text": "Primeira fala."},
        {"role": "guide", "text": GUIDE_LINE},
        {"role": "team", "text": "Segunda fala."},
        {"role": "guide", "text": GUIDE_LINE},
        {"role": "team", "text": "Terceira fala."},
        {"role": "guide", "text": GUIDE_LINE},
    ], (
        "a costura entregava ao turno só uma janela da conversa, e o juiz aprovaria pelo "
        "motivo errado"
    )


class _Wire:
    """The provider answering the real `call_agent`, one scripted reply per call."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.messages = self

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        text = self._replies.pop(0)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            stop_reason="end_turn",
            model="claude-fable-5-1",
            usage=SimpleNamespace(
                input_tokens=1200,
                output_tokens=len(text),
                cache_read_input_tokens=896000,
                cache_creation_input_tokens=0,
            ),
        )


async def test_every_model_call_of_the_turn_comes_back_with_its_rung_and_tokens(
    client, monkeypatch, caplog
) -> None:
    session_id = await _an_open_session(client)
    run_turn = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(run_turn, "call_agent", llm.call_agent)
    wire = _Wire([GUIDE_LINE, json.dumps({"verdict": "pass", "issues": []})])
    monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", lambda **_: wire)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-fake")
    caplog.set_level(logging.INFO, logger="app.services.internalization_room.llm")

    answered = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "text": TEAM_LINE})

    body = answered.json()
    assert body["usage"] == [
        {
            "rung": "claude-fable-5-1",
            "input_tokens": 1200,
            "output_tokens": len(GUIDE_LINE),
            "cache_read_tokens": 896000,
            "cache_write_tokens": 0,
            "latency_ms": None,
        },
        {
            "rung": "claude-fable-5-1",
            "input_tokens": 1200,
            "output_tokens": len('{"verdict": "pass", "issues": []}'),
            "cache_read_tokens": 896000,
            "cache_write_tokens": 0,
            "latency_ms": None,
        },
    ], "o custo de um turno ficava só no log do servidor, longe do runner que compara com o dela"
    assert body["turnMs"] >= 0


async def test_the_beads_settle_before_the_answer_so_the_next_turn_reads_them(
    client, monkeypatch
) -> None:
    from app.api.internalization_room import text_seam

    settled: list[tuple[str, str]] = []

    async def _settle(*, session_id: str, team_utterance: str, guide_response: str, **_: Any):
        settled.append((team_utterance, guide_response))

    monkeypatch.setattr(text_seam, "settle_coverage", _settle)
    session_id = await _an_open_session(client)
    assert settled == [], "a abertura é uma frase que a sala escreveu para si; não move conta"

    answered = await client.post(f"{SEAM}/turn", json={"sessionId": session_id, "text": TEAM_LINE})

    assert answered.status_code == 200, answered.text
    assert settled == [(TEAM_LINE, GUIDE_LINE)], (
        "o classificador rodava atrás da resposta e o turno seguinte lia as contas de antes, "
        "então o bloco de cobertura do Guia não era o que o app mostraria"
    )
