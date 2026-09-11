"""The second door of the text seam: her frases enter as text and the room judges them.

The first door (`/text-seam/turn`) opens the Guide's conversation. This one opens the
back-translation check: a runner declares a session over her clips, then plays a round of
frases as text through the real path — the Correction check when a frase supersedes, the
Analyst's reading, the Speaker's verdict, the Validator — and reads back the findings with
their frase numbers, the spoken turn, the outcome tag and `conferida`.

Nothing here is a shortcut around the room: the only things outside are the microphone and
the synthesiser, exactly as on the Guide's door.
"""

from __future__ import annotations

import importlib
import json
import logging
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import router
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.db.models.internalization_room import IRTakeKind
from app.services import internalization_room as room
from app.services.internalization_room.back_translation import playback_confirms_rehearsal
from app.services.internalization_room.takes import takes_of
from tests.test_ir_a_correction_is_verified_on_its_own import CORRECTION_MARK

SEAM = "/api/internalization-room/text-seam/back-translation"
RUNNER_KEY = "runner-de-teste"
PASSAGE = "P02"
LANGUAGE = "Brazilian Portuguese"

#: Her `draft.clips` of the three P02 scripts, key and duration and nothing else: a clip is
#: declared, never uploaded.
CLIPS = [
    {"key": "S1", "durationMs": 20000},
    {"key": "S2", "durationMs": 25000},
    {"key": "S3", "durationMs": 45000},
]

#: Round one of her `golden/bt/P02-causa-a-mais.json`, typed here rather than read from her
#: repository, as the plan requires. The map is `_spec/canon/meaning-map/P02-Ruth-1-6-14.md`,
#: scene 1 (Ruth 1:6-7), rule R1 of the compilation log: the news of the bread is present and
#: an extra cause — "porque as noras pediram" — is added beside it on frase 1.
CAUSA_A_MAIS = [
    {
        "clipKey": "S1",
        "coversFrom": 0,
        "coversTo": 10,
        "text": (
            "Noemi ouviu, nos campos de Moabe, que o Senhor tinha dado pão ao seu povo, e "
            "decidiu voltar para Judá porque as noras pediram."
        ),
    },
    {
        "clipKey": "S1",
        "coversFrom": 10,
        "coversTo": 20,
        "text": (
            "Ela saiu do lugar onde estava, com as duas noras, e as três foram andando pela "
            "estrada para voltar para a terra de Judá."
        ),
    },
    {
        "clipKey": "S2",
        "coversFrom": 0,
        "coversTo": 8,
        "text": (
            "No caminho, Noemi disse para as duas noras: vão, voltem cada uma para a casa da "
            "sua mãe."
        ),
    },
    {
        "clipKey": "S2",
        "coversFrom": 8,
        "coversTo": 17,
        "text": (
            "Que o Senhor trate vocês com bondade, como vocês trataram os que morreram e a "
            "mim. Que o Senhor dê a vocês descanso, cada uma na casa de um marido."
        ),
    },
    {
        "clipKey": "S2",
        "coversFrom": 17,
        "coversTo": 25,
        "text": (
            "Ela beijou as duas, e elas choraram alto. E disseram: não, nós vamos voltar com a "
            "senhora para o seu povo."
        ),
    },
    {
        "clipKey": "S3",
        "coversFrom": 0,
        "coversTo": 10,
        "text": (
            "Noemi disse: voltem, minhas filhas. Por que vocês iriam comigo? Eu ainda tenho "
            "filhos dentro de mim para serem maridos de vocês?"
        ),
    },
    {
        "clipKey": "S3",
        "coversFrom": 10,
        "coversTo": 25,
        "text": (
            "Voltem, vão. Eu estou velha demais para ter marido. Mesmo se eu dissesse que "
            "tenho esperança, e tivesse marido esta noite e tivesse filhos, vocês iam esperar "
            "até eles crescerem? Iam ficar sem casar por causa deles?"
        ),
    },
    {
        "clipKey": "S3",
        "coversFrom": 25,
        "coversTo": 33,
        "text": (
            "Não, minhas filhas. Para mim é muito mais amargo do que para vocês, porque a mão "
            "do Senhor se voltou contra mim."
        ),
    },
    {
        "clipKey": "S3",
        "coversFrom": 33,
        "coversTo": 45,
        "text": (
            "Elas choraram alto de novo. Orfa beijou a sogra e voltou. Mas Rute se agarrou a Noemi."
        ),
    },
]

#: Her round two of the same script: frase 1 told again, faithfully, superseding the first.
FAITHFUL_FRASE_ONE = {
    "clipKey": "S1",
    "coversFrom": 0,
    "coversTo": 10,
    "text": (
        "Noemi ouviu, nos campos de Moabe, que o Senhor tinha visitado o seu povo e dado pão a "
        "eles. Então ela se levantou com as duas noras para voltar dos campos de Moabe."
    ),
    "supersedes": 0,
}

THE_EXTRA_CAUSE = (
    "A tradução diz que Noemi decidiu voltar porque as noras pediram; a história conta apenas "
    "que ela ouviu a notícia do pão."
)
THE_VOICE = (
    "Vocês traduziram bem quase tudo. Na frase 1 vocês disseram que as noras pediram. Isso "
    "está no áudio de vocês, ou entrou agora na tradução?"
)


class Analyst:
    """The analyst in its two modes, each answering what the case set.

    The whole reading answers the next entry of `readings`; the correction check answers
    `resolves` and whatever `broke` carries. The two are told apart by the heading only the
    correction prompt has, the way a reader would — not by counting calls.
    """

    def __init__(self) -> None:
        self.readings: list[dict[str, Any]] = []
        self.verifications: list[str] = []
        self.answered: list[str] = []
        self.resolves = True
        self.broke: list[dict[str, str]] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if CORRECTION_MARK in system_prompt:
            self.verifications.append(system_prompt)
            return json.dumps({"resolved": self.resolves, "findings": self.broke})
        reply = json.dumps(self.readings.pop(0) if self.readings else {"findings": []})
        self.answered.append(reply)
        return reply


class Speaker:
    """The verdict Speaker and the Validator behind it, saying what the case set."""

    def __init__(self) -> None:
        self.line = THE_VOICE

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self.line


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    from app.services.internalization_room import back_translation as bt_service

    reader = Analyst()
    monkeypatch.setattr(bt_service, "call_agent", reader)
    return reader


@pytest.fixture()
def speaker(monkeypatch: pytest.MonkeyPatch) -> Speaker:
    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    voice = Speaker()
    monkeypatch.setattr(turn_module, "call_agent", voice)
    return voice


def _the_app(db_session: AsyncSession):
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/internalization-room")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    return test_app


@pytest.fixture()
async def client(
    db_session: AsyncSession,
    analyst: Analyst,
    speaker: Speaker,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )

    async def _never_voiced(text: str, **_: Any) -> None:
        raise AssertionError(f"a costura pediu um clipe ao sintetizador: {text!r}")

    monkeypatch.setattr(room, "synthesize_facilitator_speech", _never_voiced)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=_the_app(db_session)),
        base_url="http://test",
        headers={"X-Access-Code": RUNNER_KEY},
    ) as c:
        yield c


async def _a_session(client: httpx.AsyncClient) -> str:
    declared = await client.post(
        f"{SEAM}/session",
        json={"pericopeId": PASSAGE, "language": LANGUAGE, "clips": CLIPS},
    )
    assert declared.status_code == 200, declared.text
    return str(declared.json()["sessionId"])


async def _a_round(client: httpx.AsyncClient, session_id: str, frases: list[dict]) -> dict:
    played = await client.post(f"{SEAM}/round", json={"sessionId": session_id, "frases": frases})
    assert played.status_code == 200, played.text
    return dict(played.json())


async def test_the_door_is_shut_without_the_key(client, monkeypatch) -> None:
    with_the_key = await client.post(
        f"{SEAM}/session", json={"pericopeId": PASSAGE, "language": LANGUAGE, "clips": CLIPS}
    )
    assert with_the_key.status_code == 200, (
        "o controle positivo: sem ele um 404 não distingue a porta fechada de uma rota que "
        "nunca foi escrita"
    )

    session_id = with_the_key.json()["sessionId"]
    monkeypatch.setattr(get_settings(), "internalization_room_runner_key", "")

    declared = await client.post(
        f"{SEAM}/session", json={"pericopeId": PASSAGE, "language": LANGUAGE, "clips": CLIPS}
    )
    played = await client.post(
        f"{SEAM}/round", json={"sessionId": session_id, "frases": CAUSA_A_MAIS[:1]}
    )

    assert (declared.status_code, played.status_code) == (404, 404), (
        "em produção a chave do runner não existe; as duas portas têm de responder como rotas "
        "que não existem, nunca pedir uma credencial que ninguém recebeu"
    )


async def test_the_door_refuses_a_wrong_key(client) -> None:
    session_id = await _a_session(client)
    wrong = {"X-Access-Code": "outra-chave"}

    declared = await client.post(
        f"{SEAM}/session",
        json={"pericopeId": PASSAGE, "language": LANGUAGE, "clips": CLIPS},
        headers=wrong,
    )
    played = await client.post(
        f"{SEAM}/round",
        json={"sessionId": session_id, "frases": CAUSA_A_MAIS[:1]},
        headers=wrong,
    )

    assert (declared.status_code, played.status_code) == (401, 401), declared.text


async def test_the_door_is_not_published_in_the_openapi_schema(db_session) -> None:
    mounted = sorted(
        route.path  # type: ignore[attr-defined]
        for route in router.routes
        if "text-seam/back-translation" in getattr(route, "path", "")
    )
    assert len(mounted) == 2, (
        "o controle positivo: as duas rotas existem no router, senão a ausência delas no "
        "schema não prova nada"
    )

    paths = _the_app(db_session).openapi()["paths"]

    assert [path for path in paths if "text-seam" in path] == [], (
        "a costura é um instrumento de teste; publicada no schema ela vira uma superfície de "
        "produto que um cliente pode gerar e chamar"
    )


async def test_a_declared_session_has_her_parts_heard(client, db_session) -> None:
    declared = await client.post(
        f"{SEAM}/session",
        json={"pericopeId": PASSAGE, "language": LANGUAGE, "clips": CLIPS},
    )

    assert declared.status_code == 200, declared.text
    body = declared.json()
    assert [part["key"] for part in body["parts"]] == ["S1", "S2", "S3"]

    session = await room.get_session(db_session, body["sessionId"])
    assert session.project_id is None, (
        "a costura não é o trabalho de nenhuma equipe; uma sessão dela com projeto entraria "
        "no histórico de alguém"
    )
    takes = await takes_of(db_session, session.id)
    assert [take.kind for take in takes] == [IRTakeKind.ENSAIO] * 3
    state = room.back_translation_of(session)
    assert [entry.clip_duration_ms for entry in state.played_by_take] == [20000, 25000, 45000]
    assert playback_confirms_rehearsal(state, [take.id for take in takes]) == [], (
        "o roteiro dela marca cada clipe como ouvido por inteiro antes da primeira rodada; "
        "sem isso a passagem nunca fecha e a rodada dela mede outra coisa"
    )


async def test_the_causa_a_mais_round_carries_an_addition_on_frase_1_and_no_missing(
    client, analyst
) -> None:
    analyst.readings = [{"findings": [{"kind": "addition", "note": THE_EXTRA_CAUSE, "chunk": 1}]}]
    session_id = await _a_session(client)

    result = await _a_round(client, session_id, CAUSA_A_MAIS)

    assert [(one["kind"], one["frase"]) for one in result["findings"]] == [("addition", 1)]
    assert result["findings"][0]["stretchId"], "o achado tem de nomear o trecho que ele pega"
    assert "frase 1" in result["spoken"]
    assert result["outcome"] == "pass"
    assert result["conferida"] is False
    assert result["findingsRemaining"] == 1
    assert result["missingWithoutFrase"] == 0


async def test_a_superseding_frase_runs_the_correction_check_then_the_reading(
    client, analyst, db_session
) -> None:
    analyst.readings = [{"findings": [{"kind": "addition", "note": THE_EXTRA_CAUSE, "chunk": 1}]}]
    session_id = await _a_session(client)
    await _a_round(client, session_id, CAUSA_A_MAIS)

    result = await _a_round(client, session_id, [FAITHFUL_FRASE_ONE])

    assert len(analyst.verifications) == 1, (
        "uma frase que supera outra é uma correção: a sala verifica a correção contra o achado "
        "que a pediu, e só depois lê a passagem inteira"
    )
    assert result["findings"] == []
    assert result["conferida"] is True
    told = room.told_back(await room.final_segments(db_session, session_id))
    assert len(told) == len(CAUSA_A_MAIS), "a frase nova substitui a primeira, não se soma a ela"
    assert told[0].pass_number == 2
    assert told[0].transcript == FAITHFUL_FRASE_ONE["text"]


async def test_two_superseding_frases_in_one_round_both_replace_their_stretches(
    client, analyst, db_session
) -> None:
    analyst.readings = [
        {
            "findings": [
                {"kind": "addition", "note": THE_EXTRA_CAUSE, "chunk": 1},
                {"kind": "unclear", "note": "A frase 3 ficou difícil de seguir.", "chunk": 3},
            ]
        }
    ]
    session_id = await _a_session(client)
    await _a_round(client, session_id, CAUSA_A_MAIS)
    retold_third = {
        "clipKey": "S2",
        "coversFrom": 0,
        "coversTo": 8,
        "text": "No caminho, Noemi disse às duas noras que voltassem para a casa das suas mães.",
        "supersedes": 2,
    }

    result = await _a_round(client, session_id, [FAITHFUL_FRASE_ONE, retold_third])

    assert analyst.verifications == [], (
        "duas posições mudadas não são uma correção; a sala cai na leitura inteira, que é a "
        "resposta que nunca está errada"
    )
    assert result["conferida"] is True
    told = room.told_back(await room.final_segments(db_session, session_id))
    assert [told[0].transcript, told[2].transcript] == [
        FAITHFUL_FRASE_ONE["text"],
        retold_third["text"],
    ]
    assert [told[0].pass_number, told[2].pass_number] == [2, 2]


async def test_a_supersedes_on_a_slice_where_nothing_stands_is_refused(client) -> None:
    session_id = await _a_session(client)

    refused = await client.post(
        f"{SEAM}/round",
        json={
            "sessionId": session_id,
            "frases": [{**FAITHFUL_FRASE_ONE, "coversFrom": 12, "coversTo": 18}],
        },
    )

    assert refused.status_code == 400, refused.text
    assert "1" in refused.json()["detail"], (
        "o runner dela lê a recusa sem o roteiro na mão: ela tem de nomear a frase que não "
        "encontrou nada para superar"
    )


async def test_a_swap_is_one_thing_in_the_round_result(client, analyst) -> None:
    analyst.readings = [
        {
            "findings": [
                {
                    "kind": "missing",
                    "note": "A notícia do pão não é contada.",
                    "chunk": 1,
                    "where": "inside",
                },
                {"kind": "addition", "note": THE_EXTRA_CAUSE, "chunk": 1},
                {"kind": "unclear", "note": "A frase 7 ficou difícil de seguir.", "chunk": 7},
            ]
        }
    ]
    session_id = await _a_session(client)

    result = await _a_round(client, session_id, CAUSA_A_MAIS)

    assert [one["kind"] for one in result["findings"]] == ["addition", "missing", "unclear"], (
        "a adição lidera a troca, seja qual for a metade que o analista listou primeiro: é ela "
        "que nomeia o trecho onde a troca aconteceu. O que não é da troca vem atrás, na ordem "
        "do analista: um achado que a costura engolisse passaria no `no_kinds` dela como se a "
        "sala não o tivesse levantado"
    )
    assert [one["frase"] for one in result["findings"]] == [1, 1, 7]
    assert result["findingsRemaining"] == 2, (
        "uma relação trocada é uma coisa só para a equipe: uma fala, uma gravação de novo — "
        "a troca e o `unclear` são duas paradas, não três"
    )


async def test_a_missing_without_a_frase_is_counted_and_logged(client, analyst, caplog) -> None:
    analyst.readings = [
        {"findings": [{"kind": "missing", "note": "Falta a notícia do pão.", "where": "after"}]}
    ]
    session_id = await _a_session(client)

    with caplog.at_level(
        logging.WARNING, logger="app.services.internalization_room.back_translation"
    ):
        result = await _a_round(client, session_id, CAUSA_A_MAIS)

    assert result["findings"][0]["frase"] is None
    assert result["missingWithoutFrase"] == 1, (
        "o item 1 do bloco dobrado: a costura mede com que frequência o modelo deixa a frase "
        "de fora, porque o item dela não pode ser editado até a Marcia decidir"
    )
    landed = [
        record
        for record in caplog.records
        if "missing" in record.getMessage() and session_id in record.getMessage()
    ]
    assert len(landed) == 1, (
        "uma falta sem frase aterrissava sem endereço e sem uma linha sequer; produção não "
        "tinha como contar um modelo desobediente"
    )
    assert analyst.answered[0] in landed[0].getMessage(), (
        "a linha carrega a resposta crua inteira, como toda recusa deste arquivo carrega"
    )


async def test_a_round_with_no_frases_is_refused_rather_than_read_as_clean(client) -> None:
    session_id = await _a_session(client)

    refused = await client.post(f"{SEAM}/round", json={"sessionId": session_id, "frases": []})

    assert refused.status_code == 400, (
        "o analista comparado contra nada responde sem achados, e nenhum achado é do que a "
        "`conferida` é feita: uma rodada vazia voltava PASS num roteiro que ninguém contou"
    )


async def test_two_clips_with_one_key_are_refused(client) -> None:
    twice = {"key": "S1", "durationMs": 20000}

    refused = await client.post(
        f"{SEAM}/session",
        json={"pericopeId": PASSAGE, "language": LANGUAGE, "clips": [twice, twice]},
    )

    assert refused.status_code == 400, (
        "o roteiro dela é lido literalmente e ninguém o valida; duas partes com a mesma chave "
        "colidiam no índice e o operador recebia um erro de integridade em vez da causa"
    )


async def test_a_missing_without_a_frase_is_counted_once_and_not_again_next_round(
    client, analyst
) -> None:
    analyst.readings = [
        {
            "findings": [
                {"kind": "addition", "note": THE_EXTRA_CAUSE, "chunk": 1},
                {"kind": "missing", "note": "Falta a notícia do pão.", "where": "after"},
            ]
        }
    ]
    session_id = await _a_session(client)
    first = await _a_round(client, session_id, CAUSA_A_MAIS)
    assert first["missingWithoutFrase"] == 1

    analyst.resolves = False
    second = await _a_round(client, session_id, [FAITHFUL_FRASE_ONE])

    assert second["findings"], "o achado continua de pé: é o que torna a recontagem possível"
    assert second["missingWithoutFrase"] == 0, (
        "o número é sobre o que o modelo respondeu NESTA rodada. Contado sobre a lista que "
        "fica de pé, um achado sem frase da rodada 1 era recontado em cada rodada seguinte, e "
        "quem somasse o campo pelo roteiro media o mesmo fato várias vezes"
    )
