"""The Golden doors: her runner plays her golden scripts against our room, in her own wire.

Her runner opens a session and plays each turn through two calls, `/golden/session` and
`/golden/turn`, with her field names and her Bearer credential, and judges the room by what
comes back. The doors run the real Guide, the real Validator and the real ladder; only STT and
TTS sit outside them. They exist only where a runner key is configured, and never reach a
tablet.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import internalization_room as room
from app.services.internalization_room import llm
from tests.text_seam_harness import (
    BEARER,
    GOLDEN,
    GUIDE_LINE,
    RUNNER_KEY,
    TEAM_LINE,
    the_app,
    the_models_answer,
)
from tests.turn_harness import the_room_agent_is

CORRECTED_LINE = "Vamos ficar com o que a passagem conta."
UNREPAIRABLE_LINE = (
    "Vamos parar um instante aqui e olhar de novo o que está acontecendo nesta parte da passagem."
)
HER_P01 = json.loads(
    (Path(__file__).parent / "fixtures/golden/P01-opening-and-mother-tongue.wire.json").read_text(
        encoding="utf-8"
    )
)
INTERRUPTED_NOTE = "[A equipe interrompeu a sua fala anterior neste ponto.]"
CUT_IN = "Espera, espera. Antes disso: a Noemi ficou sozinha ou ficou com os filhos?"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    the_models_answer(monkeypatch)

    async def _never_voiced(text: str, **_: Any) -> None:
        raise AssertionError(f"a porta dourada pediu um clipe ao sintetizador: {text!r}")

    monkeypatch.setattr(room, "synthesize_facilitator_speech", _never_voiced)
    transport = ASGITransport(app=the_app(db_session))
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=BEARER) as c:
        yield c


async def _a_session(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{GOLDEN}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )
    assert created.status_code == 200, created.text
    return str(created.json()["sessionId"])


async def _an_open_session(client: httpx.AsyncClient) -> str:
    session_id = await _a_session(client)
    opened = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "session_start"}
    )
    assert opened.status_code == 200, opened.text
    return session_id


def _spoken(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"role": m["role"], "text": m["text"]} for m in messages]


def _passes_her_runner(answered: httpx.Response, field: str) -> None:
    """Her `playSessionHttp` validation: 2xx, a JSON object, and the fields she reads."""
    assert answered.is_success, answered.text
    body = answered.json()
    assert isinstance(body, dict), answered.text
    assert isinstance(body.get(field), str) and body[field].strip(), answered.text
    if field == "guideText":
        assert isinstance(body.get("outcome"), str) and body["outcome"].strip(), answered.text


async def test_her_runner_opens_a_ruth_p01_session_in_portuguese_and_gets_a_session_back(
    client,
) -> None:
    created = await client.post(
        f"{GOLDEN}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )

    assert created.status_code == 200, created.text
    assert created.json()["sessionId"], "a sessão abriu sem um id que o runner pudesse guardar"


async def test_a_language_the_room_does_not_speak_is_refused_not_answered_in_another(
    client,
) -> None:
    created = await client.post(
        f"{GOLDEN}/session", json={"pericopeId": "P01", "language": "Terena"}
    )

    assert created.status_code == 400, created.text


async def test_her_runner_plays_a_team_text_turn_and_gets_the_voices_reply_and_an_outcome(
    client, monkeypatch
) -> None:
    session_id = await _an_open_session(client)
    agent = the_models_answer(monkeypatch)

    answered = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": TEAM_LINE}
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["guideText"] == GUIDE_LINE
    assert body["outcome"] == "pass"
    assert body["transcript"] == TEAM_LINE
    assert agent.guide_inputs == [TEAM_LINE], (
        "o teamText dela chegava vazio e o turno era recusado como sem texto"
    )


async def test_a_mother_tongue_turn_hands_the_guide_her_full_note_last_words_included(
    client, monkeypatch
) -> None:
    session_id = await _an_open_session(client)
    agent = the_models_answer(monkeypatch)
    her_note = (
        "[A equipe falou na língua materna por cerca de 12 segundos; sem transcrição — "
        "nenhuma palavra chegou até você.]"
    )

    answered = await client.post(
        f"{GOLDEN}/turn",
        json={"sessionId": session_id, "roomNote": "mother_tongue", "seconds": 12},
    )

    assert answered.status_code == 200, answered.text
    assert agent.guide_inputs == [her_note], (
        "a nota da língua materna parava em 'sem transcrição' e o Guia nunca lia que nenhuma "
        "palavra chegou até ele"
    )
    assert answered.json()["transcript"] == her_note


async def test_an_interrupted_turn_tells_the_guide_it_was_cut(client, monkeypatch) -> None:
    session_id = await _an_open_session(client)
    agent = the_models_answer(monkeypatch)

    answered = await client.post(
        f"{GOLDEN}/turn",
        json={"sessionId": session_id, "teamText": CUT_IN, "interrupted": True},
    )

    assert answered.status_code == 200, answered.text
    assert agent.guide_inputs == [f"{INTERRUPTED_NOTE} {CUT_IN}"], (
        "a interrupção que o runner dela manda era descartada e o Guia não sabia que foi cortado"
    )
    assert answered.json()["transcript"] == f"{INTERRUPTED_NOTE} {CUT_IN}"


async def test_an_interruption_with_no_words_hands_the_guide_her_note_alone(
    client, monkeypatch
) -> None:
    session_id = await _an_open_session(client)
    agent = the_models_answer(monkeypatch)

    answered = await client.post(
        f"{GOLDEN}/turn",
        json={"sessionId": session_id, "roomNote": "interrupted"},
    )

    assert answered.status_code == 200, answered.text
    assert agent.guide_inputs == [INTERRUPTED_NOTE]
    assert answered.json()["transcript"] == INTERRUPTED_NOTE


async def test_a_cut_in_in_the_mother_tongue_tells_the_guide_both_facts(
    client, monkeypatch
) -> None:
    session_id = await _an_open_session(client)
    agent = the_models_answer(monkeypatch)
    both = (
        f"{INTERRUPTED_NOTE} [A equipe falou na língua materna por cerca de 30 segundos; sem "
        "transcrição — nenhuma palavra chegou até você.]"
    )

    answered = await client.post(
        f"{GOLDEN}/turn",
        json={
            "sessionId": session_id,
            "roomNote": "mother_tongue",
            "seconds": 30,
            "interrupted": True,
        },
    )

    assert answered.status_code == 200, answered.text
    assert agent.guide_inputs == [both]
    assert answered.json()["transcript"] == both


async def test_a_session_opened_with_earlier_passages_has_the_guide_know_them_on_its_first_turn(
    client, monkeypatch
) -> None:
    agent = the_models_answer(monkeypatch)
    created = await client.post(
        f"{GOLDEN}/session",
        json={
            "pericopeId": "P04",
            "language": "Brazilian Portuguese",
            "earlierPassages": {"P01": "approved", "P02": "started", "P03": "not_worked"},
        },
    )
    assert created.status_code == 200, created.text

    opened = await client.post(
        f"{GOLDEN}/turn",
        json={"sessionId": created.json()["sessionId"], "roomNote": "session_start"},
    )

    assert opened.status_code == 200, opened.text
    assert (
        "EARLIER PASSAGES FOR THIS TEAM: Approved: Ruth 1:1\N{EN DASH}5. "
        "Started, not approved yet: Ruth 1:6\N{EN DASH}14. Not worked yet: Ruth 1:15\N{EN DASH}18."
    ) in agent.guide_systems[0], (
        "as passagens anteriores que o runner dela manda nunca chegavam ao Guia, que tratava "
        "como lembrada uma passagem que a equipe ainda não fez"
    )


async def test_a_session_opened_without_earlier_passages_hands_the_guide_no_such_line(
    client, monkeypatch
) -> None:
    agent = the_models_answer(monkeypatch)
    created = await client.post(
        f"{GOLDEN}/session", json={"pericopeId": "P04", "language": "Brazilian Portuguese"}
    )

    opened = await client.post(
        f"{GOLDEN}/turn",
        json={"sessionId": created.json()["sessionId"], "roomNote": "session_start"},
    )

    assert opened.status_code == 200, opened.text
    assert "EARLIER PASSAGES" not in agent.guide_systems[0]


async def test_her_runner_plays_a_whole_golden_script_end_to_end_without_a_contract_error(
    client,
) -> None:
    created = await client.post(f"{GOLDEN}/session", json=HER_P01["session"])
    _passes_her_runner(created, "sessionId")
    session_id = created.json()["sessionId"]

    for turn in HER_P01["turns"]:
        answered = await client.post(f"{GOLDEN}/turn", json={**turn, "sessionId": session_id})
        _passes_her_runner(answered, "guideText")


async def test_the_golden_doors_answer_404_where_no_runner_key_is_configured(
    client, monkeypatch
) -> None:
    session_id = await _a_session(client)
    monkeypatch.setattr(get_settings(), "internalization_room_runner_key", "")

    opened = await client.post(
        f"{GOLDEN}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )
    played = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": TEAM_LINE}
    )

    assert (opened.status_code, played.status_code) == (404, 404), (
        "em produção a chave do runner não existe; as portas têm de responder como rotas que "
        "não existem, nunca pedir uma credencial que ninguém recebeu"
    )


async def test_a_wrong_or_missing_bearer_token_is_refused_with_401(client) -> None:
    session = {"pericopeId": "P01", "language": "Brazilian Portuguese"}

    wrong = await client.post(
        f"{GOLDEN}/session", json=session, headers={"Authorization": "Bearer outra-chave"}
    )
    missing = await client.post(f"{GOLDEN}/session", json=session, headers={"Authorization": ""})
    in_the_seams_header = await client.post(
        f"{GOLDEN}/session",
        json=session,
        headers={"Authorization": "", "X-Access-Code": RUNNER_KEY},
    )

    assert (wrong.status_code, missing.status_code, in_the_seams_header.status_code) == (
        401,
        401,
        401,
    )


async def test_a_request_with_keys_we_do_not_know_is_answered_not_refused(client) -> None:
    created = await client.post(
        f"{GOLDEN}/session",
        json={"pericopeId": "P01", "language": "Brazilian Portuguese", "aNewKey": {"x": 1}},
    )
    assert created.status_code == 200, created.text

    opened = await client.post(
        f"{GOLDEN}/turn",
        json={
            "sessionId": created.json()["sessionId"],
            "roomNote": "session_start",
            "anotherNewKey": [1],
        },
    )

    assert opened.status_code == 200, (
        "um validador estrito que recusa chave desconhecida derruba o roteiro dela"
    )


async def test_scene_rehearsals_naming_a_scene_the_passage_does_not_have_are_refused(
    client,
) -> None:
    session_id = await _an_open_session(client)

    answered = await client.post(
        f"{GOLDEN}/turn",
        json={"sessionId": session_id, "teamText": TEAM_LINE, "sceneRehearsals": ["S1", "S9"]},
    )

    assert answered.status_code == 400, answered.text


async def test_scene_rehearsals_the_passage_has_are_kept_with_the_turn(
    client, db_session: AsyncSession
) -> None:
    session_id = await _an_open_session(client)

    answered = await client.post(
        f"{GOLDEN}/turn",
        json={"sessionId": session_id, "teamText": TEAM_LINE, "sceneRehearsals": ["S1", "S2"]},
    )

    assert answered.status_code == 200, answered.text
    session = await room.get_session(db_session, session_id)
    await db_session.refresh(session)
    assert [m.get("scene_rehearsals") for m in session.messages] == [None, None, ["S1", "S2"]], (
        "a lista de ensaios de cena que o runner dela manda era descartada e o turno não a guardava"
    )


async def test_the_opening_on_a_session_that_already_spoke_is_still_refused(client) -> None:
    session_id = await _an_open_session(client)

    again = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "session_start"}
    )

    assert again.status_code == 409, again.text


async def test_the_opening_is_the_guides_and_no_clip_is_asked_for(client, db_session) -> None:
    session_id = await _a_session(client)

    answered = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "session_start"}
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["guideText"] == GUIDE_LINE
    assert body["outcome"] == "pass"
    session = await room.get_session(db_session, session_id)
    assert _spoken(session.messages) == [{"role": "guide", "text": GUIDE_LINE}], (
        "a abertura era dita e não ficava na conversa, então o turno seguinte abria de novo"
    )


async def test_a_turn_with_neither_words_nor_a_room_note_is_refused(client) -> None:
    session_id = await _a_session(client)

    answered = await client.post(f"{GOLDEN}/turn", json={"sessionId": session_id})

    assert answered.status_code == 400, answered.text


async def test_a_turn_the_validator_mended_is_tagged_corrected(client, monkeypatch) -> None:
    session_id = await _an_open_session(client)
    the_models_answer(
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

    answered = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": TEAM_LINE}
    )

    body = answered.json()
    assert body["guideText"] == CORRECTED_LINE
    assert body["outcome"] == "corrected", (
        "o juiz é definido contra pass/corrected/fail_safe e a porta dizia pass para a "
        "versão emendada pelo Validador"
    )


async def test_a_turn_that_fell_to_a_canned_line_is_tagged_fail_safe(client, monkeypatch) -> None:
    session_id = await _an_open_session(client)
    regenerate = json.dumps(
        {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]}
    )
    the_models_answer(monkeypatch, None, regenerate, None, regenerate, None, regenerate)

    answered = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": TEAM_LINE}
    )

    body = answered.json()
    assert body["guideText"] == UNREPAIRABLE_LINE
    assert body["outcome"] == "fail_safe"


async def test_a_canned_line_on_the_first_text_answer_is_recorded_in_the_scene_just_opened(
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await _an_open_session(client)
    regenerate = json.dumps(
        {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]}
    )
    the_models_answer(monkeypatch, None, regenerate, None, regenerate, None, regenerate)

    answered = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": TEAM_LINE}
    )

    assert answered.json()["outcome"] == "fail_safe"
    stored = await room.get_session(db_session, session_id)
    await db_session.refresh(stored)
    fired = [m for m in stored.messages or [] if m.get("outcome") == "fail_safe"]
    assert fired and fired[-1].get("scene") is not None, (
        "a porta gravava o disparo do fail-safe sem cena na primeira resposta da equipe, "
        "a mesma lacuna que f50a7a54 fechou na rota falada"
    )


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
        answered = await client.post(
            f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": words}
        )
        assert answered.status_code == 200, answered.text

    assert _spoken(seen[-1]) == [
        {"role": "guide", "text": GUIDE_LINE},
        {"role": "team", "text": "Primeira fala."},
        {"role": "guide", "text": GUIDE_LINE},
        {"role": "team", "text": "Segunda fala."},
        {"role": "guide", "text": GUIDE_LINE},
        {"role": "team", "text": "Terceira fala."},
        {"role": "guide", "text": GUIDE_LINE},
    ], "a porta entregava ao turno só uma janela da conversa, e o juiz aprovaria pelo motivo errado"


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
                cache_creation=None,
            ),
        )


async def test_every_model_call_of_the_turn_comes_back_with_its_rung_and_tokens(
    client, monkeypatch, caplog
) -> None:
    session_id = await _an_open_session(client)
    the_room_agent_is(monkeypatch, turn=llm.call_agent)
    wire = _Wire([GUIDE_LINE, json.dumps({"verdict": "pass", "issues": []})])
    monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", lambda **_: wire)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-fake")
    caplog.set_level(logging.INFO, logger="app.services.internalization_room.llm")

    answered = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": TEAM_LINE}
    )

    body = answered.json()
    for call in body["usage"]:
        assert isinstance(call.pop("latency_ms"), int), (
            "a linha de uso agora carrega a latência de cada chamada, e a porta a repassa"
        )
    assert body["usage"] == [
        {
            "role": "guide",
            "rung": "claude-fable-5-1",
            "input_tokens": 1200,
            "output_tokens": len(GUIDE_LINE),
            "cache_read_tokens": 896000,
            "cache_write_tokens": 0,
            "cost_usd": 0.23895,
        },
        {
            "role": "validator",
            "rung": "claude-fable-5-1",
            "input_tokens": 1200,
            "output_tokens": len('{"verdict": "pass", "issues": []}'),
            "cache_read_tokens": 896000,
            "cache_write_tokens": 0,
            "cost_usd": 0.23765,
        },
    ], (
        "o custo de um turno ficava só no log do servidor, longe do runner que compara com o "
        "dela; e sem o papel as três chamadas de um turno eram indistinguíveis na linha de uso"
    )
    assert body["latencyMs"] >= 0


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

    answered = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": TEAM_LINE}
    )

    assert answered.status_code == 200, answered.text
    assert settled == [(TEAM_LINE, GUIDE_LINE)], (
        "o classificador rodava atrás da resposta e o turno seguinte lia as contas de antes, "
        "então o bloco de cobertura do Guia não era o que o app mostraria"
    )


def test_the_golden_doors_are_not_published_in_the_openapi_schema() -> None:
    from app.main import app

    published = [path for path in app.openapi()["paths"] if "golden" in path or "text-seam" in path]

    assert published == [], (
        "o /openapi.json e o /docs de produção não têm autenticação, então as portas "
        "anunciavam os seus caminhos, os corpos e o cabeçalho da chave exatamente onde o "
        "404 existe para não anunciar nada"
    )
